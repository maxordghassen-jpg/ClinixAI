from collections import Counter
from datetime import datetime, time, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logger import get_logger
from app.repositories.appointment_repository import AppointmentRepository, ACTIVE_STATUSES
from app.schemas.appointment_schema import ReservationCreate, ReservationReschedule

logger = get_logger(__name__)


DAY_NAMES = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]


class AppointmentService:
    def __init__(self):
        self.repository = AppointmentRepository()
        self.availability_url = settings.AVAILABILITY_SERVICE_URL.rstrip("/")

    async def create_appointment(self, payload: ReservationCreate) -> dict[str, Any]:
        day = self._day_name(payload.date)
        await self._book_slot(payload.doctor_id, day, payload.time)
        try:
            reservation = await self.repository.create(payload.model_dump())
        except Exception:
            await self._release_slot(payload.doctor_id, day, payload.time)
            raise
        return self._serialize(reservation)

    async def cancel_appointment(self, reservation_id: str) -> dict[str, Any]:
        reservation = await self._get_required(reservation_id)
        updated = await self.repository.update_status(reservation_id, "cancelled")
        await self._release_slot(
            reservation["doctorId"],
            self._day_name(reservation["date"]),
            reservation["time"],
        )
        return self._serialize(updated)

    async def confirm_appointment(self, reservation_id: str) -> dict[str, Any]:
        return self._serialize(await self._update_status(reservation_id, "confirmed"))

    async def reject_appointment(self, reservation_id: str) -> dict[str, Any]:
        reservation = await self._get_required(reservation_id)
        updated = await self.repository.update_status(reservation_id, "rejected")
        await self._release_slot(
            reservation["doctorId"],
            self._day_name(reservation["date"]),
            reservation["time"],
        )
        return self._serialize(updated)

    async def reschedule_appointment(
        self,
        reservation_id: str,
        payload: ReservationReschedule,
    ) -> dict[str, Any]:
        reservation = await self._get_required(reservation_id)
        new_day = self._day_name(payload.date)
        old_day = self._day_name(reservation["date"])

        await self._book_slot(reservation["doctorId"], new_day, payload.time)
        try:
            updated = await self.repository.update_schedule(reservation_id, payload.date, payload.time)
        except Exception:
            await self._release_slot(reservation["doctorId"], new_day, payload.time)
            raise

        await self._release_slot(reservation["doctorId"], old_day, reservation["time"])
        return self._serialize(updated)

    async def view_today_appointments(
        self,
        doctor_id: str,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(datetime.now(timezone.utc))
        return await self._list_range(doctor_id, start, start + timedelta(days=1), status_value)

    async def view_tomorrow_appointments(
        self,
        doctor_id: str,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(datetime.now(timezone.utc)) + timedelta(days=1)
        return await self._list_range(doctor_id, start, start + timedelta(days=1), status_value)

    async def view_week_appointments(
        self,
        doctor_id: str,
        status_value: str | None = None,
        next_week: bool = False,
    ) -> list[dict[str, Any]]:
        today = self._start_of_day(datetime.now(timezone.utc))
        start = today + timedelta(days=7) if next_week else today
        return await self._list_range(doctor_id, start, start + timedelta(days=7), status_value)

    async def view_appointments_by_exact_date(
        self,
        doctor_id: str,
        date_value: datetime,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(date_value)
        return await self._list_range(doctor_id, start, start + timedelta(days=1), status_value)

    async def view_patient_today_appointments(
        self,
        patient_id: str,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(datetime.now(timezone.utc))
        return await self._list_patient_range(patient_id, start, start + timedelta(days=1), status_value)

    async def view_patient_tomorrow_appointments(
        self,
        patient_id: str,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(datetime.now(timezone.utc)) + timedelta(days=1)
        return await self._list_patient_range(patient_id, start, start + timedelta(days=1), status_value)

    async def view_patient_week_appointments(
        self,
        patient_id: str,
        status_value: str | None = None,
        next_week: bool = False,
    ) -> list[dict[str, Any]]:
        today = self._start_of_day(datetime.now(timezone.utc))
        start = today + timedelta(days=7) if next_week else today
        return await self._list_patient_range(patient_id, start, start + timedelta(days=7), status_value)

    async def view_patient_appointments_by_exact_date(
        self,
        patient_id: str,
        date_value: datetime,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        start = self._start_of_day(date_value)
        return await self._list_patient_range(patient_id, start, start + timedelta(days=1), status_value)

    async def _list_range(
        self,
        doctor_id: str,
        start_date: datetime,
        end_date: datetime,
        status_value: str | None,
    ) -> list[dict[str, Any]]:
        logger.info(
            "doctor_appointments_query | doctor=%s | window=[%s, %s) | status=%s",
            doctor_id,
            start_date.date(),
            end_date.date(),
            status_value or "all",
        )
        documents = await self.repository.list_by_date_range(
            doctor_id,
            start_date,
            end_date,
            status_value,
        )
        serialized = [self._serialize(document) for document in documents]
        logger.info(
            "doctor_appointments_result | doctor=%s | total=%d",
            doctor_id,
            len(serialized),
        )
        return serialized

    async def _list_patient_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        status_value: str | None,
    ) -> list[dict[str, Any]]:
        # Effective filter applied by the repository:
        #   None / "active" → ACTIVE_STATUSES only (confirmed + pending)
        #   "all"           → no filter
        #   other           → exact match
        effective_filter = (
            f"active({ACTIVE_STATUSES})" if status_value in (None, "active")
            else status_value or "active(default)"
        )
        logger.info(
            "patient_appointments_query | patient=%s | window=[%s, %s) | filter=%s",
            patient_id,
            start_date.date(),
            end_date.date(),
            effective_filter,
        )

        documents = await self.repository.list_by_patient_date_range(
            patient_id,
            start_date,
            end_date,
            status_value,
        )
        serialized = [self._serialize(document) for document in documents]

        # Status distribution for observability
        dist = dict(Counter(a["status"] for a in serialized))
        logger.info(
            "patient_appointments_result | patient=%s | total=%d | distribution=%s",
            patient_id,
            len(serialized),
            dist,
        )

        return serialized

    async def _update_status(self, reservation_id: str, status_value: str) -> dict[str, Any]:
        document = await self.repository.update_status(reservation_id, status_value)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")
        return document

    async def _get_required(self, reservation_id: str) -> dict[str, Any]:
        reservation = await self.repository.get_by_id(reservation_id)
        if not reservation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")
        return reservation

    async def _book_slot(self, doctor_id: str, day: str, start: str) -> None:
        await self._availability_post("/availability/slots/book", doctor_id, day, start)

    async def _release_slot(self, doctor_id: str, day: str, start: str) -> None:
        await self._availability_post("/availability/slots/release", doctor_id, day, start)

    async def _availability_post(self, path: str, doctor_id: str, day: str, start: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.availability_url}{path}",
                json={"doctor_id": doctor_id, "day": day, "start": start},
            )
        if response.status_code >= 400:
            detail = response.json().get("detail", "availability service error")
            raise HTTPException(status_code=response.status_code, detail=detail)

    def _day_name(self, date_value: datetime) -> str:
        return DAY_NAMES[date_value.weekday()]

    def _start_of_day(self, date_value: datetime) -> datetime:
        return datetime.combine(date_value.date(), time.min, tzinfo=timezone.utc)

    def _serialize(self, document: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id":         str(document["_id"]),
            "doctor_id":  document["doctorId"],
            "patient_id": document["patientId"],
            "date":       document["date"],
            "time":       document["time"],
            "status":     document["status"],
            "created_at": document["createdAt"],
            "updated_at": document["updatedAt"],
        }
        # Pass-through optional relationship fields — absent on legacy records
        for mongo_key, api_key in (
            ("doctorName",  "doctor_name"),
            ("patientName", "patient_name"),
            ("specialty",   "specialty"),
            ("endTime",     "end_time"),
            ("source",      "source"),
            ("notes",       "notes"),
        ):
            value = document.get(mongo_key)
            if value is not None:
                result[api_key] = value
        return result
