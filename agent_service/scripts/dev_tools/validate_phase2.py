"""
Phase 2 validation.

Part 1 (prerequisite for Improvement #2):
    Prove, using the REAL _searching_doctors() ranking logic and REAL
    state.long_term_memories pulled from MongoDB, that preferred_doctor_ids
    contains Dr MHIRI Kais's id (6a0c323c0072c8dec428fcbf) for the patient
    who has doctor_affinity:6a0c323c0072c8dec428fcbf — i.e. the
    "preferred_boost={...}" trace line is non-empty for "I need a
    pediatrician". Only the doctor microservice call (doctor_service.search)
    and availability lookups are mocked; the ranking/grouping/rendering code
    is untouched production code.

Part 2 (Bug #1):
    Reproduce the OBSERVED buggy LLM classification for a doctor-card click
    on "Dr MHIRI Kais" while step=selecting_doctor
    ({"intent": "select_appointment", "selected_appointment_index": 1}) and
    show that the new IntentNode guard + WorkflowNode + _doctor_selected()
    chain resolves it as:

        doctor_results -> select_doctor -> doctor_selected -> awaiting_date

    and NEVER as:

        doctor_results -> select_appointment -> selecting_appointment
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.mongo_client import connect_to_mongo, get_database, close_mongo_connection  # noqa: E402
from app.repositories.memory_repo import MemoryRepository  # noqa: E402

import graphs.shared.nodes.intent_node as intent_node_module  # noqa: E402
from graphs.shared.nodes.intent_node import IntentNode  # noqa: E402
from graphs.patient.nodes.workflow_node import WorkflowNode  # noqa: E402
from graphs.patient.handlers.booking_handler import BookingHandler  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402


MHIRI_ID = "6a0c323c0072c8dec428fcbf"


# ── Fake Groq client (same pattern as validate_b2.py) ───────────────────────

class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, *args, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _mock_llm(extracted: dict) -> None:
    intent_node_module.client = _FakeClient(json.dumps(extracted))


# ── Fake service dependencies for BookingHandler ────────────────────────────

class _FakeRedisMemory:
    async def update(self, session_id, values):
        return {}

    async def delete_keys(self, session_id, keys):
        return None


class _FakeAvailability:
    async def get_free_slots(self, doctor_id, date):
        return [{"start": "09:00"}]

    async def has_availability_schedule(self, doctor_id):
        return True


class _FakeNextAvailable:
    async def find_next_date(self, doctor_id):
        return "2026-06-15"


async def _identity_run(state: AgentState) -> AgentState:
    return state


# ── Part 1: prove preferred_doctor_ids contains Dr MHIRI Kais ───────────────

async def prove_preferred_boost() -> bool:
    print("=" * 70)
    print("PART 1 — Improvement #2 prerequisite: preferred_boost proof")
    print("=" * 70)

    await connect_to_mongo()
    db = get_database()
    if db is None:
        print("FAIL: MongoDB unavailable")
        return False

    aff_key = f"doctor_affinity:{MHIRI_ID}"
    aff = await db["user_memories"].find_one({"key": aff_key})
    if not aff:
        print(f"FAIL: no '{aff_key}' memory found in user_memories")
        await close_mongo_connection()
        return False

    user_id = aff["user_id"]
    print(f"found {aff_key} | user_id={user_id!r} "
          f"confidence={aff.get('confidence')!r} frequency={aff.get('frequency')!r} "
          f"value={aff.get('value')!r}")

    repo = MemoryRepository()
    long_term_memories = await repo.get_ranked_memories(user_id)
    print(f"\nget_ranked_memories({user_id!r}) -> {len(long_term_memories)} memorie(s):")
    for m in long_term_memories:
        print(f"   key={m.get('key')!r} confidence={m.get('confidence')!r} "
              f"value={m.get('value')!r}")

    await close_mongo_connection()

    # "I need a pediatrician" candidates, as the doctor microservice would
    # return them. The real ranking/grouping/rendering code in
    # _searching_doctors() is exercised unmodified below.
    candidates = [
        {
            "id": MHIRI_ID,
            "name": "Cabinet de Pédiatrie Dr MHIRI Kais",
            "address": "Avenue Habib Bourguiba, Tunis",
            "specialty": "pediatrician",
        },
        {
            "id": "ayadi-pediatrician-002",
            "name": "Dr Imène Ayadi",
            "address": "Rue de Marseille, Tunis",
            "specialty": "pediatrician",
        },
    ]

    class _FakeDoctorService:
        async def search(self, query):
            return candidates

    handler = BookingHandler(
        tools=None,
        redis_memory=_FakeRedisMemory(),
        booking_service=None,
        availability_service=_FakeAvailability(),
        next_available=_FakeNextAvailable(),
        doctor_service=_FakeDoctorService(),
        patient_memory=None,
        responses=None,
        run_fn=_identity_run,
    )

    state = AgentState(
        role="patient",
        message="I need a pediatrician",
        session_id="validation-phase2-preferred-boost",
        memory={"specialty": "pediatrician", "language": "english"},
        long_term_memories=long_term_memories,
    )

    print("\n--- _searching_doctors() trace output ---")
    await handler._searching_doctors(state)
    print("--- end trace output ---\n")

    print("doctor_results (order as built by _searching_doctors):")
    for d in state.memory.get("doctor_results", []):
        print(f"   {d}")

    print("\nresponse shown to user:")
    print(state.response)

    # Recompute preferred_doctor_ids exactly as _searching_doctors does, to
    # assert the proof independent of the trace text.
    preferred_doctor_ids: set[str] = set()
    for m in long_term_memories:
        key = m.get("key", "")
        if (key == "last_booked_doctor" or key.startswith("doctor_affinity:")) \
                and m.get("confidence", 0) >= 0.6:
            value = m.get("value")
            if isinstance(value, dict) and value.get("doctor_id"):
                preferred_doctor_ids.add(str(value["doctor_id"]))

    print(f"\npreferred_doctor_ids = {preferred_doctor_ids}")

    ok = MHIRI_ID in preferred_doctor_ids
    if ok:
        print(f"PASS: preferred_doctor_ids contains Dr MHIRI Kais's id ({MHIRI_ID})")
    else:
        print(f"FAIL: preferred_doctor_ids does NOT contain {MHIRI_ID}")
    return ok


# ── Part 2: Bug #1 chain validation ─────────────────────────────────────────

DOCTOR_RESULTS = [
    {
        "id": MHIRI_ID,
        "name": "Cabinet de Pédiatrie Dr MHIRI Kais",
        "address": "Avenue Habib Bourguiba, Tunis",
        "specialty": "pediatrician",
        "has_availability": True,
    },
    {
        "id": "ayadi-pediatrician-002",
        "name": "Dr Imène Ayadi",
        "address": "Rue de Marseille, Tunis",
        "specialty": "pediatrician",
        "has_availability": True,
    },
]


async def validate_bug1() -> bool:
    print()
    print("=" * 70)
    print("PART 2 — Bug #1: doctor-card click must continue booking, "
          "not appointment listing")
    print("=" * 70)
    print("Turn 1 (assumed): 'I need a pediatrician' -> doctor_results shown, "
          "step=selecting_doctor")
    print("Turn 2: user clicks 'Dr MHIRI Kais' "
          "(LLM misclassifies as select_appointment, idx=1)")
    print()

    ok = True

    state = AgentState(
        role="patient",
        message="Dr MHIRI Kais",
        session_id="validation-phase2-bug1",
        memory={
            "step": "selecting_doctor",
            "doctor_results": [dict(d) for d in DOCTOR_RESULTS],
            "patient_id": "patient-validation",
            "language": "english",
            "specialty": "pediatrician",
        },
    )

    # Reproduce the OBSERVED buggy LLM output for this message.
    _mock_llm({
        "intent": "select_appointment",
        "selected_appointment_index": 1,
        "language": "english",
    })

    # ---- IntentNode ----
    await IntentNode().run(state)
    print(f"after IntentNode: intent={state.memory.get('intent')!r} "
          f"selected_doctor_index={state.memory.get('selected_doctor_index')!r} "
          f"selected_appointment_index={state.memory.get('selected_appointment_index')!r} "
          f"step={state.memory.get('step')!r}")

    if state.memory.get("intent") != "select_doctor":
        ok = False
        print(f"FAIL: intent={state.memory.get('intent')!r}, expected 'select_doctor'")
    if state.memory.get("selected_doctor_index") != 1:
        ok = False
        print(f"FAIL: selected_doctor_index={state.memory.get('selected_doctor_index')!r}, expected 1")
    if "selected_appointment_index" in state.memory:
        ok = False
        print(f"FAIL: selected_appointment_index leaked: "
              f"{state.memory['selected_appointment_index']!r}")

    # ---- WorkflowNode ----
    await WorkflowNode().run(state)
    print(f"\nafter WorkflowNode: step={state.memory.get('step')!r}")

    if state.memory.get("step") == "selecting_appointment":
        ok = False
        print("FAIL: routed to selecting_appointment (appointment listing) "
              "-- Bug #1 NOT fixed")
    if state.memory.get("step") != "doctor_selected":
        ok = False
        print(f"FAIL: step={state.memory.get('step')!r}, expected 'doctor_selected'")

    # ---- BookingHandler (step=doctor_selected) ----
    handler = BookingHandler(
        tools=None,
        redis_memory=_FakeRedisMemory(),
        booking_service=None,
        availability_service=_FakeAvailability(),
        next_available=None,
        doctor_service=None,
        patient_memory=None,
        responses=None,
        run_fn=_identity_run,
    )
    await handler.handle(state)
    print(f"\nafter BookingHandler: step={state.memory.get('step')!r} "
          f"doctor_id={state.memory.get('doctor_id')!r} "
          f"doctor_name={state.memory.get('doctor_name')!r}")

    if state.memory.get("doctor_id") != MHIRI_ID:
        ok = False
        print(f"FAIL: doctor_id={state.memory.get('doctor_id')!r}, expected {MHIRI_ID!r}")
    if state.memory.get("doctor_name") != "Cabinet de Pédiatrie Dr MHIRI Kais":
        ok = False
        print(f"FAIL: doctor_name={state.memory.get('doctor_name')!r}")
    if state.memory.get("step") == "selecting_appointment":
        ok = False
        print("FAIL: ended at selecting_appointment (appointment listing) "
              "-- Bug #1 NOT fixed")
    if state.memory.get("step") != "awaiting_date":
        ok = False
        print(f"FAIL: step={state.memory.get('step')!r}, expected 'awaiting_date'")

    print()
    if ok:
        print("PASS: doctor_results -> select_doctor -> doctor_selected -> "
              f"{state.memory.get('step')!r} (never select_appointment -> "
              "selecting_appointment)")
    else:
        print("FAIL: see above")
    return ok


async def main() -> None:
    results = [
        await prove_preferred_boost(),
        await validate_bug1(),
    ]

    print()
    print("ALL PASS" if all(results) else "SOME FAILED")
    if not all(results):
        sys.exit(1)


asyncio.run(main())
