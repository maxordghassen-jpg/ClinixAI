from typing import Any, Literal

from pydantic import BaseModel


AppointmentAction = Literal[
    "view_appointments",
    "view_today_appointments",
    "view_tomorrow_appointments",
    "view_week_appointments",
    "view_next_week_appointments",
    "view_appointments_by_exact_date",
    "confirm_appointment",
    "reject_appointment",
    "cancel_appointment",
]


class AppointmentToolInput(BaseModel):
    action: AppointmentAction
    doctor_id: str | None = None
    reservation_id: str | None = None
    status: str | None = None
    entities: dict[str, Any] = {}
