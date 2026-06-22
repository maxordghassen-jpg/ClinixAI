"""
Inspect the canonical UUID patient_profiles document.
Prints the complete document and shows which database/collection it came from.

Run from auth_service/ directory:
    python scripts/inspect_uuid_doc.py
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings
from motor.motor_asyncio import AsyncIOMotorClient

CANONICAL_UUID = "76985768-4c45-4307-a258-144e07f4fd1a"
SLUG_ID        = "patient-amira-bouazizi"
COLLECTION     = "patient_profiles"


def _coerce(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, dict):
        return {k2: _coerce(v2) for k2, v2 in v.items()}
    if isinstance(v, list):
        return [_coerce(i) for i in v]
    return v


def _serialize(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            out[k] = str(v)
        else:
            out[k] = _coerce(v)
    return out


async def main() -> None:
    uri = settings.MONGODB_URI
    db_name = settings.MONGO_DB_NAME

    masked = uri
    if "@" in uri:
        prefix = uri.split("://")[0]
        host   = uri.split("@")[-1]
        masked = f"{prefix}://****:****@{host}"

    print(f"\n{'='*60}")
    print(f"  Connection string : {masked}")
    print(f"  Database          : {db_name}")
    print(f"  Collection        : {COLLECTION}")
    print(f"{'='*60}\n")

    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    db = client[db_name]
    col = db[COLLECTION]

    # ── UUID canonical document ───────────────────────────────────────────────
    uuid_doc = await col.find_one({"patient_id": CANONICAL_UUID})
    print(f"--- find_one({{\"patient_id\": \"{CANONICAL_UUID}\"}}) ---")
    if uuid_doc:
        print(json.dumps(_serialize(uuid_doc), ensure_ascii=False, indent=2))
    else:
        print("  !! NOT FOUND — document does not exist in this database !!")

    # ── Slug document (for comparison) ────────────────────────────────────────
    print(f"\n--- find_one({{\"patient_id\": \"{SLUG_ID}\"}}) ---")
    slug_doc = await col.find_one({"patient_id": SLUG_ID})
    if slug_doc:
        slug_out = _serialize(slug_doc)
        # Suppress large arrays for readability
        for f in ("appointment_history",):
            if f in slug_out and isinstance(slug_out[f], list):
                slug_out[f] = f"[{len(slug_doc[f])} items — suppressed]"
        print(json.dumps(slug_out, ensure_ascii=False, indent=2))
    else:
        print("  (slug document does not exist)")

    # ── All docs that have the target email ───────────────────────────────────
    print("\n--- All documents with email 'amira_bouazizi@gmail.com' ---")
    cursor = col.find({"email": "amira_bouazizi@gmail.com"}, {"_id": 0, "patient_id": 1, "name": 1, "email": 1, "phone": 1, "gender": 1, "blood_type": 1})
    docs = await cursor.to_list(length=20)
    for d in docs:
        print(f"  patient_id={d.get('patient_id')!r:50s}  name={d.get('name')!r}  phone={d.get('phone')!r}")
    if not docs:
        print("  (none found)")

    # ── users record ─────────────────────────────────────────────────────────
    print("\n--- users.find_one({email: 'amira_bouazizi@gmail.com'}) ---")
    users_col = db["users"]
    user = await users_col.find_one(
        {"email": "amira_bouazizi@gmail.com"},
        {"_id": 0, "email": 1, "patient_profile_id": 1, "name": 1, "role": 1},
    )
    if user:
        print(json.dumps(user, ensure_ascii=False, indent=2))
    else:
        print("  (user not found)")

    client.close()
    print()


if __name__ == "__main__":
    asyncio.run(main())
