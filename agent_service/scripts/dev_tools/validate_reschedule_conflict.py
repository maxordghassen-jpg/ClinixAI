"""
Reschedule double-booking validation (Diff 2 — MODE 2 pre-validation in
_awaiting_reschedule_time, agent_service/graphs/patient/handlers/appointments_handler.py).

Scenario:
    An appointment for Dr MHIRI Kais already exists on 2026-06-15 at 11:00.
    A second appointment is being rescheduled to 2026-06-15 11:00 (same
    doctor, same date, same time).

The fake AvailabilityService.get_free_slots() reproduces what the real
availability_service returns in this situation: 11:00 is EXCLUDED from
the free-slot list because the existing appointment already occupies it
for that date (see availability_service/app/services/availability_service.py
get_free_slots(): booked_times filter).

Expected (per Diff 2):
    * the requested slot (11:00) is rejected before _ready_to_reschedule runs
    * step -> awaiting_reschedule_slot_selection, with alternative slots offered
    * new_time is cleared (not persisted)
    * tools.reschedule_appointment() is NEVER called -> no duplicate
      appointment is created at 2026-06-15 11:00
"""
import asyncio
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from graphs.patient.handlers.appointments_handler import AppointmentsHandler  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402


MHIRI_ID = "6a0c323c0072c8dec428fcbf"

# Free slots for Dr MHIRI Kais on 2026-06-15, AFTER the existing 11:00
# appointment has been excluded by availability_service.get_free_slots().
FREE_SLOTS_2026_06_15 = [
    {"start": "09:00", "end": "09:30"},
    {"start": "10:00", "end": "10:30"},
    {"start": "14:00", "end": "14:30"},
    {"start": "15:00", "end": "15:30"},
]


class _FakeRedisMemory:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def update(self, session_id, values):
        return {}

    async def delete_keys(self, session_id, keys):
        self.deleted.extend(keys)


class _FakeAvailability:
    def __init__(self, free_slots: list[dict]) -> None:
        self._free_slots = free_slots
        self.calls: list[tuple[str, str]] = []

    async def get_free_slots(self, doctor_id, date):
        self.calls.append((doctor_id, date))
        return self._free_slots


class _FakeTools:
    def __init__(self) -> None:
        self.reschedule_calls: list[tuple[str, dict]] = []

    async def reschedule_appointment(self, appointment_id, payload):
        # If this is ever called in this scenario, a duplicate appointment
        # would be created at the conflicting date/time.
        self.reschedule_calls.append((appointment_id, payload))
        return {"status": "ok"}


async def _identity_run(state: AgentState) -> AgentState:
    return state


async def main() -> None:
    redis_memory = _FakeRedisMemory()
    availability = _FakeAvailability(FREE_SLOTS_2026_06_15)
    tools = _FakeTools()

    handler = AppointmentsHandler(
        tools=tools,
        redis_memory=redis_memory,
        availability_service=availability,
        next_available=None,
        name_hydrator=None,
        patient_memory=None,
        run_fn=_identity_run,
    )

    state = AgentState(
        role="patient",
        message="11am",
        session_id="validation-reschedule-conflict",
        memory={
            "step": "awaiting_reschedule_time",
            "language": "english",
            "selected_appointment_id": "appt-OTHER-002",
            "selected_appointment_doctor_id": MHIRI_ID,
            "selected_appointment_doctor": "Cabinet de Pediatrie Dr MHIRI Kais",
            "new_date": "2026-06-15",
            "new_time": "11am",
        },
    )

    print("Existing appointment: Dr MHIRI Kais @ 2026-06-15 11:00 (occupies the 11:00 slot)")
    print("Reschedule request:   another appointment -> 2026-06-15 11:00")
    print()

    await handler.handle(state)

    print(f"get_free_slots calls: {availability.calls}")
    print(f"resulting step:       {state.memory.get('step')!r}")
    print(f"new_time in memory:   {'new_time' in state.memory}")
    print(f"suggested_slots:      {[s.get('start') for s in state.memory.get('suggested_slots', [])]}")
    print(f"redis delete_keys:    {redis_memory.deleted}")
    print(f"reschedule_appointment calls: {tools.reschedule_calls}")
    print()
    print("response shown to user:")
    print(state.response)
    print()

    ok = True

    if "11:00" in [s.get("start") for s in state.memory.get("suggested_slots", [])]:
        ok = False
        print("FAIL: conflicting slot 11:00 was offered as an alternative")

    if state.memory.get("step") != "awaiting_reschedule_slot_selection":
        ok = False
        print(f"FAIL: step={state.memory.get('step')!r}, expected 'awaiting_reschedule_slot_selection'")

    if "new_time" in state.memory:
        ok = False
        print(f"FAIL: new_time not cleared: {state.memory.get('new_time')!r}")

    if not state.memory.get("suggested_slots"):
        ok = False
        print("FAIL: no alternative slots offered")

    if tools.reschedule_calls:
        ok = False
        print(f"FAIL: reschedule_appointment() was called -> duplicate booking: {tools.reschedule_calls!r}")

    if state.response is None or "9:00 AM" not in state.response:
        ok = False
        print("FAIL: response does not list alternative slots")

    print()
    if ok:
        print("PASS: 2026-06-15 11:00 rejected, alternatives offered, "
              "no duplicate appointment created")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
