"""
ReportGenerationService — creates an immutable preconsultation_reports document
at booking time.

Called fire-and-forget from BookingHandler._ready_to_book immediately after a
successful appointment booking.  Fetches point-in-time snapshots of:

  1. patient_profiles  — identity, vitals, lifestyle, medical history
  2. preconsultation_data — chief complaint, symptoms, urgency, AI summary

The snapshot is frozen at this instant.  Subsequent profile edits or new
preconsultation sessions do NOT affect the stored report.

Graceful degradation:
  - Missing patient profile → empty patient_snapshot, report still saved.
  - Missing preconsultation → empty snapshot, ai_summary = "".
    Doctor sees "No pre-consultation data available."
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo_client import get_database
from app.repositories.preconsultation_repo import PreconsultationRepository
from app.repositories.preconsultation_report_repo import PreconsultationReportRepository

logger = logging.getLogger(__name__)

_preconsult_repo = PreconsultationRepository()
_report_repo     = PreconsultationReportRepository()

_PATIENT_FIELDS = [
    "name", "gender", "date_of_birth", "phone",
    "weight", "height", "blood_type",
    "smoking_status", "alcohol_consumption",
    "allergies", "chronic_conditions", "current_medications",
    "past_surgeries", "family_history",
    "emergency_contact_name", "emergency_contact_phone",
    "emergency_contact_relationship",
]

_PRECONSULT_FIELDS = [
    "chief_complaint", "duration", "severity",
    "associated_symptoms", "urgency",
]

_LIST_FIELDS = frozenset({
    "allergies", "chronic_conditions", "current_medications",
    "past_surgeries", "family_history", "associated_symptoms",
})


def _snapshot(source: dict | None, fields: list[str]) -> dict[str, Any]:
    src = source or {}
    out: dict[str, Any] = {}
    for f in fields:
        val = src.get(f)
        out[f] = [] if (val is None and f in _LIST_FIELDS) else val
    return out


async def generate_preconsultation_report(
    appointment_id: str,
    doctor_id: str,
    patient_id: str,
    session_id: str,
) -> str | None:
    """
    Build and persist an immutable report snapshot.
    Returns the inserted document's string _id, or None on failure.
    Safe to call as asyncio.create_task().
    """
    logger.info(
        "[REPORT SVC] generating | appt=%s patient=%s doctor=%s",
        appointment_id, patient_id, doctor_id,
    )

    # ── 1. Load patient profile ──────────────────────────────────────────────
    patient_profile: dict | None = None
    db = get_database()
    if db is not None:
        try:
            patient_profile = await db["patient_profiles"].find_one(
                {"patient_id": patient_id}, {"_id": 0}
            )
        except Exception as exc:
            logger.warning("[REPORT SVC] patient profile fetch failed (non-fatal): %s", exc)

    # ── 2. Load preconsultation — session-exact first, then latest ───────────
    preconsult: dict | None = None
    try:
        preconsult = await _preconsult_repo.get_by_session(patient_id, session_id)
        if not preconsult:
            preconsult = await _preconsult_repo.get_latest(patient_id)
    except Exception as exc:
        logger.warning("[REPORT SVC] preconsult fetch failed (non-fatal): %s", exc)

    if not preconsult:
        logger.warning(
            "[REPORT SVC] no preconsultation found | patient=%s session=%s — "
            "report saved with empty clinical section",
            patient_id, session_id,
        )

    # ── 3. Build frozen snapshots ────────────────────────────────────────────
    patient_snapshot    = _snapshot(patient_profile, _PATIENT_FIELDS)
    preconsult_snapshot = _snapshot(preconsult,      _PRECONSULT_FIELDS)
    ai_summary          = (preconsult or {}).get("summary_text", "")

    # ── 4. Persist ───────────────────────────────────────────────────────────
    report: dict[str, Any] = {
        "appointment_id":           appointment_id,
        "doctor_id":                doctor_id,
        "patient_id":               patient_id,
        "patient_snapshot":         patient_snapshot,
        "preconsultation_snapshot": preconsult_snapshot,
        "ai_summary":               ai_summary,
        "created_at":               datetime.now(timezone.utc),
        "generated_by":             "clinixai",
    }

    doc_id = await _report_repo.create(report)
    if doc_id:
        logger.info("[REPORT SVC] saved | id=%s appt=%s", doc_id, appointment_id)
    else:
        logger.error(
            "[REPORT SVC] save failed | appt=%s patient=%s", appointment_id, patient_id
        )
    return doc_id
