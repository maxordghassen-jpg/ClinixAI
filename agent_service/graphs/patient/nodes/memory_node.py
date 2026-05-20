from app.memory.session_memory import SessionMemory
from graphs.shared.memory_extractor import MemoryExtractor
from graphs.shared.schemas import AgentState


class MemoryNode:
    def __init__(self):
        self.extractor = MemoryExtractor()

    async def run(self, state: AgentState) -> AgentState:
        current = await SessionMemory.get(state.session_id)
        extracted = await self.extractor.extract(state.message, current)
        state.memory = await SessionMemory.update(state.session_id, extracted)
        if state.patient_id:
            state.memory = await SessionMemory.update(state.session_id, {"patient_id": state.patient_id})
        return state
