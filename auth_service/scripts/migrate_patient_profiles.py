"""
One-time migration: fix patient_profile_id in the users collection.

PROBLEM
-------
Legacy patient_profiles documents were created by the appointments service
and carry UUID patient_ids (e.g. "772da821-4e2f-4d61-a05e-8d33b6759658").
auth_service.signup_patient() generates slug-based IDs ("patient-mehdiletaief").
When a legacy patient registered via the auth_service, their user document
got a slug ID that doesn't match any patient_profiles document, so
GET /profile always returns 404.

FIX
---
For every patient user in `clinix_agent.users`:
  1. Check if stored patient_profile_id resolves to a patient_profiles doc.
  2. If not, look up the profile by email.
  3. If found by email: update the user's patient_profile_id to the real UUID.
  4. If not found by email at all: log as UNRESOLVED (manual review needed).

SAFE TO RE-RUN: checks are idempotent.

Run from the repo root:
    cd auth_service
    python -m scripts.migrate_patient_profiles
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.mongo_client import close_mongo_connection, connect_to_mongo, get_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


async def migrate() -> None:
    await connect_to_mongo()
    db = get_database()
    if db is None:
        logger.error("MongoDB connection failed — check MONGODB_URI in .env")
        return

    users_col    = db["users"]
    profiles_col = db["patient_profiles"]

    patients = await users_col.find({"role": "patient"}).to_list(length=50_000)
    logger.info("Found %d patient user(s) to process", len(patients))

    already_ok  = 0
    fixed       = 0
    unresolved  = 0

    for user in patients:
        email     = user.get("email", "")
        stored_id = user.get("patient_profile_id", "")

        # ── Step 1: check stored id ───────────────────────────────────────
        by_id = await profiles_col.find_one(
            {"patient_id": stored_id}, {"patient_id": 1}
        )
        if by_id:
            already_ok += 1
            logger.info("  OK        %-42s  id=%r", email, stored_id)
            continue

        # ── Step 2: fall back to email ────────────────────────────────────
        by_email = await profiles_col.find_one(
            {"email": email.lower()}, {"patient_id": 1, "name": 1}
        )
        if by_email:
            correct_id = by_email["patient_id"]
            await users_col.update_one(
                {"email": email.lower()},
                {"$set": {"patient_profile_id": correct_id}},
            )
            logger.info(
                "  FIXED     %-42s  %r  →  %r",
                email, stored_id, correct_id,
            )
            fixed += 1
            continue

        # ── Step 3: no match at all ───────────────────────────────────────
        logger.warning("  UNRESOLVED %-42s  stored_id=%r", email, stored_id)
        unresolved += 1

    logger.info("")
    logger.info(
        "Done: %d already correct | %d fixed | %d unresolved",
        already_ok, fixed, unresolved,
    )
    if unresolved:
        logger.warning(
            "UNRESOLVED users have no patient_profiles document by id or email.\n"
            "They will receive a fresh profile when they next log in and the\n"
            "auth_service creates a new slug-based patient_profiles stub."
        )

    await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(migrate())
