from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import httpx

from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.schemas import AgentState


logger = logging.getLogger(__name__)


DAY_NAMES = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]


class PatientAvailabilityExecutor:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def execute(self, state: AgentState) -> Any:
        intent = state.intent
        entities = intent.entities if intent else {}
        action = intent.action if intent else "view_available_slots"
        doctor_id = state.doctor_id or entities.get("doctor_id")

        if not doctor_id:
            return {"message": "Please specify the doctor first."}

        day = self._resolve_day(action, entities)
        try:
            if action in {"view_available_slots", "view_today_availability", "view_tomorrow_availability"}:
                return await self.tool_caller.get_availability(f"/availability/{doctor_id}/{day}/free-slots")
            return await self.tool_caller.get_availability(f"/availability/{doctor_id}")
        except httpx.HTTPError as exc:
            logger.warning("patient availability request failed: %s", exc)
            return {"message": f"I could not retrieve doctor availability right now. {exc}"}

    def _resolve_day(self, action: str, entities: dict[str, Any]) -> str:
        if entities.get("day"):
            return entities["day"]
        today = datetime.now(timezone.utc)
        if "tomorrow" in action:
            today = today + timedelta(days=1)
        return DAY_NAMES[today.weekday()]
