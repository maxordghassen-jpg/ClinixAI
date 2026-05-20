from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database.connection import get_database


class AppointmentRepository:
    collection_name = "reservations"

    def __init__(self):
        self.collection = get_database()[self.collection_name]

    async def create_indexes(self) -> None:
        await self.collection.create_index([("doctorId", 1), ("date", 1), ("time", 1)])
        await self.collection.create_index([("patientId", 1), ("date", 1)])

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document = {
            "doctorId": data["doctor_id"],
            "patientId": data["patient_id"],
            "date": data["date"],
            "time": data["time"],
            "status": data["status"],
            "createdAt": now,
            "updatedAt": now,
        }
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def get_by_id(self, reservation_id: str) -> dict[str, Any] | None:
        return await self.collection.find_one({"_id": ObjectId(reservation_id)})

    async def update_status(self, reservation_id: str, status_value: str) -> dict[str, Any] | None:
        await self.collection.update_one(
            {"_id": ObjectId(reservation_id)},
            {
                "$set": {
                    "status": status_value,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
        )
        return await self.get_by_id(reservation_id)

    async def update_schedule(
        self,
        reservation_id: str,
        date: datetime,
        time: str,
    ) -> dict[str, Any] | None:
        await self.collection.update_one(
            {"_id": ObjectId(reservation_id)},
            {
                "$set": {
                    "date": date,
                    "time": time,
                    "updatedAt": datetime.now(timezone.utc),
                }
            },
        )
        return await self.get_by_id(reservation_id)

    async def list_by_date_range(
        self,
        doctor_id: str,
        start_date: datetime,
        end_date: datetime,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "doctorId": doctor_id,
            "date": {"$gte": start_date, "$lt": end_date},
        }
        if status_value == "active":
            query["status"] = {"$in": ["pending", "confirmed"]}
        elif status_value:
            query["status"] = status_value

        cursor = self.collection.find(query).sort([("date", 1), ("time", 1)])
        return await cursor.to_list(length=None)

    async def list_by_patient_date_range(
        self,
        patient_id: str,
        start_date: datetime,
        end_date: datetime,
        status_value: str | None = None,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "patientId": patient_id,
            "date": {"$gte": start_date, "$lt": end_date},
        }
        if status_value == "active":
            query["status"] = {"$in": ["pending", "confirmed"]}
        elif status_value:
            query["status"] = status_value

        cursor = self.collection.find(query).sort([("date", 1), ("time", 1)])
        return await cursor.to_list(length=None)
