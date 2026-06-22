"""
Doctor MemoryNode — Redis session state + MongoDB long-term memory + semantic retrieval.

Three sources loaded in parallel:
  Layer 1 — Redis session_memory    → state.memory             (workflow context, mutable)
  Layer 2 — MongoDB long_term       → state.long_term_memories (user_memories, read-only)
  Layer 3 — Semantic retrieval      → merged into memory_context (per-turn, ephemeral)

Builds state.memory_context for LLM injection via MemoryContextBuilder.

Doctor session_id = "doctor:{doctor_id}" — set by DoctorGraph.run().
"""

import asyncio
import logging

from app.memory.memory_manager import MemoryManager
from graphs.shared.memory_context_builder import MemoryContextBuilder
from graphs.shared.memory_extractor import MemoryExtractor
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

logger = logging.getLogger(__name__)


class MemoryNode:

    def __init__(self):
        self.manager   = MemoryManager()
        self.extractor = MemoryExtractor()

    async def run(self, state: AgentState) -> AgentState:
        user_id = state.doctor_id or ""

        # ── Load session + long-term + semantic in parallel ───────────────────
        session_memory, long_term_memories, semantic_memories = await asyncio.gather(
            self.manager.load_session(state.session_id),
            self.manager.load_long_term(user_id),
            self.manager.load_semantic(user_id, state.message),
            return_exceptions=True,
        )

        if isinstance(session_memory, BaseException):
            trace("DOCTOR-MEM", state.session_id, f"Redis load error: {session_memory} — empty")
            session_memory = {}
        if isinstance(long_term_memories, BaseException) or not isinstance(long_term_memories, list):
            long_term_memories = []
        if isinstance(semantic_memories, BaseException) or not isinstance(semantic_memories, list):
            semantic_memories = []

        trace("DOCTOR-MEM", state.session_id,
              f"loaded | redis={len(session_memory)} keys "
              f"| long_term={len(long_term_memories)} "
              f"| semantic={len(semantic_memories)}")

        # ── Extract entities from the current message ─────────────────────────
        try:
            extracted = await self.extractor.extract(state.message, session_memory)
        except Exception as exc:
            trace("DOCTOR-MEM", state.session_id, f"extractor error: {exc}")
            extracted = {}

        # Track last referenced patient for pronoun resolution
        if extracted.get("patient_name"):
            extracted["last_patient_name"] = extracted["patient_name"]
        if extracted.get("patient_id"):
            extracted["last_patient_id"] = extracted["patient_id"]

        if extracted:
            try:
                session_memory = await self.manager.redis.update(state.session_id, extracted)
                trace("DOCTOR-MEM", state.session_id,
                      f"updated {len(extracted)} key(s): {list(extracted.keys())}")
            except Exception as exc:
                trace("DOCTOR-MEM", state.session_id, f"Redis update error: {exc}")
                for k, v in extracted.items():
                    if v not in (None, "", [], {}):
                        session_memory[k] = v

        # ── Build LLM-injectable context (hybrid: semantic + structured) ──────
        memory_context = MemoryContextBuilder.build_doctor_context(
            profile={},
            long_term=long_term_memories,
            semantic=semantic_memories,
        )

        # Carry over pronoun resolution
        if state.intent and self._has_patient_pronoun(state.message):
            state.intent.entities.setdefault("patient_name", session_memory.get("last_patient_name"))
            state.intent.entities.setdefault("patient_id",   session_memory.get("last_patient_id"))

        state.memory             = session_memory
        state.long_term_memories = long_term_memories if isinstance(long_term_memories, list) else []
        state.memory_context     = memory_context

        return state

    def _has_patient_pronoun(self, message: str) -> bool:
        text = message.lower()
        return any(
            token in text
            for token in ["his", "her", "him", "sa", "son", "lui", "elle", "له", "لها"]
        )
