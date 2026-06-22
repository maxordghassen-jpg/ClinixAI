"""
Doctor StateWriterNode — turn-end persistence.

  1. Flush state.memory to Redis.
  2. Fire async: MemoryExtractionService → user_memories for this doctor.
"""

import asyncio
import logging

from app.memory.redis_memory import RedisMemory
from app.services.memory_extraction_service import MemoryExtractionService
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)

_redis     = RedisMemory()
_extractor = MemoryExtractionService()


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

        # Async long-term memory extraction for the doctor
        doctor_id = state.doctor_id
        if doctor_id:
            asyncio.create_task(
                _extractor.extract_and_store(
                    user_id=doctor_id,
                    role="doctor",
                    message=state.message,
                    response=state.response or "",
                    session_memory=state.memory,
                    profile={},
                )
            )

        return state
