from datetime import datetime, timezone
from typing import Any

from graphs.doctor.mcp.tool_caller import ToolCaller
from graphs.shared.schemas import AgentState


class AppointmentsExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        doctor_id = state.doctor_id or state.memory.get("doctor_id")
        action = intent.action if intent else "view_appointments"
        status = None
        
        if intent and intent.status not in [None, "pending"]:
            status = intent.status
        params = {"status": status} if status else None

        if action in {"view_appointments", "view_today_appointments"}:
            return await self.tool_caller.get_appointments(f"/appointments/today/{doctor_id}", params)
        if action == "view_tomorrow_appointments":
            return await self.tool_caller.get_appointments(f"/appointments/tomorrow/{doctor_id}", params)
        if action == "view_week_appointments":
            return await self.tool_caller.get_appointments(f"/appointments/week/{doctor_id}", params)
        if action == "view_next_week_appointments":
            return await self.tool_caller.get_appointments(f"/appointments/next-week/{doctor_id}", params)
        if action == "view_appointments_by_exact_date":
            date_value = intent.entities.get("date") or datetime.now(timezone.utc).isoformat()
            query = {
                "date": f"{date_value}T00:00:00"
            }
            if status:
                query["status"] = status
            return await self.tool_caller.get_appointments(f"/appointments/date/{doctor_id}", query)

        reservation_id = state.appointment_id or intent.entities.get("reservation_id")
        if action == "confirm_appointment":
            return await self.tool_caller.post_appointments(f"/appointments/{reservation_id}/confirm")
        if action == "reject_appointment":
            return await self.tool_caller.post_appointments(f"/appointments/{reservation_id}/reject")
        if action == "cancel_appointment":
            return await self.tool_caller.post_appointments(f"/appointments/{reservation_id}/cancel")
        return {"message": f"unsupported appointment action: {action}"}
