"""
Seed demo doctor auth accounts into clinix_agent.users.

Each demo doctor gets an auth account (email: doc-XXX@clinix.ai, password: doctor123)
linked to a REAL doctor record in medical_data_tunisia.doctors via its MongoDB
ObjectId (`_id`). This ObjectId string is what availability_service /
appointment_service / geo_service all use as `doctorId` / `doctor_id`, so the
auth account's `doctor_id` MUST be that ObjectId string for the doctor portal's
availability and appointment lookups to return data for this account.

DEMO_DOCTOR_ID_MAP below was selected from medical_data_tunisia.doctors records
that (a) have a specialty matching the demo persona where possible, and (b) have
seeded availability templates in disponibility.disponibilites. doc-002 has no
"Neurologue" specialty in the dataset, so it falls back to a Généraliste record.

Run from auth_service/ root:
    python -m scripts.seed_doctors
"""
import asyncio
import logging
from datetime import datetime, timezone

import bcrypt
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

MONGODB_URI = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"
AUTH_DB = "clinix_agent"
DOCTORS_DB = "medical_data_tunisia"
DEFAULT_PASSWORD = "doctor123"

DEMO_DOCTOR_IDS = [
    "doc-001",
    "doc-002",
    "doc-003",
    "doc-004",
    "doc-005",
    "doc-006",
]

DEMO_STUBS: dict[str, dict] = {
    "doc-001": {"name": "Dr. Sarah Mitchell",  "specialty": "Cardiologist"},
    "doc-002": {"name": "Dr. Ahmed Bensalem",  "specialty": "Neurologist"},
    "doc-003": {"name": "Dr. Leila Trabelsi",  "specialty": "Dermatologist"},
    "doc-004": {"name": "Dr. Omar Khelifa",    "specialty": "Pediatrician"},
    "doc-005": {"name": "Dr. Fatma Ezzahra",   "specialty": "Ophthalmologist"},
    "doc-006": {"name": "Dr. Karim Mansouri",  "specialty": "Orthopedist"},
}

# doc-XXX -> medical_data_tunisia.doctors._id (ObjectId, as string).
# Each target has a seeded availability template in disponibility.disponibilites.
DEMO_DOCTOR_ID_MAP: dict[str, str] = {
    "doc-001": "6a0c323c0072c8dec428fcf7",  # Cardiologue
    "doc-002": "6a0c32400072c8dec42900da",  # Généraliste (no Neurologue in dataset)
    "doc-003": "6a0c323c0072c8dec428fd6f",  # Dermatologue
    "doc-004": "6a0c323c0072c8dec428fcbb",  # Pédiatre
    "doc-005": "6a0c323c0072c8dec428fde6",  # Ophtalmologue
    "doc-006": "6a0c323c0072c8dec428fe5e",  # Orthopédiste
}


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def seed() -> None:
    client = AsyncIOMotorClient(MONGODB_URI)
    try:
        auth_db    = client[AUTH_DB]
        doctors_db = client[DOCTORS_DB]

        created = 0
        updated = 0
        skipped = 0

        for doctor_id in DEMO_DOCTOR_IDS:
            email = f"{doctor_id}@clinix.ai"

            real_object_id = ObjectId(DEMO_DOCTOR_ID_MAP[doctor_id])
            doctor_doc = await doctors_db["doctors"].find_one({"_id": real_object_id})
            stub = DEMO_STUBS.get(doctor_id, {})
            name = (doctor_doc or {}).get("name") or stub.get("name") or doctor_id
            mapped_doctor_id = str(real_object_id)

            existing = await auth_db["users"].find_one({"email": email})
            if existing:
                if existing.get("doctor_id") != mapped_doctor_id:
                    await auth_db["users"].update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"doctor_id": mapped_doctor_id, "name": name}},
                    )
                    logger.info(
                        f"UPDATED {email} → doctor_id {existing.get('doctor_id')!r} "
                        f"→ {mapped_doctor_id!r} ({name})"
                    )
                    updated += 1
                else:
                    logger.info(f"SKIP  {email} — already up to date")
                    skipped += 1
                continue

            user_doc = {
                "email": email,
                "password_hash": _hash(DEFAULT_PASSWORD),
                "role": "doctor",
                "name": name,
                "patient_profile_id": None,
                "doctor_id": mapped_doctor_id,
                "created_at": datetime.now(timezone.utc),
                "is_active": True,
            }
            await auth_db["users"].insert_one(user_doc)
            logger.info(f"CREATED {email} → {mapped_doctor_id} ({name})")
            created += 1

        logger.info(f"\nDone. Created: {created}  Updated: {updated}  Skipped: {skipped}")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(seed())
