"""
Shared appointment engine — used by both patient and doctor graphs.

Provides:
  - get_doctor_appointments_for_date() : fetch doctor's appointments on a date
  - check_conflict()                   : verify a slot is not already booked
  - create_appointment()               : create a reservation
  - cancel_appointment()               : cancel by ID
  - reschedule_appointment()           : reschedule by ID

All methods return None / False / [] on error rather than raising, so callers
can decide how to handle failures.
"""
from __future__ import annotations

from typing import Any

from graphs.shared.mcp.appointment_client import AppointmentClient
from graphs.shared.trace import trace


class AppointmentEngine:
    """Shared appointment operations used by both patient and doctor graphs."""

    def __init__(self) -> None:
        self._appointments = AppointmentClient()

    async def get_doctor_appointments_for_date(
        self,
        doctor_id: str,
        iso_date: str,
    ) -> list[dict[str, Any]]:
        """
        Return active (non-cancelled/non-rejected) appointments for doctor_id
        on iso_date (YYYY-MM-DD).
        """
        try:
            raw = await self._appointments.get_doctor_appointments_for_date(doctor_id, iso_date)
            if not isinstance(raw, list):
                return []
            return [
                a for a in raw
                if a.get("status") not in ("cancelled", "rejected")
            ]
        except Exception as exc:
            trace("APPT_ENGINE", doctor_id, f"get_appointments ERROR: {exc}")
            return []

    async def check_conflict(
        self,
        doctor_id: str,
        iso_date: str,
        time: str,
    ) -> bool:
        """
        Return True if doctor_id already has an active appointment at time on
        iso_date.  Returns False on any error (fail-open).
        """
        appointments = await self.get_doctor_appointments_for_date(doctor_id, iso_date)
        return any(a.get("time") == time for a in appointments)

    async def create_appointment(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        """POST /appointments.  Returns the created appointment or None on error."""
        try:
            return await self._appointments.create_appointment(payload)
        except Exception as exc:
            trace("APPT_ENGINE", "create", f"create_appointment ERROR: {exc}")
            return None

    async def cancel_appointment(self, appointment_id: str) -> dict[str, Any] | None:
        try:
            return await self._appointments.cancel_appointment(appointment_id)
        except Exception as exc:
            trace("APPT_ENGINE", appointment_id, f"cancel ERROR: {exc}")
            return None

    async def reschedule_appointment(
        self,
        appointment_id: str,
        iso_date: str,
        time: str,
    ) -> dict[str, Any] | None:
        try:
            return await self._appointments.reschedule_appointment(
                appointment_id,
                {"date": f"{iso_date}T00:00:00", "time": time},
            )
        except Exception as exc:
            trace("APPT_ENGINE", appointment_id, f"reschedule ERROR: {exc}")
            return None
