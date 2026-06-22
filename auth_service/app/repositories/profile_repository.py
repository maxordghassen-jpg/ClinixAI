import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo_client import get_database
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

PROFILES_COLLECTION = "patient_profiles"

MEDICAL_FIELDS = [
    # Vitals
    "weight", "height", "blood_type",
    # Personal
    "date_of_birth", "address", "city",
    # Lifestyle
    "smoking_status", "alcohol_consumption",
    # Medical history
    "allergies", "chronic_conditions",
    "current_medications", "past_surgeries", "family_history",
    # Emergency contact
    "emergency_contact_name", "emergency_contact_phone",
    "emergency_contact_relationship",
]


class ProfileRepository:

    async def get_by_patient_id(self, patient_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            doc = await db[PROFILES_COLLECTION].find_one(
                {"patient_id": patient_id}, {"_id": 0}
            )
            logger.warning(
                "[PROFILE_DEBUG] get_by_patient_id | query_id=%r | found=%s | name=%r",
                patient_id,
                doc is not None,
                doc.get("name") if doc else None,
            )
            return doc
        except Exception as exc:
            logger.error("PROFILE_DEBUG] get_by_patient_id FAILED | patient=%s | %s", patient_id, exc)
            return None

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        """Fallback lookup used during login identity-mismatch correction."""
        db = get_database()
        if db is None:
            return None
        try:
            doc = await db[PROFILES_COLLECTION].find_one(
                {"email": email.lower()}, {"_id": 0}
            )
            logger.warning(
                "[PROFILE_DEBUG] get_by_email | email=%r | found=%s | patient_id=%r",
                email,
                doc is not None,
                doc.get("patient_id") if doc else None,
            )
            return doc
        except Exception as exc:
            logger.error("[PROFILE_DEBUG] get_by_email FAILED | email=%s | %s", email, exc)
            return None

    async def upsert_fields(self, patient_id: str, fields: dict[str, Any]) -> bool:
        db = get_database()
        if db is None:
            logger.error("[WRITE_TRACE] upsert_fields | db is None — no connection")
            return False
        try:
            now = datetime.now(timezone.utc)
            mongo_filter = {"patient_id": patient_id}
            mongo_update = {
                "$set": {**fields, "updated_at": now},
                "$setOnInsert": {"patient_id": patient_id, "created_at": now},
            }

            # ── BEFORE ──────────────────────────────────────────────────────────
            before = await db[PROFILES_COLLECTION].find_one(mongo_filter, {"_id": 0})
            logger.warning(
                "[WRITE_TRACE] upsert_fields BEFORE | filter=%r | doc_exists=%s | "
                "name=%r phone=%r gender=%r blood_type=%r city=%r",
                mongo_filter,
                before is not None,
                (before or {}).get("name"),
                (before or {}).get("phone"),
                (before or {}).get("gender"),
                (before or {}).get("blood_type"),
                (before or {}).get("city"),
            )
            logger.warning(
                "[WRITE_TRACE] upsert_fields UPDATE | filter=%r | $set_keys=%s",
                mongo_filter,
                sorted(fields.keys()),
            )

            result = await db[PROFILES_COLLECTION].update_one(
                mongo_filter,
                mongo_update,
                upsert=True,
            )

            # ── AFTER ───────────────────────────────────────────────────────────
            after = await db[PROFILES_COLLECTION].find_one(mongo_filter, {"_id": 0})
            logger.warning(
                "[WRITE_TRACE] upsert_fields RESULT | matched=%d modified=%d upserted=%s",
                result.matched_count,
                result.modified_count,
                result.upserted_id,
            )
            logger.warning(
                "[WRITE_TRACE] upsert_fields AFTER | patient_id=%r | "
                "name=%r phone=%r gender=%r blood_type=%r city=%r",
                patient_id,
                (after or {}).get("name"),
                (after or {}).get("phone"),
                (after or {}).get("gender"),
                (after or {}).get("blood_type"),
                (after or {}).get("city"),
            )
            return True
        except DuplicateKeyError as exc:
            logger.error(
                "[WRITE_TRACE] upsert_fields DUPLICATE KEY | patient=%s | %s",
                patient_id, exc.details,
            )
            return False
        except Exception as exc:
            logger.error("[WRITE_TRACE] upsert_fields FAILED | patient=%s | %s", patient_id, exc)
            return False

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            await db[PROFILES_COLLECTION].create_index("patient_id", unique=True)
            # Phone numbers must be unique per patient; sparse so null values are allowed.
            await db[PROFILES_COLLECTION].create_index(
                "phone", unique=True, sparse=True, name="phone_sparse_unique"
            )
            logger.info("[PROFILE REPO] indexes ensured")
        except Exception as exc:
            logger.error("[PROFILE REPO] create_indexes failed: %s", exc)
