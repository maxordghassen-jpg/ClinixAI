"""
PreconsultationReportRepository — MongoDB operations on preconsultation_reports.

Schema (one document per appointment):
  appointment_id           str   — FK to reservations collection
  doctor_id                str   — FK to doctor record
  patient_id               str   — FK to patient_profiles
  patient_snapshot         dict  — frozen profile copy at booking time
  preconsultation_snapshot dict  — frozen preconsultation data
  ai_summary               str   — LLM-generated clinical narrative
  created_at               datetime
  generated_by             str   — "clinixai"

Immutable after creation: no update methods are provided.
Reports are doctor-read-only; patients cannot modify them.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

COLLECTION = "preconsultation_reports"


class PreconsultationReportRepository:

    async def create(self, report: dict[str, Any]) -> str | None:
        db = get_database()
        if db is None:
            return None
        try:
            result = await db[COLLECTION].insert_one(report)
            doc_id = str(result.inserted_id)
            logger.info(
                "[REPORT REPO] created | appt=%s patient=%s id=%s",
                report.get("appointment_id"), report.get("patient_id"), doc_id,
            )
            return doc_id
        except Exception as exc:
            logger.error("[REPORT REPO] create failed | %s", exc)
            return None

    async def get_by_appointment(self, appointment_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            return await db[COLLECTION].find_one(
                {"appointment_id": appointment_id}, {"_id": 0}
            )
        except Exception as exc:
            logger.error(
                "[REPORT REPO] get_by_appointment failed | appt=%s | %s",
                appointment_id, exc,
            )
            return None

    async def get_by_patient(
        self, patient_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        db = get_database()
        if db is None:
            return []
        try:
            cursor = db[COLLECTION].find(
                {"patient_id": patient_id},
                {"_id": 0},
            ).sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.error(
                "[REPORT REPO] get_by_patient failed | patient=%s | %s",
                patient_id, exc,
            )
            return []

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            col = db[COLLECTION]
            await col.create_index("appointment_id", unique=True)
            await col.create_index([("patient_id", 1), ("created_at", -1)])
            await col.create_index("doctor_id")
            logger.info("[REPORT REPO] indexes ensured")
        except Exception as exc:
            logger.error("[REPORT REPO] create_indexes failed: %s", exc)
