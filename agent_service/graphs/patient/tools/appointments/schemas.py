from typing import Any, Literal

from pydantic import BaseModel


PatientAppointmentAction = Literal[
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
    "view_today_appointments",
    "view_tomorrow_appointments",
    "view_week_appointments",
    "view_appointments_by_exact_date",
]


class PatientAppointmentToolInput(BaseModel):
    action: PatientAppointmentAction
    doctor_id: str | None = None
    patient_id: str | None = None
    reservation_id: str | None = None
    entities: dict[str, Any] = {}
