from typing import Any

from graphs.patient.mcp.client import MCPClient


class ToolCaller:
    def __init__(self):
        self.client = MCPClient()

    async def get_appointments(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.client.get(self.client.appointment_service_url, path, params)

    async def post_appointments(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self.client.post(self.client.appointment_service_url, path, payload)

    async def get_availability(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self.client.get(self.client.availability_service_url, path, params)

    async def post_availability(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self.client.post(self.client.availability_service_url, path, payload)

    async def search_nearby_places(self, payload: dict[str, Any]) -> Any:
        return await self.client.post(self.client.geo_service_url, "/api/nearby", payload)

    async def search_places(self, payload: dict[str, Any]) -> Any:
        return await self.client.post(self.client.geo_service_url, "/api/search/manual", payload)

    async def get_specialties(self) -> Any:
        return await self.client.get(self.client.geo_service_url, "/api/specialties")
