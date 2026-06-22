"""
Patient MemoryNode — four-layer memory load at turn start.

  Layer 1 — Redis session_memory    → state.memory             (workflow state, mutable)
  Layer 2 — MongoDB patient_profile → state.profile            (patient_profiles, read-only)
  Layer 3 — MongoDB long-term       → state.long_term_memories (user_memories, read-only)
  Layer 4 — MongoDB pending workflow → state.pending_workflow  (workflow_snapshots, read-only)
  Layer 5 — Semantic retrieval      → merged into memory_context (per-turn, ephemeral)

All five sources are loaded concurrently via asyncio.gather.

Exception safety:
  asyncio.gather(return_exceptions=True) returns raw results — not a destructure-safe
  nested tuple.  Results are collected as a flat list and unpacked with isinstance
  checks to prevent TypeError when any coroutine raises unexpectedly.

Graceful degradation: if semantic retrieval is unavailable (model not installed,
provider error), the turn continues with structured memory only.
"""

import asyncio
import time

from app.memory.memory_manager import MemoryManager
from app.services.patient_memory_service import PatientMemoryService
from graphs.shared.memory_context_builder import MemoryContextBuilder
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.patient.services.workflow_guard_service import WorkflowGuardService
from graphs.patient.services.workflow_cleanup_service import WorkflowCleanupService


class MemoryNode:

    def __init__(self):
        self.manager        = MemoryManager()
        self.patient_memory = PatientMemoryService()
        self.workflow_guard = WorkflowGuardService()
        self.cleanup        = WorkflowCleanupService()

    async def run(self, state: AgentState) -> AgentState:
        user_id = state.patient_id or ""

        # ── Concurrent load: all five layers ─────────────────────────────────
        # Collect as a flat list first — nested-tuple destructuring is unsafe
        # when return_exceptions=True can put an Exception in position 0.
        raw = await asyncio.gather(
            self.manager.load_all(state.session_id, user_id),
            self.patient_memory.load_profile(user_id),
            self.manager.load_semantic(user_id, state.message),
            return_exceptions=True,
        )

        # ── Safe unpack ───────────────────────────────────────────────────────
        load_all_result   = raw[0]
        patient_profile   = raw[1]
        semantic_memories = raw[2]

        if isinstance(load_all_result, BaseException):
            trace("MEMORY", state.session_id, f"load_all error: {load_all_result} — fallback empty")
            session_memory, long_term_memories, pending_workflow = {}, [], None
        else:
            session_memory, long_term_memories, pending_workflow = load_all_result

        if isinstance(patient_profile, BaseException):
            trace("MEMORY", state.session_id, f"profile load error: {patient_profile}")
            patient_profile = {}
        if not isinstance(patient_profile, dict):
            patient_profile = {}

        if isinstance(semantic_memories, BaseException) or not isinstance(semantic_memories, list):
            semantic_memories = []

        trace(
            "MEMORY", state.session_id,
            f"loaded | redis={len(session_memory)} keys "
            f"| long_term={len(long_term_memories)} "
            f"| semantic={len(semantic_memories)} "
            f"| pending={'yes' if pending_workflow else 'no'} "
            f"| lang={patient_profile.get('language', '—')}",
        )

        # ── [DEBUG] Preconsultation field tracker ─────────────────────────────
        _PC_DEBUG = frozenset({
            "preconsultation_done", "symptom_chief_complaint", "symptom_duration",
            "symptom_severity", "symptom_associated", "recommended_specialty",
            "preconsultation_summary",
        })

        # ── Expired workflow guard ────────────────────────────────────────────
        if self.workflow_guard.is_expired(session_memory):
            _pre_cleanup = {k: v for k, v in session_memory.items() if k in _PC_DEBUG}
            trace("DEBUG_PRECONSULT", state.session_id,
                  f"[EXPIRY] Redis BEFORE cleanup: {_pre_cleanup}")
            trace("MEMORY", state.session_id, "WORKFLOW EXPIRED — clearing")
            await self.cleanup.clear_workflow(state.session_id)
            session_memory = await self.manager.load_session(state.session_id)
            _post_cleanup = {k: v for k, v in session_memory.items() if k in _PC_DEBUG}
            trace("DEBUG_PRECONSULT", state.session_id,
                  f"[EXPIRY] Redis AFTER cleanup: {_post_cleanup} | "
                  f"pending_workflow_loaded_pre_cleanup={'yes' if pending_workflow else 'no'}")

        # ── Cross-session workflow resume ─────────────────────────────────────
        # MED-3: the snapshot is intentionally NOT merged into session_memory
        # here. pending_workflow (set below) carries it forward to IntentNode,
        # and the resume hint (below) tells the LLM a workflow is pending.
        # IntentNode merges the snapshot in only if THIS message's extracted
        # intent is empty/"none" or matches the pending workflow's type — so a
        # brand-new, unrelated request never silently inherits a stale
        # step/doctor/date from an abandoned workflow.

        # ── Inject request-level IDs ──────────────────────────────────────────
        if state.patient_id:
            session_memory["patient_id"] = state.patient_id
        if state.doctor_id and not session_memory.get("doctor_id"):
            session_memory["doctor_id"] = state.doctor_id

        # ── Seed language from profile ────────────────────────────────────────
        if not session_memory.get("language") and patient_profile.get("language"):
            session_memory["language"] = patient_profile["language"]
            trace("MEMORY", state.session_id,
                  f"language seeded from profile: {patient_profile['language']!r}")

        # ── Build LLM-injectable memory context (hybrid: semantic + structured) ──
        memory_context = MemoryContextBuilder.build_patient_context(
            profile=patient_profile,
            long_term=long_term_memories,
            semantic=semantic_memories,
        )
        if pending_workflow and not session_memory.get("step"):
            hint = MemoryContextBuilder.build_resume_hint(pending_workflow)
            if hint:
                memory_context = (memory_context + "\n" + hint).strip() if memory_context else hint

        if memory_context:
            trace("MEMORY", state.session_id,
                  f"context={len(memory_context)} chars | semantic_hits={len(semantic_memories)}")

        # ── Populate state ────────────────────────────────────────────────────
        state.memory             = session_memory
        state.profile            = patient_profile
        state.long_term_memories = long_term_memories
        state.memory_context     = memory_context
        state.pending_workflow   = pending_workflow

        return state
