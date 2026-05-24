"""
Doctor conversation pipeline (imperative, not LangGraph).

Execution order:
  IntentDetector   → extract intent + entities from message
  MemoryNode       → load Redis session, merge extracted entities, write back
  ActionNode       → route to domain handler, populate state.tool_result
  ResponseGenerator → format tool_result into a human response
  StateWriterNode  → flush final state.memory to Redis
"""

import logging

from graphs.doctor.nodes.action_node import ActionNode
from graphs.doctor.nodes.intent_detector import IntentDetector
from graphs.doctor.nodes.memory_node import MemoryNode
from graphs.doctor.nodes.response_generator import ResponseGenerator
from graphs.doctor.nodes.state_writer_node import StateWriterNode
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)


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
            state = await ActionNode().run(state)
            state = await ResponseGenerator().run(state)
            state = await StateWriterNode().run(state)
        except Exception as exc:
            logger.error(f"[DOCTOR GRAPH] unhandled pipeline error: {exc}")
            trace("DOCTOR", state.session_id, f"pipeline ERROR: {exc}")
            state.response = "I encountered an error. Please try again."

        trace("DOCTOR", state.session_id, "turn complete")

        return {
            "response": state.response,
            "intent": state.intent.model_dump() if state.intent else None,
            "memory": state.memory,
            "data": state.tool_result,
        }
