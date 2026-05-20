from app.memory.session_memory import SessionMemory
from graphs.shared.memory_extractor import MemoryExtractor
from graphs.shared.schemas import AgentState


class MemoryNode:
    def __init__(self):
        self.extractor = MemoryExtractor()

    async def run(self, state: AgentState) -> AgentState:
        current = await SessionMemory.get(state.session_id)
        extracted = await self.extractor.extract(state.message, current)
        if extracted.get("patient_name"):
            extracted["last_patient_name"] = extracted["patient_name"]
        if extracted.get("patient_id"):
            extracted["last_patient_id"] = extracted["patient_id"]
        state.memory = await SessionMemory.update(state.session_id, extracted)

        if state.intent and self._has_patient_pronoun(state.message):
            state.intent.entities.setdefault("patient_name", state.memory.get("last_patient_name"))
            state.intent.entities.setdefault("patient_id", state.memory.get("last_patient_id"))
        return state

    def _has_patient_pronoun(self, message: str) -> bool:
        text = message.lower()
        return any(token in text for token in ["his", "her", "him", "sa", "son", "lui", "elle"])
