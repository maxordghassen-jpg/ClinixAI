from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database.connection import get_database

# Statuses that represent an active (non-terminal) appointment.
# Used as the default filter for patient-facing queries so cancelled
# and rejected appointments are excluded unless explicitly requested.
ACTIVE_STATUSES: list[str] = ["pending", "confirmed"]


class AppointmentRepository:
    collection_name = "reservations"

    def __init__(self):
        self.collection = get_database()[self.collection_name]

    async def create_indexes(self) -> None:
        await self.collection.create_index([("doctorId", 1), ("date", 1), ("time", 1)])
        await self.collection.create_index([("patientId", 1), ("date", 1)])

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        document: dict[str, Any] = {
            "doctorId":  data["doctor_id"],
            "patientId": data["patient_id"],
            "date":      data["date"],
            "time":      data["time"],
            "status":    data["status"],
            "createdAt": now,
            "updatedAt": now,
        }
        # Optional relationship fields — omit if not provided to save space
        for field, key in (
            ("doctor_name",  "doctorName"),
            ("patient_name", "patientName"),
            ("specialty",    "specialty"),
            ("end_time",     "endTime"),
            ("source",       "source"),
            ("notes",        "notes"),
        ):
            value = data.get(field)
            if value is not None:
                document[key] = value

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
        elif status_value == "all":
            pass  # no status filter — caller wants full history
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
        """
        Retrieve patient appointments within a date window.

        status_value semantics (patient-facing retrieval policy):
          None / "active" → confirmed + pending only  (DEFAULT — excludes cancelled/rejected)
          "all"           → no status filter (history / admin use)
          "cancelled"     → cancelled only
          "rejected"      → rejected only
          <any other>     → exact status match
        """
        query: dict[str, Any] = {
            "patientId": patient_id,
            "date": {"$gte": start_date, "$lt": end_date},
        }
        if status_value == "all":
            pass  # no status filter — caller explicitly wants full history
        elif status_value in (None, "active"):
            query["status"] = {"$in": ACTIVE_STATUSES}
        else:
            query["status"] = status_value

        cursor = self.collection.find(query).sort([("date", 1), ("time", 1)])
        return await cursor.to_list(length=None)
