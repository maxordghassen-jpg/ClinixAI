from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.repositories.availability_repository import AvailabilityRepository
from app.schemas.availability_schema import AvailabilityCreate, AvailabilityUpdate


class AvailabilityService:
    def __init__(self):
        self.repository = AvailabilityRepository()

    async def create_availability(self, payload: AvailabilityCreate) -> dict[str, Any]:
        slots = [slot.model_dump() for slot in payload.slots]
        self._validate_slots(slots)

        existing = await self.repository.get_by_doctor_and_day(payload.doctor_id, payload.day)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="availability already exists for this doctor and day",
            )

        return self._serialize(
            await self.repository.create(
                {
                    "doctor_id": payload.doctor_id,
                    "day": payload.day,
                    "slots": slots,
                }
            )
        )

    async def update_availability(
        self,
        availability_id: str,
        payload: AvailabilityUpdate,
    ) -> dict[str, Any]:
        slots = [slot.model_dump() for slot in payload.slots]
        self._validate_slots(slots)

        document = await self.repository.update(availability_id, slots)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="availability not found")
        return self._serialize(document)

    async def delete_availability(self, availability_id: str) -> dict[str, bool]:
        deleted = await self.repository.delete(availability_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="availability not found")
        return {"deleted": True}

    async def block_slot(self, doctor_id: str, day: str, start: str) -> dict[str, Any]:
        return await self._set_slot_status(doctor_id, day, start, "blocked")

    async def unblock_slot(self, doctor_id: str, day: str, start: str) -> dict[str, Any]:
        return await self._set_slot_status(doctor_id, day, start, "available")

    async def book_slot(self, doctor_id: str, day: str, start: str) -> dict[str, Any]:
        updated = await self.repository.set_slot_status(
            doctor_id,
            day,
            start,
            "booked",
        )
        if not updated:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slot is not available")
        return self._serialize(updated)

    async def release_slot(self, doctor_id: str, day: str, start: str) -> dict[str, Any]:
        return await self._set_slot_status(doctor_id, day, start, "available")

    async def get_free_slots(self, doctor_id: str, day: str) -> list[dict[str, str]]:
        document = await self.repository.get_by_doctor_and_day(doctor_id, day)
        if not document:
            return []
        return [
            slot
            for slot in document["slots"]
            if slot.get("status", "available") == "available"
        ]

    async def get_doctor_availability(self, doctor_id: str) -> list[dict[str, Any]]:
        documents = await self.repository.list_by_doctor(doctor_id)
        return [self._serialize(document) for document in documents]

    async def get_day_availability(self, doctor_id: str, day: str) -> dict[str, Any]:
        document = await self.repository.get_by_doctor_and_day(doctor_id, day)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="availability not found")
        return self._serialize(document)

    async def _set_slot_status(
        self,
        doctor_id: str,
        day: str,
        start: str,
        status_value: str,
    ) -> dict[str, Any]:
        document = await self.repository.set_slot_status(doctor_id, day, start, status_value)
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="slot not found")
        return self._serialize(document)

    def _validate_slots(self, slots: list[dict[str, str]]) -> None:
        if not slots:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slots cannot be empty")

        normalized = sorted(slots, key=lambda slot: slot["start"])
        for index, slot in enumerate(normalized):
            start = self._to_minutes(slot["start"])
            end = self._to_minutes(slot["end"])
            if start >= end:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="slot start must be before slot end",
                )
            if index > 0 and start < self._to_minutes(normalized[index - 1]["end"]):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="slots cannot overlap",
                )

    def _to_minutes(self, value: str) -> int:
        parsed = datetime.strptime(value, "%H:%M")
        return parsed.hour * 60 + parsed.minute

    def _serialize(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(document["_id"]),
            "doctor_id": document["doctorId"],
            "day": document["day"],
            "slots": document["slots"],
            "created_at": document["createdAt"],
            "updated_at": document["updatedAt"],
        }
