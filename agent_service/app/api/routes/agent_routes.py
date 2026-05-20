from fastapi import APIRouter
from pydantic import BaseModel

from graphs.doctor.navigation_graph import DoctorGraph
from graphs.patient.navigation_graph import PatientGraph


router = APIRouter(tags=["agents"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    doctor_id: str | None = None
    patient_id: str | None = None
    appointment_id: str | None = None


@router.post("/doctor/chat")
async def doctor_chat(payload: ChatRequest):
    return await DoctorGraph.run(
        message=payload.message,
        doctor_id=payload.doctor_id,
        session_id=payload.session_id,
        appointment_id=payload.appointment_id,
    )


@router.post("/patient/chat")
async def patient_chat(payload: ChatRequest):
    return await PatientGraph.run(
        message=payload.message,
        patient_id=payload.patient_id,
        session_id=payload.session_id,
        doctor_id=payload.doctor_id,
        appointment_id=payload.appointment_id,
    )
