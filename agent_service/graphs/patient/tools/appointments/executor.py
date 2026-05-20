from datetime import datetime, timezone
import logging
from typing import Any

import httpx

from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.schemas import AgentState


logger = logging.getLogger(__name__)


class PatientAppointmentsExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        action = intent.action if intent else "view_today_appointments"
        entities = intent.entities if intent else {}
        doctor_id = state.doctor_id or entities.get("doctor_id")
        patient_id = state.patient_id or entities.get("patient_id")
        reservation_id = state.appointment_id or entities.get("reservation_id")

        try:
            if action == "book_appointment":
                return await self.tool_caller.post_appointments(
                    "/appointments",
                    {
                        "doctor_id": doctor_id,
                        "patient_id": patient_id,
                        "date": entities.get("date"),
                        "time": entities.get("time"),
                        "status": "confirmed",
                    },
                )
            if action == "cancel_appointment":
                if not reservation_id:
                    return {"message": "Please specify which appointment to cancel."}
                return await self.tool_caller.post_appointments(f"/appointments/{reservation_id}/cancel")
            if action == "reschedule_appointment":
                if not reservation_id:
                    return {"message": "Please specify which appointment to reschedule."}
                return await self.tool_caller.post_appointments(
                    f"/appointments/{reservation_id}/reschedule",
                    {"date": entities.get("date"), "time": entities.get("time")},
                )
            if action == "view_tomorrow_appointments":
                return await self.tool_caller.get_appointments(f"/appointments/patient/tomorrow/{patient_id}")
            if action == "view_week_appointments":
                return await self.tool_caller.get_appointments(f"/appointments/patient/week/{patient_id}")
            if action == "view_next_week_appointments":
                return await self.tool_caller.get_appointments(f"/appointments/patient/next-week/{patient_id}")
            if action == "view_appointments_by_exact_date":
                date_value = entities.get("date") or datetime.now(timezone.utc).isoformat()
                return await self.tool_caller.get_appointments(
                    f"/appointments/patient/date/{patient_id}",
                    {"date": date_value},
                )
            return await self.tool_caller.get_appointments(f"/appointments/patient/today/{patient_id}")
        except httpx.HTTPError as exc:
            logger.warning("patient appointment request failed: %s", exc)
            return {"message": f"I could not complete the appointment request right now. {exc}"}
