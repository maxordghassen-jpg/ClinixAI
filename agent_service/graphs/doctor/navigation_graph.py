"""
Doctor conversation pipeline (imperative, not LangGraph).

Execution order:
  IntentDetector  → extract intent + entities from message
  MemoryNode      → load Redis session, merge extracted entities, write back
  ToolSelector    → map intent.tool to selected_tool name
  Executor        → run the tool, populate state.tool_result
  ResponseGenerator → format tool_result into a human response
  terminal write  → flush final state.memory to Redis

The terminal write is the doctor agent's equivalent of StateWriterNode:
it ensures that any state mutations made by the Executor or ResponseGenerator
are persisted at the end of the turn, not mid-turn. MemoryNode's write is
an early write for extracted entities; the terminal write is the final
authoritative snapshot.
"""

import logging

from app.memory.redis_memory import RedisMemory
from graphs.doctor.nodes.executor import Executor
from graphs.doctor.nodes.intent_detector import IntentDetector
from graphs.doctor.nodes.memory_node import MemoryNode
from graphs.doctor.nodes.response_generator import ResponseGenerator
from graphs.doctor.nodes.tool_selector import ToolSelector
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)

_redis = RedisMemory()


class DoctorGraph:

    @classmethod
    async def run(
        cls,
        message: str,
        doctor_id: str,
        session_id: str | None = None,
        appointment_id: str | None = None,
    ) -> dict:

        state = AgentState(
            role="doctor",
            message=message,
            doctor_id=doctor_id,
            session_id=session_id or doctor_id,
            appointment_id=appointment_id,
        )

        trace("DOCTOR", state.session_id, f"turn start | message={message!r}")

        try:
            state = await IntentDetector().run(state)
            state = await MemoryNode().run(state)
            state = await ToolSelector().run(state)
            state = await Executor().run(state)
            state = await ResponseGenerator().run(state)
        except Exception as exc:
            logger.error(f"[DOCTOR GRAPH] unhandled pipeline error: {exc}")
            trace("DOCTOR", state.session_id, f"pipeline ERROR: {exc}")
            state.response = "I encountered an error. Please try again."

        # Terminal Redis write — persists any final mutations from the pipeline
        try:
            if state.memory:
                await _redis.update(state.session_id, state.memory)
                trace("DOCTOR", state.session_id,
                      f"terminal Redis write complete | keys={list(state.memory.keys())}")
        except Exception as exc:
            logger.error(f"[DOCTOR GRAPH] terminal Redis write failed: {exc}")
            trace("DOCTOR", state.session_id, f"terminal write ERROR: {exc}")

        trace("DOCTOR", state.session_id, "turn complete")

        return {
            "response": state.response,
            "intent": state.intent.model_dump() if state.intent else None,
            "memory": state.memory,
            "data": state.tool_result,
        }
