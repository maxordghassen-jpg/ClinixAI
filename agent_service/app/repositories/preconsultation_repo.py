"""
PreconsultationRepository — MongoDB operations on the preconsultation_data collection.

One document per preconsultation session. Indexed by (patient_id + created_at desc)
so that the latest summary for any patient is a O(log n) lookup.

Schema:
  patient_id          str       — FK to patient_profiles
  session_id          str       — the Redis session that produced this entry
  appointment_id      str|None  — reserved field; link_appointment() not wired in runtime
  chief_complaint     str       — primary reason for consultation
  duration            str       — how long the patient has had the complaint
  severity            int       — 1–10 patient-reported pain/severity scale
  associated_symptoms list[str] — additional symptoms mentioned
  urgency             str       — "low" | "medium" | "high" (computed)
  summary_text        str       — LLM-generated doctor-ready narrative
  created_at          datetime
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

COLLECTION = "preconsultation_data"


class PreconsultationRepository:

    # =========================================================================
    # WRITE — upsert latest preconsultation entry for a session
    # Each session produces at most one document. If the same session submits
    # an update (e.g. severity revised) the document is replaced in-place.
    # =========================================================================

    async def upsert(self, patient_id: str, session_id: str, data: dict[str, Any]) -> str | None:
        db = get_database()
        if db is None:
            return None
        try:
            now = datetime.now(timezone.utc)
            result = await db[COLLECTION].find_one_and_update(
                {"patient_id": patient_id, "session_id": session_id},
                {
                    "$set": {**data, "updated_at": now},
                    "$setOnInsert": {
                        "patient_id": patient_id,
                        "session_id": session_id,
                        "created_at": now,
                    },
                },
                upsert=True,
                return_document=True,
            )
            doc_id = str(result.get("_id", "")) if result else None
            logger.info(f"[PRECONSULT REPO] upserted | patient={patient_id} session={session_id}")
            return doc_id
        except Exception as exc:
            logger.error(f"[PRECONSULT REPO] upsert failed | patient={patient_id} | {exc}")
            return None

    # =========================================================================
    # READ — latest preconsultation entry for a patient
    # Returns the most recently created document, or None if no entry exists.
    # =========================================================================

    async def get_latest(self, patient_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            doc = await db[COLLECTION].find_one(
                {"patient_id": patient_id},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
            return doc
        except Exception as exc:
            logger.error(f"[PRECONSULT REPO] get_latest failed | patient={patient_id} | {exc}")
            return None

    # =========================================================================
    # READ — preconsultation entry by session_id
    # Used by the SymptomCollectionHandler to resume mid-collection.
    # =========================================================================

    async def get_by_session(self, patient_id: str, session_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            return await db[COLLECTION].find_one(
                {"patient_id": patient_id, "session_id": session_id},
                {"_id": 0},
            )
        except Exception as exc:
            logger.error(f"[PRECONSULT REPO] get_by_session failed | session={session_id} | {exc}")
            return None


    # =========================================================================
    # INDEXES — called once at startup
    # =========================================================================

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            col = db[COLLECTION]
            await col.create_index([("patient_id", 1), ("created_at", -1)])
            await col.create_index([("patient_id", 1), ("session_id", 1)], unique=True)
            await col.create_index("appointment_id", sparse=True)
            logger.info("[PRECONSULT REPO] indexes ensured")
        except Exception as exc:
            logger.error(f"[PRECONSULT REPO] create_indexes failed: {exc}")
