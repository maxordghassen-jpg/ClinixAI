import logging

from app.memory.redis_memory import RedisMemory
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)

_redis = RedisMemory()


class StateWriterNode:
    async def run(self, state: AgentState) -> AgentState:
        if not state.memory:
            return state
        try:
            await _redis.update(state.session_id, state.memory)
            trace("DOCTOR-WRITE", state.session_id,
                  f"Redis write complete | keys={list(state.memory.keys())}")
        except Exception as exc:
            logger.error(f"[DOCTOR STATE WRITER] Redis write failed: {exc}")
            trace("DOCTOR-WRITE", state.session_id, f"write ERROR: {exc}")
        return state
