from typing import Any

from graphs.shared.mcp.appointment_client import AppointmentClient
from graphs.shared.mcp.availability_client import AvailabilityClient


class ToolCaller:
    def __init__(self) -> None:
        self._appointments = AppointmentClient()
        self._availability = AvailabilityClient()

    # ── Generic transport (path-level) ────────────────────────────────────────

    async def get_appointments(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._appointments.get(path, params)

    async def post_appointments(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._appointments.post(path, payload)

    async def get_availability(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._availability.get(path, params)

    async def post_availability(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._availability.post(path, payload)

    async def delete_availability(self, path: str) -> Any:
        return await self._availability.delete(path)

    # ── Availability exceptions ────────────────────────────────────────────────

    async def post_exception(self, payload: dict[str, Any]) -> Any:
        return await self._availability.post_exception(payload)

    async def get_exceptions(self, doctor_id: str) -> Any:
        return await self._availability.get_exceptions(doctor_id)

    async def delete_exception(self, exception_id: str) -> Any:
        return await self._availability.delete_exception(exception_id)
