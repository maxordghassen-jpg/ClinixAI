from typing import Literal

from pydantic import BaseModel


PatientAvailabilityAction = Literal[
    "view_available_slots",
    "view_today_availability",
    "view_tomorrow_availability",
    "view_week_availability",
    "view_availability",
]


class PatientAvailabilityToolInput(BaseModel):
    action: PatientAvailabilityAction
    doctor_id: str | None = None
    day: str | None = None
