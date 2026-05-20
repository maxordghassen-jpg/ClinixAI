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

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value


class ReservationReschedule(BaseModel):
    date: datetime
    time: str

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
