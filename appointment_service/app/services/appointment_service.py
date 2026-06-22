from collections import Counter
from datetime import datetime, time, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.logger import get_logger
from app.database.connection import get_client
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
        serialized = await self._enrich_appointments(serialized)
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
        serialized = await self._enrich_appointments(serialized)

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

    async def _enrich_appointments(
        self,
        appointments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Resolve missing patient_name, doctor_name, specialty from profile databases.

        AI-booked appointments are stored with only doctor_id and patient_id.
        This method batch-fetches the human-readable names so the UI can display
        them instead of raw IDs.
        """
        mongo = get_client()
        if not mongo or not appointments:
            return appointments

        missing_patient_ids = {
            a["patient_id"]
            for a in appointments
            if not a.get("patient_name") and a.get("patient_id")
        }
        missing_doctor_ids = {
            a["doctor_id"]
            for a in appointments
            if (not a.get("doctor_name") or not a.get("specialty")) and a.get("doctor_id")
        }

        patient_map: dict[str, str] = {}
        if missing_patient_ids:
            cursor = mongo["clinix_agent"]["patient_profiles"].find(
                {"patient_id": {"$in": list(missing_patient_ids)}},
                {"patient_id": 1, "name": 1, "_id": 0},
            )
            async for doc in cursor:
                if doc.get("name"):
                    patient_map[doc["patient_id"]] = doc["name"]

            # patient_profiles documents often have no "name" field. Fall back
            # to clinix_agent.users, which links patient_profile_id -> name.
            unresolved_ids = [pid for pid in missing_patient_ids if pid not in patient_map]
            if unresolved_ids:
                cursor = mongo["clinix_agent"]["users"].find(
                    {"patient_profile_id": {"$in": unresolved_ids}, "role": "patient"},
                    {"patient_profile_id": 1, "name": 1, "_id": 0},
                )
                async for doc in cursor:
                    if doc.get("name") and doc.get("patient_profile_id"):
                        patient_map[doc["patient_profile_id"]] = doc["name"]

        # doctor_id in the appointment is the MongoDB _id of the doctor document
        # (stored as a 24-char hex string). clinix_agent.users has a doctor_id
        # string field that matches, providing the clean display name.
        # Specialty comes from medical_data_tunisia.doctors via ObjectId _id lookup.
        doctor_map: dict[str, dict[str, str]] = {}
        if missing_doctor_ids:
            from bson import ObjectId

            # Pass 1: name from clinix_agent.users (doctor_id string field)
            cursor = mongo["clinix_agent"]["users"].find(
                {"doctor_id": {"$in": list(missing_doctor_ids)}, "role": "doctor"},
                {"doctor_id": 1, "name": 1, "_id": 0},
            )
            async for doc in cursor:
                if doc.get("doctor_id"):
                    doctor_map[doc["doctor_id"]] = {
                        "name":      doc.get("name", ""),
                        "specialty": "",
                    }

            # Pass 2: specialty from medical_data_tunisia.doctors (_id ObjectId)
            valid_oids = []
            for did in missing_doctor_ids:
                try:
                    valid_oids.append(ObjectId(did))
                except Exception:
                    pass
            if valid_oids:
                cursor = mongo["medical_data_tunisia"]["doctors"].find(
                    {"_id": {"$in": valid_oids}},
                    {"specialty": 1},
                )
                async for doc in cursor:
                    did = str(doc["_id"])
                    specialty = doc.get("specialty", "")
                    if did in doctor_map:
                        doctor_map[did]["specialty"] = specialty
                    else:
                        doctor_map[did] = {"name": "", "specialty": specialty}

        for apt in appointments:
            if not apt.get("patient_name"):
                pid = apt.get("patient_id", "")
                resolved_name = patient_map.get(pid) or pid
                apt["patient_name"] = resolved_name
                logger.info("[DOCTOR-APPT] patient_id=%r resolved_name=%r", pid, resolved_name)

            if apt.get("doctor_id") in doctor_map:
                info = doctor_map[apt["doctor_id"]]
                if not apt.get("doctor_name") and info["name"]:
                    apt["doctor_name"] = info["name"]
                if not apt.get("specialty") and info["specialty"]:
                    apt["specialty"] = info["specialty"]

        logger.info(
            "enrich_appointments | resolved_patients=%d/%d resolved_doctors=%d/%d",
            len(patient_map),
            len(missing_patient_ids),
            len(doctor_map),
            len(missing_doctor_ids),
        )
        return appointments

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
