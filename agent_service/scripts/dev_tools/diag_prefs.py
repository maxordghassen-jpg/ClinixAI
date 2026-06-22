import asyncio, json
from motor.motor_asyncio import AsyncIOMotorClient

PATIENT_ID = "76985768-4c45-4307-a258-144e07f4fd1a"
MONGO_URI  = "mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/"

async def run():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["clinix_agent"]

    # 1. patient_profiles.preferred_doctors
    profile = await db["patient_profiles"].find_one(
        {"patient_id": PATIENT_ID},
        {"_id": 0, "patient_id": 1, "preferred_doctors": 1, "preferred_specialties": 1}
    )
    print("=== patient_profiles entry ===")
    print(json.dumps(profile, default=str, indent=2))

    # 2. All user_memories for this patient
    entries = await db["user_memories"].find(
        {"user_id": PATIENT_ID},
        {"_id": 0, "key": 1, "value": 1, "confidence": 1, "frequency": 1, "updated_at": 1}
    ).to_list(length=100)
    print()
    print(f"=== user_memories: {len(entries)} total entries ===")
    for e in entries:
        print(json.dumps(e, default=str))

    # 3. doctor_affinity entries
    affinity = [e for e in entries if e.get("key","").startswith("doctor_affinity:")]
    print()
    print(f"=== doctor_affinity entries: {len(affinity)} ===")
    for e in affinity:
        print(json.dumps(e, default=str))

    # 4. last_booked_doctor entries
    last_booked = [e for e in entries if e.get("key") == "last_booked_doctor"]
    print()
    print(f"=== last_booked_doctor entries: {len(last_booked)} ===")
    for e in last_booked:
        print(json.dumps(e, default=str))

    client.close()

asyncio.run(run())
