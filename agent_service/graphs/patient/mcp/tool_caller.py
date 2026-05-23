from typing import Any

from graphs.shared.mcp.appointment_client import AppointmentClient
from graphs.shared.mcp.availability_client import AvailabilityClient
from graphs.shared.mcp.geo_client import GeoClient


class ToolCaller:

    def __init__(self) -> None:
        self._appointments = AppointmentClient()
        self._availability = AvailabilityClient()
        self._geo = GeoClient()

    # ── Generic transport (path-level) ────────────────────────────────────────

    async def get_appointments(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._appointments.get(path, params)

    async def post_appointments(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._appointments.post(path, payload)

    async def get_availability(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._availability.get(path, params)

    async def post_availability(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        return await self._availability.post(path, payload)

    # ── Free slots ────────────────────────────────────────────────────────────

    async def get_free_slots(self, doctor_id: str, date: str) -> Any:
        return await self._availability.get_free_slots(doctor_id, date)

    # ── Appointment lifecycle ─────────────────────────────────────────────────

    async def create_appointment(self, payload: dict) -> Any:
        return await self._appointments.create_appointment(payload)

    async def get_patient_appointments_today(self, patient_id: str) -> Any:
        return await self._appointments.get_patient_appointments_today(patient_id)

    async def get_patient_appointments_week(self, patient_id: str) -> Any:
        return await self._appointments.get_patient_appointments_week(patient_id)

    async def get_patient_appointments_next_week(self, patient_id: str) -> Any:
        return await self._appointments.get_patient_appointments_next_week(patient_id)

    async def cancel_patient_appointment(self, appointment_id: str) -> Any:
        return await self._appointments.cancel_appointment(appointment_id)

    async def reschedule_appointment(self, appointment_id: str, payload: dict[str, Any]) -> Any:
        return await self._appointments.reschedule_appointment(appointment_id, payload)

    # ── Geo search ────────────────────────────────────────────────────────────

    async def search_nearby_places(self, payload: dict[str, Any]) -> Any:
        return await self._geo.search_nearby_places(payload)

    async def search_places(self, query: str) -> Any:
        return await self._geo.search_places(query)

    async def lookup_doctors_by_ids(self, doctor_ids: list[str]) -> Any:
        return await self._geo.lookup_doctors_by_ids(doctor_ids)

    async def get_specialties(self) -> Any:
        return await self._geo.get_specialties()
