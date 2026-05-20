from datetime import datetime, timedelta, timezone
from typing import Any

from graphs.doctor.mcp.tool_caller import ToolCaller
from graphs.shared.schemas import AgentState


DAY_NAMES = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]


class AvailabilityExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        doctor_id = state.doctor_id or state.memory.get("doctor_id")
        action = intent.action if intent else "view_availability"
        day = self._resolve_day(action, intent.entities if intent else {})

        if action in {"view_available_slots", "view_today_availability", "view_tomorrow_availability"}:
            return await self.tool_caller.get_availability(f"/availability/{doctor_id}/{day}/free-slots")
        if action in {"view_availability", "view_week_availability", "view_next_week_availability"}:
            return await self.tool_caller.get_availability(f"/availability/{doctor_id}")
        if action == "create_availability":
            return await self.tool_caller.post_availability(
                "/availability",
                {
                    "doctor_id": doctor_id,
                    "day": day,
                    "slots": intent.entities.get("slots", []),
                },
            )
        if action == "update_availability":
            return await self.tool_caller.post_availability(
                f"/availability/{intent.entities.get('availability_id')}",
                {"slots": intent.entities.get("slots", [])},
            )
        if action in {"block_availability", "unblock_availability"}:
            endpoint = "block" if action == "block_availability" else "unblock"
            return await self.tool_caller.post_availability(
                f"/availability/slots/{endpoint}",
                {
                    "doctor_id": doctor_id,
                    "day": day,
                    "start": intent.entities.get("time") or intent.entities.get("start"),
                },
            )
        if action == "delete_availability":
            return await self.tool_caller.delete_availability(
                f"/availability/{intent.entities.get('availability_id')}"
            )
        return {"message": f"unsupported availability action: {action}"}

    def _resolve_day(self, action: str, entities: dict[str, Any]) -> str:
        if entities.get("day"):
            return entities["day"]
        today = datetime.now(timezone.utc)
        if "tomorrow" in action:
            today = today + timedelta(days=1)
        return DAY_NAMES[today.weekday()]
