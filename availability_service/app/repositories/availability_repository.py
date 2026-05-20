from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database.connection import get_database


class AvailabilityRepository:
    collection_name = "disponibilites"

    def __init__(self):
        self.collection = get_database()[self.collection_name]

    async def create_indexes(self) -> None:
        await self.collection.create_index(
            [("doctorId", 1), ("day", 1)],
            unique=True,
        )

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document = {
            "doctorId": data["doctor_id"],
            "day": data["day"],
            "slots": [
                {
                    **slot,
                    "status": slot.get("status", "available")
                }
                for slot in data["slots"]
            ],
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def update(self, availability_id: str, slots: list[dict[str, Any]]) -> dict[str, Any] | None:
        await self.collection.update_one(
            {"_id": ObjectId(availability_id)},
            {
                "$set": {
                    "slots": slots,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
        )
        return await self.get_by_id(availability_id)

    async def delete(self, availability_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(availability_id)})
        return result.deleted_count == 1

    async def get_by_id(self, availability_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": ObjectId(availability_id)})

    async def get_by_doctor_and_day(self, doctor_id: str, day: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"doctorId": doctor_id, "day": day})

    async def list_by_doctor(self, doctor_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"doctorId": doctor_id}).sort("day", 1)
        return await cursor.to_list(length=None)

    async def set_slot_status(
        self,
        doctor_id: str,
        day: str,
        start: str,
        status: str,
        required_status: str | None = None,
    ) -> dict[str, Any] | None:
        slot_filter: dict[str, str] = {"start": start}
        if required_status:
            slot_filter["status"] = required_status

        result = await self.collection.update_one(
            {
                "doctorId": doctor_id,
                "day": day,
                "slots": {
                    "$elemMatch": slot_filter
                    if not required_status
                    else {
                        "start": start,
                        "$or": [
                            {"status": required_status},
                            {"status": {"$exists": False}},
                            {"status": None},
                        ],
                    }
                },
            },
            {
                "$set": {
                    "slots.$.status": status,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
        )
        if result.modified_count != 1:
            return None
        return await self.get_by_doctor_and_day(doctor_id, day)
