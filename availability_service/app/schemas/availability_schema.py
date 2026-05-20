from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


Day = Literal[
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]

SlotStatus = Literal["available", "booked", "blocked"]


class SlotSchema(BaseModel):
    start: str = Field(..., examples=["09:00"])
    end: str = Field(..., examples=["09:30"])
    status: SlotStatus | None = None

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value


class AvailabilityCreate(BaseModel):
    doctor_id: str
    day: Day
    slots: list[SlotSchema]


class AvailabilityUpdate(BaseModel):
    slots: list[SlotSchema]


class SlotStatusUpdate(BaseModel):
    doctor_id: str
    day: Day
    start: str

    @field_validator("start")
    @classmethod
    def validate_start(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value


class AvailabilityResponse(BaseModel):
    id: str
    doctor_id: str
    day: Day
    slots: list[SlotSchema]
    created_at: datetime
    updated_at: datetime
