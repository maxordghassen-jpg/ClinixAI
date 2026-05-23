"""
Backward-compatible wrapper — delegates to the shared AvailabilityEngine.

Existing callers (ActionNode) continue to work unchanged.
New code should import AvailabilityEngine from graphs.shared.services.scheduling.
"""
from graphs.shared.services.scheduling.availability_engine import AvailabilityEngine as _Engine

SCAN_DAYS = 14  # kept for any code that reads NextAvailableService.SCAN_DAYS


class NextAvailableService:
    """Find the next calendar date on which a doctor has free slots."""

    SCAN_DAYS = SCAN_DAYS

    def __init__(self) -> None:
        self._engine = _Engine()

    async def find_next_date(self, doctor_id: str) -> str | None:
        return await self._engine.find_next_available_date(doctor_id)
