from datetime import datetime

from fastapi import APIRouter, Query

from app.schemas.appointment_schema import (
    ReservationCreate,
    ReservationReschedule,
    ReservationResponse,
)
from app.services.appointment_service import AppointmentService


router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=ReservationResponse)
async def create_appointment(payload: ReservationCreate):
    return await AppointmentService().create_appointment(payload)


@router.get("/today/{doctor_id}", response_model=list[ReservationResponse])
async def view_today_appointments(doctor_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_today_appointments(doctor_id, status)


@router.get("/tomorrow/{doctor_id}", response_model=list[ReservationResponse])
async def view_tomorrow_appointments(doctor_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_tomorrow_appointments(doctor_id, status)


@router.get("/week/{doctor_id}", response_model=list[ReservationResponse])
async def view_week_appointments(doctor_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_week_appointments(doctor_id, status)


@router.get("/next-week/{doctor_id}", response_model=list[ReservationResponse])
async def view_next_week_appointments(doctor_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_week_appointments(doctor_id, status, next_week=True)


@router.get("/date/{doctor_id}", response_model=list[ReservationResponse])
async def view_appointments_by_exact_date(
    doctor_id: str,
    date: datetime,
    status: str | None = Query(default=None),
):
    return await AppointmentService().view_appointments_by_exact_date(doctor_id, date, status)


@router.get("/patient/today/{patient_id}", response_model=list[ReservationResponse])
async def view_patient_today_appointments(patient_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_patient_today_appointments(patient_id, status)


@router.get("/patient/tomorrow/{patient_id}", response_model=list[ReservationResponse])
async def view_patient_tomorrow_appointments(patient_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_patient_tomorrow_appointments(patient_id, status)


@router.get("/patient/week/{patient_id}", response_model=list[ReservationResponse])
async def view_patient_week_appointments(patient_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_patient_week_appointments(patient_id, status)


@router.get("/patient/next-week/{patient_id}", response_model=list[ReservationResponse])
async def view_patient_next_week_appointments(patient_id: str, status: str | None = Query(default=None)):
    return await AppointmentService().view_patient_week_appointments(patient_id, status, next_week=True)


@router.get("/patient/date/{patient_id}", response_model=list[ReservationResponse])
async def view_patient_appointments_by_exact_date(
    patient_id: str,
    date: datetime,
    status: str | None = Query(default=None),
):
    return await AppointmentService().view_patient_appointments_by_exact_date(patient_id, date, status)


@router.post("/{reservation_id}/confirm", response_model=ReservationResponse)
async def confirm_appointment(reservation_id: str):
    return await AppointmentService().confirm_appointment(reservation_id)


@router.post("/{reservation_id}/reject", response_model=ReservationResponse)
async def reject_appointment(reservation_id: str):
    return await AppointmentService().reject_appointment(reservation_id)


@router.post("/{reservation_id}/cancel", response_model=ReservationResponse)
async def cancel_appointment(reservation_id: str):
    return await AppointmentService().cancel_appointment(reservation_id)


@router.post("/{reservation_id}/reschedule", response_model=ReservationResponse)
async def reschedule_appointment(reservation_id: str, payload: ReservationReschedule):
    return await AppointmentService().reschedule_appointment(reservation_id, payload)
