from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database.connection import get_database


class ExceptionRepository:
    collection_name = "availability_exceptions"

    def __init__(self):
        self.collection = get_database()[self.collection_name]

    async def create_indexes(self) -> None:
        # Primary lookup: find exceptions covering a specific date for a doctor
        await self.collection.create_index(
            [("doctorId", 1), ("date", 1)],
            background=True,
            name="idx_doctorId_date",
        )
        # List all exceptions for a doctor
        await self.collection.create_index(
            [("doctorId", 1)],
            background=True,
            name="idx_doctorId",
        )

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document: dict[str, Any] = {
            "doctorId":       data["doctor_id"],
            "date":           data["date"],
            "endDate":        data.get("end_date"),
            "type":           data["type"],
            "reason":         data.get("reason"),
            "overrideRanges": data.get("override_ranges", []),
            "createdAt":      now,
            "updatedAt":      now,
        }
        result = await self.collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def find_for_date(self, doctor_id: str, date: str) -> dict[str, Any] | None:
        """
        Return the first exception that covers `date` for `doctor_id`.

        An exception covers `date` when:
          exception.date <= date  AND  (exception.endDate >= date OR exception.endDate is null)

        ISO date strings compare lexicographically, which is equivalent to
        chronological order — no date parsing needed for $lte/$gte.
        """
        return await self.collection.find_one({
            "doctorId": doctor_id,
            "date": {"$lte": date},
            "$or": [
                {"endDate": {"$gte": date}},
                {"endDate": None},
            ],
        })

    async def list_by_doctor(self, doctor_id: str) -> list[dict[str, Any]]:
        cursor = self.collection.find({"doctorId": doctor_id}).sort("date", 1)
        return await cursor.to_list(length=None)

    async def delete(self, exception_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(exception_id)})
        return result.deleted_count > 0

    async def delete_by_doctor_date(self, doctor_id: str, date: str) -> int:
        result = await self.collection.delete_many({"doctorId": doctor_id, "date": date})
        return result.deleted_count
