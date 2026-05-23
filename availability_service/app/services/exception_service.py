from typing import Any

from fastapi import HTTPException, status

from app.repositories.exception_repository import ExceptionRepository
from app.schemas.exception_schema import ExceptionCreate


class ExceptionService:

    def __init__(self):
        self.repository = ExceptionRepository()

    async def create_exception(self, payload: ExceptionCreate) -> dict[str, Any]:
        data = payload.model_dump()
        data["override_ranges"] = [r.model_dump() for r in payload.override_ranges]
        document = await self.repository.create(data)
        return self._serialize(document)

    async def list_doctor_exceptions(self, doctor_id: str) -> list[dict[str, Any]]:
        documents = await self.repository.list_by_doctor(doctor_id)
        return [self._serialize(d) for d in documents]

    async def delete_exception(self, exception_id: str) -> dict[str, bool]:
        deleted = await self.repository.delete(exception_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="exception not found",
            )
        return {"deleted": True}

    def _serialize(self, document: dict[str, Any]) -> dict[str, Any]:
        return {
            "id":               str(document["_id"]),
            "doctor_id":        document["doctorId"],
            "date":             document["date"],
            "end_date":         document.get("endDate"),
            "type":             document["type"],
            "reason":           document.get("reason"),
            "override_ranges":  document.get("overrideRanges", []),
            "created_at":       document["createdAt"],
            "updated_at":       document["updatedAt"],
        }
