"""
ReportHandler — serves pre-consultation reports in the doctor chat.

Resolution order for "open a report for <name>":
  1. patient_name  → patient_id   (regex search on patient_profiles.name, falling
                                    back to clinix_agent.users.name when absent —
                                    same canonical source used by the doctor
                                    appointments service for patient_id → name)
  2. patient_id    → latest report (preconsultation_reports sorted by created_at desc)

Also supports direct lookup by appointment_id when the doctor provides one.
"""

import logging
from typing import Any

from app.db.mongo_client import get_database
from app.repositories.preconsultation_report_repo import PreconsultationReportRepository
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)

_report_repo = PreconsultationReportRepository()


class ReportHandler:

    async def handle(self, state: AgentState) -> Any:
        intent   = state.intent
        action   = (intent.action if intent else None) or "open_report"
        entities = intent.entities if intent else {}

        if action == "open_report":
            # ── Path 1: direct appointment_id lookup ─────────────────────────
            appointment_id = (
                entities.get("appointment_id")
                or state.appointment_id
            )
            if appointment_id:
                return await self._by_appointment(appointment_id, state)

            # ── Path 2: patient name → patient_id → latest report ────────────
            patient_name = (
                entities.get("patient_name")
                or state.memory.get("last_patient_name")
            )
            if patient_name:
                return await self._by_patient_name(patient_name, state)

            return {
                "message": (
                    "Please specify a patient name or appointment ID to open a report.\n"
                    'Example: "open the report for Amira Bouazizi"'
                )
            }

        return {"message": f"Unsupported report action: {action}"}

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _by_appointment(self, appointment_id: str, state: AgentState) -> Any:
        trace("DOCTOR-REPORT", state.session_id,
              f"lookup by appointment_id={appointment_id!r}")
        report = await _report_repo.get_by_appointment(appointment_id)
        if not report:
            return {
                "message": (
                    f"No pre-consultation report found for appointment {appointment_id}."
                )
            }
        return {"report": report}

    async def _by_patient_name(self, patient_name: str, state: AgentState) -> Any:
        trace("DOCTOR-REPORT", state.session_id,
              f"lookup by patient_name={patient_name!r}")

        # Step 1: patient_name → patient_id  (case-insensitive partial match)
        db = get_database()
        if db is None:
            logger.error("[REPORT HANDLER] MongoDB unavailable")
            return {"message": "Database unavailable. Please try again."}

        patient_id: str | None = None
        display_name = patient_name

        profile = await db["patient_profiles"].find_one(
            {"name": {"$regex": patient_name, "$options": "i"}},
            {"_id": 0, "patient_id": 1, "name": 1},
        )
        if profile:
            patient_id   = profile["patient_id"]
            display_name = profile["name"]
        else:
            # patient_profiles documents often have no "name" field. Fall back
            # to clinix_agent.users — the same canonical source the doctor
            # appointments service uses to resolve patient_id -> name.
            user = await db["users"].find_one(
                {"name": {"$regex": patient_name, "$options": "i"}, "role": "patient"},
                {"_id": 0, "patient_profile_id": 1, "name": 1},
            )
            if user and user.get("patient_profile_id"):
                patient_id   = user["patient_profile_id"]
                display_name = user["name"]

        if not patient_id:
            logger.info("[DOCTOR-REPORT] resolved patient_name=%r patient_id=None", patient_name)
            return {"message": f"No patient named '{patient_name}' found in records."}

        logger.info("[DOCTOR-REPORT] resolved patient_name=%r patient_id=%r", patient_name, patient_id)
        trace("DOCTOR-REPORT", state.session_id,
              f"resolved patient_name={patient_name!r} patient_id={patient_id!r}")

        # Step 2: patient_id → latest report
        # get_by_patient returns docs sorted by created_at desc; first = latest appointment
        reports = await _report_repo.get_by_patient(patient_id, limit=1)
        if not reports:
            return {
                "message": (
                    f"No pre-consultation report found for {display_name}.\n"
                    "A report is generated automatically when the patient books "
                    "via the AI assistant."
                )
            }

        return {"report": reports[0]}
