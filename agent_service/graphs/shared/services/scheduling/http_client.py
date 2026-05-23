# Backward-compat stub — SchedulingHTTPClient is superseded by the shared MCP
# clients (AvailabilityClient, AppointmentClient) and is no longer used
# internally.  Kept so any stale import does not cause an ImportError at startup.
#
# New code should import directly from graphs.shared.mcp.
from graphs.shared.mcp.availability_client import AvailabilityClient  # noqa: F401
from graphs.shared.mcp.appointment_client import AppointmentClient    # noqa: F401


class SchedulingHTTPClient:
    """Deprecated.  Use AvailabilityClient / AppointmentClient from graphs.shared.mcp."""

    def __init__(self) -> None:
        self._avail = AvailabilityClient()
        self._appt  = AppointmentClient()

    @property
    def availability_url(self) -> str:
        return self._avail._base

    @property
    def appointment_url(self) -> str:
        return self._appt._base

    async def get_availability(self, path: str, params=None):
        return await self._avail.get(path, params)

    async def get_appointments(self, path: str, params=None):
        return await self._appt.get(path, params)

    async def post_appointments(self, path: str, payload=None):
        return await self._appt.post(path, payload)
