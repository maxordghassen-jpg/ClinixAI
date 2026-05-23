"""
Shared availability engine — used by both patient and doctor graphs.

Provides:
  - get_free_slots()           : fetch available slots for a doctor on a date
  - find_next_available_date() : scan forward to the next date with free slots
"""
from __future__ import annotations

from typing import Any

from graphs.shared.mcp.availability_client import AvailabilityClient
from graphs.shared.scheduling_engine.recurrence_engine import detect_working_weekdays
from graphs.shared.scheduling_engine.next_available_engine import (
    find_next_date,
    SCAN_DAYS,
)
from graphs.shared.trace import trace


class AvailabilityEngine:
    """
    Shared scheduling engine for availability queries.

    Both patient and doctor graphs need to know:
      - which slots are free on a given date
      - what is the next available date for a doctor

    This engine owns that logic once, delegating HTTP to AvailabilityClient
    and scan logic to next_available_engine.
    """

    def __init__(self) -> None:
        self._availability = AvailabilityClient()

    async def get_free_slots(self, doctor_id: str, iso_date: str) -> list[dict[str, Any]]:
        """
        Return free slots for doctor_id on iso_date (YYYY-MM-DD).

        Delegates to availability_service which handles template lookup,
        exception resolution, and appointment cross-check in one call.
        Returns [] on any error.
        """
        try:
            raw = await self._availability.get_free_slots(doctor_id, iso_date)
            return raw if isinstance(raw, list) else []
        except Exception as exc:
            trace("AVAIL_ENGINE", doctor_id, f"get_free_slots ERROR: {exc}")
            return []

    async def find_next_available_date(
        self,
        doctor_id: str,
        scan_days: int = SCAN_DAYS,
    ) -> str | None:
        """
        Scan forward from tomorrow for up to scan_days days and return the
        first ISO date on which doctor_id has at least one free slot.

        Returns None if no available date is found within the window.
        """
        try:
            templates = await self._availability.get(f"/availability/{doctor_id}")
        except Exception as exc:
            trace("AVAIL_ENGINE", doctor_id, f"template fetch ERROR: {exc}")
            return None

        if not isinstance(templates, list) or not templates:
            trace("AVAIL_ENGINE", doctor_id, "no availability template found")
            return None

        working_weekdays = detect_working_weekdays(templates)

        if not working_weekdays:
            trace("AVAIL_ENGINE", doctor_id, "template has no working days")
            return None

        trace(
            "AVAIL_ENGINE", doctor_id,
            f"working weekdays: {sorted(working_weekdays)} | scanning {scan_days} days",
        )

        result = await find_next_date(
            working_weekdays,
            lambda iso: self.get_free_slots(doctor_id, iso),
            scan_days=scan_days,
        )

        if result:
            trace("AVAIL_ENGINE", doctor_id, f"next available: {result}")
        else:
            trace("AVAIL_ENGINE", doctor_id, f"no available date in {scan_days} days")

        return result
