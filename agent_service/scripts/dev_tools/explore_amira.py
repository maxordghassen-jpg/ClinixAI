"""
Part C prep — inspect Amira Bouazizi's full profile across collections.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.db import mongo_client  # noqa: E402
from app.db.mongo_client import connect_to_mongo, close_mongo_connection, get_database  # noqa: E402

PATIENT_PROFILE_ID = "76985768-4c45-4307-a258-144e07f4fd1a"
EMAIL = "amira_bouazizi@gmail.com"


def _default(o):
    return str(o)


async def main() -> None:
    await connect_to_mongo()
    db = get_database()
    if db is None:
        print("BLOCKED: MongoDB not connected")
        return

    try:
        user = await db["users"].find_one({"email": EMAIL}, {"_id": 0})
        print("users doc:")
        print(json.dumps(user, indent=2, default=_default))

        profile = await db["patient_profiles"].find_one(
            {"patient_id": PATIENT_PROFILE_ID}, {"_id": 0}
        )
        print("\npatient_profiles doc (by patient_profile_id):")
        print(json.dumps(profile, indent=2, default=_default))

        if profile is None:
            # try matching by email instead
            profile2 = await db["patient_profiles"].find_one(
                {"email": EMAIL}, {"_id": 0}
            )
            print("\npatient_profiles doc (by email):")
            print(json.dumps(profile2, indent=2, default=_default))

        # Other DBs that might hold medical data
        for dbname in ["medical_data_tunisia", "appointment_reservation", "disponibility"]:
            other_db = mongo_client._client[dbname]
            cols = await other_db.list_collection_names()
            print(f"\n[{dbname}] collections: {cols}")

    finally:
        await close_mongo_connection()


asyncio.run(main())
