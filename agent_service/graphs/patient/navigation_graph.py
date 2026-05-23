from graphs.patient.nodes.executor import Executor
from graphs.patient.nodes.intent_detector import IntentDetector
from graphs.patient.nodes.memory_node import MemoryNode
from graphs.patient.nodes.response_generator import ResponseGenerator
from graphs.patient.nodes.tool_selector import ToolSelector
from graphs.shared.schemas import AgentState


class PatientGraph:
    @classmethod
    async def run(
        cls,
        message: str,
        patient_id: str,
        session_id: str | None = None,
        doctor_id: str | None = None,
        appointment_id: str | None = None,
    ) -> dict:
        state = AgentState(
            role="patient",
            message=message,
            patient_id=patient_id,
            doctor_id=doctor_id,
            session_id=session_id or patient_id,
            appointment_id=appointment_id,
        )
        state = await IntentDetector().run(state)
        state = await MemoryNode().run(state)
        state = await ToolSelector().run(state)
        state = await Executor().run(state)
        state = await ResponseGenerator().run(state)
        return {
            "response": state.response,
            "intent": state.intent.model_dump() if state.intent else None
        }
