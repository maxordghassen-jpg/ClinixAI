from datetime import datetime

from pydantic import BaseModel, Field


class AppointmentModel(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    doctor_id: str = Field(alias="doctorId")
    patient_id: str = Field(alias="patientId")
    date: datetime
    time: str
    status: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
