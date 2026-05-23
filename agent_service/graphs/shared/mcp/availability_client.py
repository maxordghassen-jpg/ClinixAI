"""
Availability service client.

Single source of truth for all HTTP calls to availability_service.
Used by both patient and doctor graphs.
"""
from __future__ import annotations

from typing import Any

from app.config.settings import settings
from graphs.shared.mcp.base_client import BaseClient


class AvailabilityClient:
    """
    All availability_service HTTP operations in one place.

    Covers:
    - Weekly template reads / writes (availability CRUD)
    - Free-slot queries
    - Availability exceptions (vacation / closure / override)
    """

    def __init__(self) -> None:
        self._http = BaseClient()
        self._base = settings.AVAILABILITY_SERVICE_URL.rstrip("/")

    # ── Generic transport ─────────────────────────────────────────────────────

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._http.get(self._base, path, params)

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._http.post(self._base, path, payload)

    async def delete(self, path: str) -> Any:
        return await self._http.delete(self._base, path)

    # ── Free slot queries ─────────────────────────────────────────────────────

    async def get_free_slots(self, doctor_id: str, date: str) -> Any:
        """Return free slots for doctor_id on date (YYYY-MM-DD)."""
        return await self.get(f"/availability/{doctor_id}/{date}/free-slots")

    # ── Availability exceptions ───────────────────────────────────────────────

    async def post_exception(self, payload: dict[str, Any]) -> Any:
        return await self.post("/exceptions", payload)

    async def get_exceptions(self, doctor_id: str) -> Any:
        return await self.get(f"/exceptions/{doctor_id}")

    async def delete_exception(self, exception_id: str) -> Any:
        return await self.delete(f"/exceptions/{exception_id}")
