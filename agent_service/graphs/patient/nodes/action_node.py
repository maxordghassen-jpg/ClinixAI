"""
ActionNode — workflow step router.

Delegates every step to the appropriate domain handler.
Contains no business logic itself.

Routing table
─────────────
  BookingHandler     searching_doctors, awaiting_specialty, doctor_selected,
                     ready_to_book, awaiting_date, awaiting_time,
                     awaiting_slot_selection, awaiting_recovery_choice

  AppointmentsHandler fetching_appointments, selecting_appointment,
                     confirming_reschedule, confirming_cancel,
                     awaiting_reschedule_date, awaiting_reschedule_time,
                     ready_to_reschedule, awaiting_reschedule_slot_selection,
                     saving_reminder_preference, ready_to_cancel

  GeoHandler         searching_places, selecting_place
"""
from __future__ import annotations

from app.memory.redis_memory import RedisMemory
from app.services.patient_memory_service import PatientMemoryService
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.services.response_service import ResponseService
from graphs.patient.services.doctor_search_service import DoctorSearchService
from graphs.patient.services.booking_service import BookingService
from graphs.patient.services.availability_service import AvailabilityService
from graphs.patient.services.next_available_service import NextAvailableService
from graphs.patient.services.doctor_name_hydrator import DoctorNameHydrator
from graphs.patient.mcp.tool_caller import ToolCaller

from graphs.patient.handlers.booking_handler import BookingHandler
from graphs.patient.handlers.booking_handler import STEPS as BOOKING_STEPS
from graphs.patient.handlers.appointments_handler import AppointmentsHandler
from graphs.patient.handlers.appointments_handler import STEPS as APPOINTMENT_STEPS
from graphs.patient.handlers.geo_handler import GeoHandler
from graphs.patient.handlers.geo_handler import STEPS as GEO_STEPS


class ActionNode:
    """
    Workflow executor — routes each step to its domain handler.

    All external service calls are guarded inside the handlers.
    MongoDB writes (record_booking, etc.) are dispatched as fire-and-forget
    asyncio tasks inside handlers — they never add latency to the response.

    state.profile (long-term MongoDB data) is read-only. Used for
    personalization hints but never written to state.memory.
    """

    def __init__(self) -> None:
        # ── Service dependencies ──────────────────────────────────────────
        tools            = ToolCaller()
        redis_memory     = RedisMemory()
        booking_service  = BookingService()
        avail_service    = AvailabilityService()
        next_available   = NextAvailableService()
        doctor_service   = DoctorSearchService()
        name_hydrator    = DoctorNameHydrator()
        patient_memory   = PatientMemoryService()
        responses        = ResponseService()

        # ── Domain handlers ───────────────────────────────────────────────
        self._booking = BookingHandler(
            tools=tools,
            redis_memory=redis_memory,
            booking_service=booking_service,
            availability_service=avail_service,
            next_available=next_available,
            doctor_service=doctor_service,
            patient_memory=patient_memory,
            responses=responses,
            run_fn=self.run,
        )
        self._appointments = AppointmentsHandler(
            tools=tools,
            redis_memory=redis_memory,
            availability_service=avail_service,
            next_available=next_available,
            name_hydrator=name_hydrator,
            patient_memory=patient_memory,
            run_fn=self.run,
        )
        self._geo = GeoHandler(
            tools=tools,
            redis_memory=redis_memory,
            responses=responses,
            run_fn=self.run,
        )

    async def run(self, state: AgentState) -> AgentState:
        memory = state.memory
        step = memory.get("step")
        session_id = state.session_id

        trace("ACTION", session_id,
              f"executing step={step!r} | intent={memory.get('intent')!r}")

        if step in BOOKING_STEPS:
            return await self._booking.handle(state)

        if step in APPOINTMENT_STEPS:
            return await self._appointments.handle(state)

        if step in GEO_STEPS:
            return await self._geo.handle(state)

        if memory.get("intent") == "booking":
            return await self._booking.handle_direct_recovery(state)

        trace("ACTION", session_id,
              f"unhandled step={step!r} — default response")
        state.response = "How can I help you today?"
        return state
