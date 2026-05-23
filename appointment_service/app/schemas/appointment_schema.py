from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ReservationStatus = Literal["pending", "confirmed", "cancelled", "rejected"]


class ReservationCreate(BaseModel):
    doctor_id: str
    patient_id: str
    date: datetime
    time: str = Field(..., examples=["09:30"])
    status: ReservationStatus = "confirmed"

    # Optional relationship fields — populated at booking time when available
    doctor_name: str | None = None
    patient_name: str | None = None
    specialty: str | None = None
    end_time: str | None = None          # derived from time + consultation duration
    source: str | None = "patient_booking"
    notes: str | None = ""

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("end_time must use HH:MM format") from exc
        return value


class ReservationReschedule(BaseModel):
    date: datetime
    time: str
    end_time: str | None = None

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value


class ReservationResponse(BaseModel):
    id: str
    doctor_id: str
    patient_id: str
    date: datetime
    time: str
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime

    # Optional relationship fields — may be absent on legacy records
    doctor_name: str | None = None
    patient_name: str | None = None
    specialty: str | None = None
    end_time: str | None = None
    source: str | None = None
    notes: str | None = None
