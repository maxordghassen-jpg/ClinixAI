"""
Migration: consolidate all patient profile data into the UUID-based canonical document.

BACKGROUND
----------
The system has two types of patient_profiles documents:

  UUID doc   patient_id = "76985768-4c45-4307-a258-144e07f4fd1a"
             Created by the appointments/seeding system.
             Has: name, email, phone, gender.
             Missing: medical fields, AI data.

  Slug doc   patient_id = "patient-amira-bouazizi"
             Created by auth_service.signup_patient().
             Has: blood_type, smoking_status, appointment_history, etc.
             Missing: name, email, phone, gender.

The canonical document is the UUID doc.  All profile saves must write to it.

WHAT THIS SCRIPT DOES
---------------------
For every patient user whose users.patient_profile_id is a slug:
  1. Load the slug doc (source of medical/behavioral data).
  2. Find the UUID doc by the user's email (canonical target).
  3. Merge profile fields from slug → UUID doc using $set with null-safe logic:
       - Identity fields (name, email, phone, gender): keep UUID values, copy only
         if UUID field is null/missing.
       - Medical fields: copy from slug if present.
       - AI/behavioral fields (preferred_doctors, preferred_specialties,
         recurring_symptoms): copy from slug if present.
       NOTE: appointment_history and stats are NOT copied — they are agent data
             stored separately and are not part of the patient profile schema.
  4. Update users.patient_profile_id to the UUID patient_id.
  5. Log before/after for every affected patient.

GUARANTEES
----------
  - Idempotent: safe to run multiple times.
  - Non-destructive: slug doc is NOT deleted (orphan, can be removed later).
  - appointment_history / stats / preconsultation data are untouched.

Run from auth_service/ directory:
    python scripts/migrate_to_uuid_canonical.py           # live run
    python scripts/migrate_to_uuid_canonical.py --dry-run # preview only
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.mongo_client import close_mongo_connection, connect_to_mongo, get_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

DRY_RUN = "--dry-run" in sys.argv

# Fields copied from slug → UUID (medical / AI-curated, not identity).
_PROFILE_FIELDS = [
    # Vitals
    "weight", "height", "blood_type",
    # Personal medical
    "date_of_birth", "address", "city",
    # Lifestyle
    "smoking_status", "alcohol_consumption",
    # Medical history
    "allergies", "chronic_conditions", "current_medications",
    "past_surgeries", "family_history",
    # Emergency contact
    "emergency_contact_name", "emergency_contact_phone",
    "emergency_contact_relationship",
    # AI-curated signals
    "preferred_doctors", "preferred_specialties", "recurring_symptoms",
]

# Identity fields: copy from slug → UUID only if UUID value is null/missing.
_IDENTITY_FIELDS = ["name", "email", "phone", "gender"]


def _fmt(doc: dict) -> str:
    """Compact JSON representation for logging (skips large lists)."""
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, list):
            out[k] = f"[{len(v)} items]"
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return json.dumps(out, ensure_ascii=False, indent=2)


async def migrate() -> None:
    if DRY_RUN:
        logger.info("DRY-RUN mode — no writes will be made")

    await connect_to_mongo()
    db = get_database()
    if db is None:
        logger.error("MongoDB connection failed — check MONGODB_URI in .env")
        return

    users_col    = db["users"]
    profiles_col = db["patient_profiles"]

    patients = await users_col.find({"role": "patient"}).to_list(length=50_000)
    logger.info("Found %d patient user(s)", len(patients))

    already_canonical = 0
    migrated          = 0
    no_uuid_doc       = 0
    skipped           = 0

    for user in patients:
        email     = user.get("email", "")
        stored_id = user.get("patient_profile_id", "")

        # Only process patients whose stored ID is a slug.
        if not stored_id.startswith("patient-"):
            already_canonical += 1
            logger.debug("  SKIP (already UUID)  %s", email)
            continue

        # Load slug doc.
        slug_doc = await profiles_col.find_one({"patient_id": stored_id})
        if not slug_doc:
            skipped += 1
            logger.warning("  SKIP (slug doc missing)  %s  id=%r", email, stored_id)
            continue

        # Find UUID doc by email.
        uuid_doc = await profiles_col.find_one(
            {"email": email.lower(), "patient_id": {"$not": {"$regex": "^patient-"}}}
        )
        if not uuid_doc:
            no_uuid_doc += 1
            logger.warning(
                "  NO_UUID_DOC  %s  slug=%r  (slug becomes canonical — no action needed)",
                email, stored_id,
            )
            # Slug is already the only doc; no migration required.
            continue

        uuid_id = uuid_doc["patient_id"]
        logger.info("  MIGRATING  %s  slug=%r  →  uuid=%r", email, stored_id, uuid_id)

        # ── Build merge payload ──────────────────────────────────────────────────
        set_fields: dict = {}

        # Medical / AI-curated fields: copy from slug if slug has the value.
        for field in _PROFILE_FIELDS:
            slug_val = slug_doc.get(field)
            if slug_val is None:
                continue
            if isinstance(slug_val, list) and len(slug_val) == 0:
                continue
            set_fields[field] = slug_val

        # Identity fields: copy from slug only if UUID doc lacks them.
        for field in _IDENTITY_FIELDS:
            uuid_val = uuid_doc.get(field)
            slug_val = slug_doc.get(field)
            if not uuid_val and slug_val:
                set_fields[field] = slug_val

        set_fields["updated_at"] = datetime.now(timezone.utc)

        logger.info(
            "    BEFORE (UUID doc):\n%s",
            _fmt({k: uuid_doc.get(k) for k in list(_IDENTITY_FIELDS) + list(_PROFILE_FIELDS)
                  if uuid_doc.get(k) is not None}),
        )
        logger.info(
            "    Fields to merge from slug: %s",
            sorted(k for k in set_fields if k != "updated_at"),
        )

        if not DRY_RUN:
            await profiles_col.update_one(
                {"patient_id": uuid_id},
                {"$set": set_fields},
            )
            await users_col.update_one(
                {"email": email.lower()},
                {"$set": {"patient_profile_id": uuid_id}},
            )

            # Verify by re-fetching.
            updated = await profiles_col.find_one({"patient_id": uuid_id})
            logger.info(
                "    AFTER  (UUID doc):\n%s",
                _fmt({k: (updated or {}).get(k)
                      for k in list(_IDENTITY_FIELDS) + list(_PROFILE_FIELDS)
                      if (updated or {}).get(k) is not None}),
            )

        migrated += 1

    logger.info("")
    logger.info(
        "Done: %d already canonical | %d migrated | %d no_uuid_doc | %d skipped",
        already_canonical, migrated, no_uuid_doc, skipped,
    )
    if no_uuid_doc:
        logger.info(
            "  Patients with no_uuid_doc: slug doc is their only profile — "
            "profile saves already write to it correctly."
        )
    if DRY_RUN:
        logger.info("DRY-RUN complete — rerun without --dry-run to apply changes.")

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(migrate())
