from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


ExceptionType = Literal["closure", "vacation", "override"]


class ExceptionRangeSchema(BaseModel):
    """A time range used in override exceptions: {"start": "10:00", "end": "14:00"}."""
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM format") from exc
        return value


class ExceptionCreate(BaseModel):
    doctor_id: str
    date: str           # YYYY-MM-DD — start date (or sole date for single-day exceptions)
    end_date: str | None = None    # YYYY-MM-DD — end date, inclusive (vacations/ranges)
    type: ExceptionType
    reason: str | None = None
    override_ranges: list[ExceptionRangeSchema] = []

    @field_validator("date", "end_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("date must use YYYY-MM-DD format") from exc
        return value


class ExceptionResponse(BaseModel):
    id: str
    doctor_id: str
    date: str
    end_date: str | None
    type: ExceptionType
    reason: str | None
    override_ranges: list[dict]
    created_at: datetime
    updated_at: datetime
