from typing import Any, Literal

from pydantic import BaseModel


AvailabilityAction = Literal[
    "view_available_slots",
    "view_today_availability",
    "view_tomorrow_availability",
    "view_week_availability",
    "view_next_week_availability",
    "view_availability",
    "create_availability",
    "update_availability",
    "block_availability",
    "unblock_availability",
    "delete_availability",
]


class AvailabilityToolInput(BaseModel):
    action: AvailabilityAction
    doctor_id: str | None = None
    availability_id: str | None = None
    day: str | None = None
    start: str | None = None
    slots: list[dict[str, Any]] | None = None
