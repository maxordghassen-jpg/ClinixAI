from typing import Any

from app.memory.redis_memory import RedisMemory
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


def _has_meaningful_value(value: Any) -> bool:
    """
    Returns True only for values that should overwrite what is already in Redis.

    Empty containers, None, and empty strings are skipped so that existing
    Redis fields are never accidentally deleted by an in-flight state that
    simply never touched those fields during the current turn.

    Intentional removal must go through WorkflowCleanupService.delete_keys().
    """
    if value is None:
        return False
    if isinstance(value, str) and value == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True


class StateWriterNode:
    """
    Terminal graph node — the single authoritative Redis persistence point.

    Every upstream node (IntentNode, WorkflowNode, ActionNode) may freely
    mutate state.memory without touching Redis.  This node flushes the final
    in-memory state to Redis exactly once per turn, after all logic has
    completed.

    Merge contract:
    - Only fields with meaningful values are written.
    - Writing is additive / protective: existing Redis fields are preserved
      when the current turn did not produce a new value for them.
    - ContextMerger inside RedisMemory.update() provides the final safety net
      (None / "" in incoming are also ignored there).
    - Intentional field deletion must go through WorkflowCleanupService.
    """

    def __init__(self):
        self.memory = RedisMemory()

    async def run(self, state: AgentState) -> AgentState:
        try:
            safe_payload = {
                key: value
                for key, value in state.memory.items()
                if _has_meaningful_value(value)
            }

            if safe_payload:
                keys_written = list(safe_payload.keys())
                trace("WRITER", state.session_id,
                      f"persisting {len(keys_written)} field(s): {keys_written}")
                trace("WRITER", state.session_id,
                      f"step={safe_payload.get('step')!r} | intent={safe_payload.get('intent')!r} "
                      f"| doctor_id={safe_payload.get('doctor_id')} "
                      f"| date={safe_payload.get('date')!r} | time={safe_payload.get('time')!r}")

                await self.memory.update(
                    state.session_id,
                    safe_payload,
                )

                trace("WRITER", state.session_id, "Redis write complete")
            else:
                trace("WRITER", state.session_id,
                      "nothing to persist — all fields empty")

        except Exception as exc:
            trace("WRITER", state.session_id, f"ERROR: {exc}")

        return state
