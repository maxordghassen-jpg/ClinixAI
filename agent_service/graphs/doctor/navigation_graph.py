from graphs.doctor.nodes.executor import Executor
from graphs.doctor.nodes.intent_detector import IntentDetector
from graphs.doctor.nodes.memory_node import MemoryNode
from graphs.doctor.nodes.response_generator import ResponseGenerator
from graphs.doctor.nodes.tool_selector import ToolSelector
from graphs.shared.schemas import AgentState


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
        state = await IntentDetector().run(state)
        state = await MemoryNode().run(state)
        state = await ToolSelector().run(state)
        state = await Executor().run(state)
        state = await ResponseGenerator().run(state)
        return {
            "response": state.response,
            "intent": state.intent.model_dump() if state.intent else None,
            "memory": state.memory,
            "data": state.tool_result,
        }
