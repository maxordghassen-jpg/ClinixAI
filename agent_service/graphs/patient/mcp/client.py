from typing import Any

import httpx

from app.config.settings import settings


class MCPClient:
    def __init__(self):
        self.appointment_service_url = settings.APPOINTMENT_SERVICE_URL.rstrip("/")
        self.availability_service_url = settings.AVAILABILITY_SERVICE_URL.rstrip("/")
        self.geo_service_url = settings.GEO_SERVICE_URL.rstrip("/")

    async def get(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{base_url}{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def post(self, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{base_url}{path}", json=payload or {})
        response.raise_for_status()
        return response.json()

    async def delete(self, base_url: str, path: str) -> Any:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.delete(f"{base_url}{path}")
        response.raise_for_status()
        return response.json()
