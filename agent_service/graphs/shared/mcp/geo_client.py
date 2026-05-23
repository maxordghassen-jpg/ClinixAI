"""
Geo service client.

Single source of truth for all HTTP calls to geo_service (medical
facility search, doctor lookup, specialties).
Used by the patient graph only — doctors do not do geo searches.
"""
from __future__ import annotations

from typing import Any

from app.config.settings import settings
from graphs.shared.mcp.base_client import BaseClient


class GeoClient:
    """All geo_service HTTP operations."""

    def __init__(self) -> None:
        self._http = BaseClient()
        self._base = settings.GEO_SERVICE_URL.rstrip("/")

    # ── Place search ──────────────────────────────────────────────────────────

    async def search_places(self, query: str) -> Any:
        """Text-based medical facility search."""
        return await self._http.post(self._base, "/api/search/manual", {"query": query})

    async def search_nearby_places(self, payload: dict[str, Any]) -> Any:
        """Location-based nearby facility search."""
        return await self._http.post(self._base, "/api/nearby", payload)

    # ── Doctor lookup ─────────────────────────────────────────────────────────

    async def lookup_doctors_by_ids(self, doctor_ids: list[str]) -> Any:
        """Batch resolve doctor names from a list of IDs."""
        return await self._http.post(self._base, "/api/doctors/lookup", {"ids": doctor_ids})

    # ── Reference data ────────────────────────────────────────────────────────

    async def get_specialties(self) -> Any:
        """Return the list of available medical specialties."""
        return await self._http.get(self._base, "/api/specialties")
