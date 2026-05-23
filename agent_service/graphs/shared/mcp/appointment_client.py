"""
Appointment service client.

Single source of truth for all HTTP calls to appointment_service.
Used by both patient and doctor graphs.
"""
from __future__ import annotations

from typing import Any

from app.config.settings import settings
from graphs.shared.mcp.base_client import BaseClient


class AppointmentClient:
    """
    All appointment_service HTTP operations in one place.

    Generic methods (get / post) accept arbitrary paths so callers can
    issue any request.  Named convenience methods encode the known
    endpoint patterns for type-safe, discoverable call sites.
    """

    def __init__(self) -> None:
        self._http = BaseClient()
        self._base = settings.APPOINTMENT_SERVICE_URL.rstrip("/")

    # ── Generic transport ─────────────────────────────────────────────────────

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._http.get(self._base, path, params)

    async def post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._http.post(self._base, path, payload)

    # ── Patient appointment queries ───────────────────────────────────────────

    async def get_patient_appointments_today(self, patient_id: str) -> Any:
        return await self.get(f"/appointments/patient/today/{patient_id}")

    async def get_patient_appointments_week(self, patient_id: str) -> Any:
        return await self.get(f"/appointments/patient/week/{patient_id}")

    async def get_patient_appointments_next_week(self, patient_id: str) -> Any:
        return await self.get(f"/appointments/patient/next-week/{patient_id}")

    # ── Doctor appointment queries ────────────────────────────────────────────

    async def get_doctor_appointments_for_date(
        self,
        doctor_id: str,
        iso_date: str,
    ) -> Any:
        return await self.get(
            f"/appointments/date/{doctor_id}",
            params={"date": f"{iso_date}T00:00:00"},
        )

    # ── Booking lifecycle ─────────────────────────────────────────────────────

    async def create_appointment(self, payload: dict[str, Any]) -> Any:
        return await self.post("/appointments", payload)

    async def cancel_appointment(self, appointment_id: str) -> Any:
        return await self.post(f"/appointments/{appointment_id}/cancel")

    async def reschedule_appointment(
        self,
        appointment_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return await self.post(f"/appointments/{appointment_id}/reschedule", payload)
