from datetime import datetime
from typing import Any

import httpx

from fastapi import HTTPException, status

from app.repositories.availability_repository import (
    AvailabilityRepository,
)
from app.repositories.exception_repository import ExceptionRepository

from app.schemas.availability_schema import (
    AvailabilityCreate,
    AvailabilityUpdate,
)

from app.core.config import settings
from app.core.scheduling import generate_slots_from_ranges, get_consultation_duration


class AvailabilityService:

    def __init__(self):

        self.repository = (
            AvailabilityRepository()
        )
        self.exception_repository = ExceptionRepository()

        self.appointment_url = (
            settings.APPOINTMENT_SERVICE_URL
            .rstrip("/")
        )

    # =====================================
    # CREATE AVAILABILITY
    # =====================================

    async def create_availability(
        self,
        payload: AvailabilityCreate,
    ) -> dict[str, Any]:

        slots = [
            slot.model_dump()
            for slot in payload.slots
        ]

        self._validate_slots(slots)

        existing = await (
            self.repository
            .get_by_doctor_and_day(
                payload.doctor_id,
                payload.day,
            )
        )

        if existing:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="availability already exists for this doctor and day",
            )

        document = await (
            self.repository.create(
                {
                    "doctor_id": payload.doctor_id,
                    "day": payload.day,
                    "slots": slots,
                }
            )
        )

        return self._serialize(document)

    # =====================================
    # UPDATE AVAILABILITY
    # =====================================

    async def update_availability(
        self,
        availability_id: str,
        payload: AvailabilityUpdate,
    ) -> dict[str, Any]:

        slots = [
            slot.model_dump()
            for slot in payload.slots
        ]

        self._validate_slots(slots)

        document = await (
            self.repository.update(
                availability_id,
                slots,
            )
        )

        if not document:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="availability not found",
            )

        return self._serialize(document)

    # =====================================
    # DELETE AVAILABILITY
    # =====================================

    async def delete_availability(
        self,
        availability_id: str,
    ) -> dict[str, bool]:

        deleted = await (
            self.repository.delete(
                availability_id
            )
        )

        if not deleted:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="availability not found",
            )

        return {
            "deleted": True
        }

    # =====================================
    # BLOCK SLOT
    # =====================================

    async def block_slot(
        self,
        doctor_id: str,
        day: str,
        start: str,
    ):

        return await self._set_slot_status(
            doctor_id,
            day,
            start,
            "blocked",
        )

    # =====================================
    # UNBLOCK SLOT
    # =====================================

    async def unblock_slot(
        self,
        doctor_id: str,
        day: str,
        start: str,
    ):

        return await self._set_slot_status(
            doctor_id,
            day,
            start,
            "available",
        )

    # =====================================
    # BOOK SLOT
    # =====================================

    async def book_slot(
        self,
        doctor_id: str,
        day: str,
        start: str,
    ):

        updated = await (
            self.repository.set_slot_status(
                doctor_id,
                day,
                start,
                "booked",
            )
        )

        if not updated:

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="slot is not available",
            )

        return self._serialize(updated)

    # =====================================
    # RELEASE SLOT
    # =====================================

    async def release_slot(
        self,
        doctor_id: str,
        day: str,
        start: str,
    ):

        return await self._set_slot_status(
            doctor_id,
            day,
            start,
            "available",
        )

    # =====================================
    # GET FREE SLOTS
    # =====================================

    async def get_free_slots(
        self,
        doctor_id: str,
        day: str,
        date: str,
    ):

        # -----------------------------
        # Availability document
        # -----------------------------

        document = await (
            self.repository
            .get_by_doctor_and_day(
                doctor_id,
                day,
            )
        )

        # -----------------------------
        # Exception check — runs before template lookup so closures and
        # vacations short-circuit immediately without DB work.
        # Override exceptions replace the normal schedule for this date.
        # -----------------------------

        exception = await self.exception_repository.find_for_date(doctor_id, date)
        if exception:
            exc_type = exception.get("type")
            if exc_type in ("closure", "vacation"):
                return []
            if exc_type == "override":
                override_ranges = exception.get("overrideRanges", [])
                if not override_ranges:
                    return []
                # Derive duration from template document (if it exists)
                duration = 30
                if document:
                    duration = get_consultation_duration(document)
                candidate_slots = generate_slots_from_ranges(override_ranges, duration)
                if not candidate_slots:
                    return []
                # Still cross-check with appointments — fall through to that block
                document = {"slots": []}  # sentinel: no legacy blocked slots to filter

        if not document:
            return []

        # -----------------------------
        # Candidate slots
        # Prefer ranges-based dynamic generation (new format).
        # Fall back to slots array with status != "blocked" (legacy format).
        # This fixes the recurring-schedule bug where book_slot permanently
        # marked template slots as "booked" for all future weeks.
        # -----------------------------

        if exception and exception.get("type") == "override":
            # candidate_slots already built from override_ranges above
            pass
        else:
            ranges = document.get("ranges")
            if ranges:
                duration = get_consultation_duration(document)
                all_slots = generate_slots_from_ranges(ranges, duration)

                blocked_starts = {
                    s["start"]
                    for s in document.get("slots", [])
                    if isinstance(s, dict) and s.get("status") == "blocked"
                }
                candidate_slots = [
                    s for s in all_slots if s["start"] not in blocked_starts
                ]
            else:
                # Legacy: exclude only explicitly blocked slots (not "booked")
                candidate_slots = [
                    slot for slot in document.get("slots", [])
                    if slot.get("status") != "blocked"
                ]

        if not candidate_slots:
            return []

        # -----------------------------
        # Fetch appointments
        # -----------------------------

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:

                response = await client.get(
                    f"{self.appointment_url}/appointments/date/{doctor_id}",
                    params={
                        "date": date
                    },
                )
        except httpx.HTTPError:
            # appointment_service unreachable or timed out — return
            # candidate slots as-is rather than failing the whole request.
            return candidate_slots

        # -----------------------------
        # If appointment service fails,
        # return candidate slots as-is
        # -----------------------------

        if response.status_code != 200:
            return candidate_slots

        try:
            appointments = response.json()
        except ValueError:
            return candidate_slots

        if not isinstance(appointments, list):
            return candidate_slots

        # -----------------------------
        # Booked times
        # -----------------------------

        booked_times = {

            appointment.get("time")

            for appointment in appointments

            if isinstance(appointment, dict)
            and appointment.get("status")
            not in [
                "cancelled",
                "rejected",
            ]
        }

        # -----------------------------
        # Remove booked slots
        # -----------------------------

        return [
            slot for slot in candidate_slots
            if slot["start"] not in booked_times
        ]

    # =====================================
    # GET DOCTOR AVAILABILITY
    # =====================================

    async def get_doctor_availability(
        self,
        doctor_id: str,
    ):

        documents = await (
            self.repository.list_by_doctor(
                doctor_id
            )
        )

        return [
            self._serialize(document)
            for document in documents
        ]

    # =====================================
    # GET DAY AVAILABILITY
    # =====================================

    async def get_day_availability(
        self,
        doctor_id: str,
        day: str,
    ):

        document = await (
            self.repository
            .get_by_doctor_and_day(
                doctor_id,
                day,
            )
        )

        if not document:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="availability not found",
            )

        return self._serialize(document)

    # =====================================
    # INTERNAL SLOT STATUS
    # =====================================

    async def _set_slot_status(
        self,
        doctor_id: str,
        day: str,
        start: str,
        status_value: str,
    ):

        document = await (
            self.repository.set_slot_status(
                doctor_id,
                day,
                start,
                status_value,
            )
        )

        if not document:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="slot not found",
            )

        return self._serialize(document)

    # =====================================
    # VALIDATE SLOTS
    # =====================================

    def _validate_slots(
        self,
        slots: list[dict[str, str]],
    ):

        if not slots:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slots cannot be empty",
            )

        normalized = sorted(
            slots,
            key=lambda slot: slot["start"],
        )

        for index, slot in enumerate(normalized):

            start = self._to_minutes(
                slot["start"]
            )

            end = self._to_minutes(
                slot["end"]
            )

            if start >= end:

                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="slot start must be before slot end",
                )

            if (
                index > 0
                and start < self._to_minutes(
                    normalized[index - 1]["end"]
                )
            ):

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="slots cannot overlap",
                )

    # =====================================
    # TIME TO MINUTES
    # =====================================

    def _to_minutes(
        self,
        value: str,
    ):

        parsed = datetime.strptime(
            value,
            "%H:%M",
        )

        return (
            parsed.hour * 60
            + parsed.minute
        )

    # =====================================
    # SERIALIZE
    # =====================================

    def _serialize(
        self,
        document: dict[str, Any],
    ):

        result: dict[str, Any] = {
            "id":         str(document["_id"]),
            "doctor_id":  document["doctorId"],
            "day":        document["day"],
            "slots":      document.get("slots", []),
            "created_at": document["createdAt"],
            "updated_at": document["updatedAt"],
        }
        if "ranges" in document:
            result["ranges"] = document["ranges"]
        if "consultationDurationMinutes" in document:
            result["consultationDurationMinutes"] = document["consultationDurationMinutes"]
        return result