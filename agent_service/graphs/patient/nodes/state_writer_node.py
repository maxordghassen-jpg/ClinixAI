"""
Patient StateWriterNode — turn-end persistence.

  1. Flush state.memory to Redis (existing behaviour, unchanged).
  1b. If step=="completed", clear workflow-scoped Redis keys so stale
      doctor/date/time/specialty/intent/preconsultation fields cannot leak
      into the next turn within the 30-minute workflow-expiry window.
  2. Fire async: MemoryExtractionService → user_memories in MongoDB.
  3. Fire async: MemoryManager.save_workflow_snapshot → workflow_snapshots.
  4. Fire async: MemoryManager.complete_workflow if terminal step reached.

Rules 2-4 are fire-and-forget via asyncio.create_task. Zero latency on the hot path.
"""

import asyncio
from typing import Any

from app.memory.memory_manager import MemoryManager
from app.memory.redis_memory import RedisMemory
from app.services.memory_extraction_service import MemoryExtractionService
from graphs.patient.services.workflow_cleanup_service import WorkflowCleanupService
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


class StateWriterNode:

    def __init__(self):
        self.redis     = RedisMemory()
        self.manager   = MemoryManager()
        self.extractor = MemoryExtractionService()
        self.cleanup   = WorkflowCleanupService()

    async def run(self, state: AgentState) -> AgentState:

        # ── 1. Redis flush ────────────────────────────────────────────────────
        safe_payload = {k: v for k, v in state.memory.items() if _has_meaningful_value(v)}
        if safe_payload:
            try:
                trace("WRITER", state.session_id,
                      f"persisting {len(safe_payload)} field(s): {list(safe_payload.keys())}")
                trace("WRITER", state.session_id,
                      f"step={safe_payload.get('step')!r} | intent={safe_payload.get('intent')!r}")
                await self.redis.update(state.session_id, safe_payload)
                trace("WRITER", state.session_id, "Redis write complete")
            except Exception as exc:
                trace("WRITER", state.session_id, f"Redis ERROR: {exc}")
        else:
            trace("WRITER", state.session_id, "nothing to persist")

        # ── 1b. Workflow-completed cleanup ──────────────────────────────────────
        # step=="completed" is the final persisted step for a finished
        # booking/cancel/reschedule/reminder turn (set once, no further
        # recursion). Wipe the workflow-scoped keys now so stale doctor_id,
        # date, time, specialty, intent, workflow_started_at, etc. cannot be
        # read back as live state on the next turn before the 30-min
        # WorkflowGuardService expiry would otherwise clear them.
        if safe_payload.get("step") == "completed":
            try:
                await self.cleanup.clear_workflow(state.session_id)
                trace("WRITER", state.session_id, "step=completed -> workflow keys cleared")
            except Exception as exc:
                trace("WRITER", state.session_id, f"cleanup ERROR: {exc}")

        # ── 2-4. Async long-term writes (fire and forget) ─────────────────────
        user_id = state.patient_id
        if user_id:
            asyncio.create_task(
                self.extractor.extract_and_store(
                    user_id=user_id,
                    role="patient",
                    message=state.message,
                    response=state.response or "",
                    session_memory=state.memory,
                    profile=state.profile,
                )
            )

            step = state.memory.get("step", "")
            if step:
                asyncio.create_task(
                    self.manager.save_workflow_snapshot(
                        user_id=user_id,
                        role="patient",
                        session_memory=state.memory,
                    )
                )

            if self.manager.is_terminal_step(step):
                asyncio.create_task(self.manager.complete_workflow(user_id))
                trace("WRITER", state.session_id, f"workflow completion queued | step={step!r}")

        return state
