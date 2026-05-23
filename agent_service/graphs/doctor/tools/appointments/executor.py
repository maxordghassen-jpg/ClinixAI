from typing import Any

from graphs.doctor.mcp.tool_caller import ToolCaller
from graphs.shared.normalizers.date_normalizer import DateNormalizer
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


class AppointmentsExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        action = intent.action if intent else "view_appointments"
        entities = intent.entities if intent else {}

        doctor_id = state.doctor_id or state.memory.get("doctor_id")
        if not doctor_id:
            trace("DOCTOR-APPT", state.session_id, "ERROR: doctor_id is None")
            return {"message": "Doctor identity could not be determined. Please re-authenticate."}

        status = intent.status if intent and intent.status not in (None, "pending") else None
        params = {"status": status} if status else None

        # ── List / view actions ────────────────────────────────────────────────

        if action in {"view_appointments", "view_today_appointments", "daily_schedule"}:
            date_str = DateNormalizer.normalize_safe(entities.get("date"))
            if date_str and action == "daily_schedule":
                query = {"date": f"{date_str}T00:00:00"}
                if status:
                    query["status"] = status
                return await self.tool_caller.get_appointments(
                    f"/appointments/date/{doctor_id}", query
                )
            return await self.tool_caller.get_appointments(
                f"/appointments/today/{doctor_id}", params
            )

        if action == "view_tomorrow_appointments":
            return await self.tool_caller.get_appointments(
                f"/appointments/tomorrow/{doctor_id}", params
            )

        if action in {"view_week_appointments", "weekly_schedule"}:
            return await self.tool_caller.get_appointments(
                f"/appointments/week/{doctor_id}", params
            )

        if action == "view_next_week_appointments":
            return await self.tool_caller.get_appointments(
                f"/appointments/next-week/{doctor_id}", params
            )

        if action == "view_appointments_by_exact_date":
            iso_date = DateNormalizer.normalize_safe(entities.get("date"))
            if not iso_date:
                trace("DOCTOR-APPT", state.session_id,
                      f"view_appointments_by_exact_date: could not normalize date {entities.get('date')!r}")
                return {"message": "Please specify a valid date (e.g. 2026-05-24)."}
            query: dict[str, Any] = {"date": f"{iso_date}T00:00:00"}
            if status:
                query["status"] = status
            return await self.tool_caller.get_appointments(
                f"/appointments/date/{doctor_id}", query
            )

        # ── Single-appointment actions ─────────────────────────────────────────

        reservation_id = state.appointment_id or entities.get("reservation_id")

        if action == "confirm_appointment":
            if not reservation_id:
                return {"message": "Please specify the appointment ID to confirm."}
            return await self.tool_caller.post_appointments(
                f"/appointments/{reservation_id}/confirm"
            )

        if action == "reject_appointment":
            if not reservation_id:
                return {"message": "Please specify the appointment ID to reject."}
            return await self.tool_caller.post_appointments(
                f"/appointments/{reservation_id}/reject"
            )

        if action == "cancel_appointment":
            if not reservation_id:
                return {"message": "Please specify the appointment ID to cancel."}
            return await self.tool_caller.post_appointments(
                f"/appointments/{reservation_id}/cancel"
            )

        if action == "reschedule_appointment":
            if not reservation_id:
                return {"message": "Please specify the appointment ID to reschedule."}
            iso_date = DateNormalizer.normalize_safe(entities.get("date"))
            new_time = entities.get("time")
            if not iso_date or not new_time:
                return {"message": "Please provide both the new date and time for rescheduling."}
            payload = {"date": f"{iso_date}T00:00:00", "time": new_time}
            return await self.tool_caller.post_appointments(
                f"/appointments/{reservation_id}/reschedule", payload
            )

        trace("DOCTOR-APPT", state.session_id, f"unsupported action: {action!r}")
        return {"message": f"Unsupported appointment action: {action}"}
