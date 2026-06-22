"""
B-1 validation — StateWriterNode must clear workflow-scoped Redis keys
when step=="completed", so stale doctor_id/date/time/specialty/intent/
preconsultation/workflow_started_at fields cannot leak into the next turn.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.memory.redis_memory import RedisMemory  # noqa: E402
from graphs.patient.nodes.state_writer_node import StateWriterNode  # noqa: E402
from graphs.patient.services.workflow_cleanup_service import WorkflowCleanupService  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402

SESSION_ID = "validation-b1-session"

SEED_MEMORY = {
    # final step for a completed booking turn
    "step": "completed",
    "intent": "booking",
    "workflow_started_at": 1700000000.0,
    "doctor_id": "doc-123",
    "doctor_name": "Dr Sarah Mitchell",
    "specialty": "cardiologue",
    "date": "2026-06-20",
    "time": "10:00",
    "preconsultation_done": True,
    "recommended_specialty": "cardiologue",
    "appointment_period": "week",
    "selected_appointment_index": 0,
    # fields that must SURVIVE (not workflow-scoped)
    "patient_id": "patient-abc",
    "language": "english",
}


async def main() -> None:
    redis_memory = RedisMemory()
    await redis_memory.clear(SESSION_ID)

    try:
        state = AgentState(
            role="patient",
            message="thanks",
            session_id=SESSION_ID,
            memory=dict(SEED_MEMORY),
        )
        # patient_id left unset on the state object (not memory) so the
        # fire-and-forget MongoDB tasks (steps 2-4) are skipped — this
        # validation targets only the Redis cleanup added in 1b.
        state.patient_id = None

        await StateWriterNode().run(state)

        after = await redis_memory.get(SESSION_ID)

        results = []

        for key in WorkflowCleanupService.TEMPORARY_KEYS:
            if key in SEED_MEMORY:
                ok = key not in after
                results.append((f"cleared: {key}", ok, after.get(key)))

        for key in ("patient_id", "language"):
            ok = after.get(key) == SEED_MEMORY[key]
            results.append((f"preserved: {key}", ok, after.get(key)))

        all_ok = True
        for label, ok, value in results:
            status = "PASS" if ok else "FAIL"
            if not ok:
                all_ok = False
            print(f"{status}: {label} (value={value!r})")

        print()
        print(f"remaining keys in Redis: {sorted(after.keys())}")
        print()
        print("ALL PASS" if all_ok else "SOME FAILED")
        if not all_ok:
            sys.exit(1)
    finally:
        await redis_memory.clear(SESSION_ID)


asyncio.run(main())
