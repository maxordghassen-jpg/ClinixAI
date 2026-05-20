from datetime import datetime

from pydantic import BaseModel, Field

from app.models.slot_model import SlotModel


class AvailabilityModel(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    doctor_id: str = Field(alias="doctorId")
    day: str
    slots: list[SlotModel]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
