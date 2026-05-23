"""
Doctor MemoryNode — Redis-backed session memory.

Replaces the in-process SessionMemory dict (which died on restart and was not
shared across workers) with the same RedisMemory used by the patient graph.

Doctor session_id = doctor_id (set by DoctorGraph.run() as default).
Memory keys tracked here are doctor-scoped context: last patient referenced,
last action taken. They survive restarts and multiple worker processes.

This node runs AFTER IntentDetector (unlike patient graph where memory loads
first). The session state is updated with any entity entities extracted in the
current turn, then written immediately. The terminal write in DoctorGraph.run()
persists the final state after the full pipeline completes.
"""

import logging

from app.memory.redis_memory import RedisMemory
from graphs.shared.memory_extractor import MemoryExtractor
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)


class MemoryNode:

    def __init__(self):
        self.memory = RedisMemory()
        self.extractor = MemoryExtractor()

    async def run(self, state: AgentState) -> AgentState:

        # Load current session state from Redis
        try:
            current = await self.memory.get(state.session_id)
        except Exception as exc:
            trace("DOCTOR-MEM", state.session_id, f"Redis load error: {exc} — using empty state")
            current = {}

        trace("DOCTOR-MEM", state.session_id,
              f"loaded {len(current)} keys: {list(current.keys())}")

        # Extract entities from the current message (patient name/id references, etc.)
        try:
            extracted = await self.extractor.extract(state.message, current)
        except Exception as exc:
            trace("DOCTOR-MEM", state.session_id, f"extractor error: {exc} — no extraction")
            extracted = {}

        # Track last referenced patient for pronoun resolution ("his", "her")
        if extracted.get("patient_name"):
            extracted["last_patient_name"] = extracted["patient_name"]
        if extracted.get("patient_id"):
            extracted["last_patient_id"] = extracted["patient_id"]

        # Merge into current and persist immediately (doctor pipeline has no StateWriterNode)
        if extracted:
            try:
                current = await self.memory.update(state.session_id, extracted)
                trace("DOCTOR-MEM", state.session_id,
                      f"updated {len(extracted)} key(s): {list(extracted.keys())}")
            except Exception as exc:
                trace("DOCTOR-MEM", state.session_id, f"Redis update error: {exc}")
                # Merge in-memory even if Redis failed — pipeline continues
                for k, v in extracted.items():
                    if v not in (None, "", [], {}):
                        current[k] = v

        state.memory = current

        # Carry over pronoun resolution into intent entities for the executor
        if state.intent and self._has_patient_pronoun(state.message):
            state.intent.entities.setdefault("patient_name", current.get("last_patient_name"))
            state.intent.entities.setdefault("patient_id", current.get("last_patient_id"))

        return state

    def _has_patient_pronoun(self, message: str) -> bool:
        text = message.lower()
        return any(
            token in text
            for token in ["his", "her", "him", "sa", "son", "lui", "elle", "له", "لها"]
        )
