import asyncio

from app.memory.redis_memory import RedisMemory
from app.services.patient_memory_service import PatientMemoryService
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.patient.services.workflow_guard_service import WorkflowGuardService
from graphs.patient.services.workflow_cleanup_service import WorkflowCleanupService


class MemoryNode:
    """
    Turn-start loader — two memory sources, one clean state.

    Redis  → state.memory   (short-term workflow state, mutable this turn)
    MongoDB → state.profile  (long-term patient intelligence, read-only this turn)

    The two loads run in parallel via asyncio.gather(). Profile load failure is
    silent (returns {}); the turn continues with an empty profile rather than
    crashing.

    StateWriterNode persists state.memory to Redis at end of turn.
    PatientMemoryService (called from ActionNode on events) persists to MongoDB.
    state.profile is never written back to either store by this node.
    """

    def __init__(self):
        self.memory = RedisMemory()
        self.workflow_guard = WorkflowGuardService()
        self.cleanup_service = WorkflowCleanupService()
        self.patient_memory = PatientMemoryService()

    async def run(self, state: AgentState) -> AgentState:

        # =====================================================
        # PARALLEL LOAD: Redis workflow state + MongoDB profile
        # =====================================================

        session_memory, patient_profile = await asyncio.gather(
            self.memory.get(state.session_id),
            self.patient_memory.load_profile(state.patient_id or ""),
            return_exceptions=True,
        )

        # Handle Redis load failure (shouldn't happen — RedisMemory already
        # catches internally and returns {}, but guard here for safety)
        if isinstance(session_memory, Exception):
            trace("MEMORY", state.session_id, f"Redis load error: {session_memory} — using empty state")
            session_memory = {}

        # Handle MongoDB load failure (PatientMemoryService already catches
        # internally, but asyncio.gather with return_exceptions=True surfaces it)
        if isinstance(patient_profile, Exception):
            trace("MEMORY", state.session_id, f"MongoDB profile load error: {patient_profile} — empty profile")
            patient_profile = {}

        key_summary = ", ".join(session_memory.keys()) if session_memory else "empty"
        trace("MEMORY", state.session_id, f"loaded {len(session_memory)} Redis keys: {key_summary}")
        trace("MEMORY", state.session_id,
              f"step={session_memory.get('step')} | intent={session_memory.get('intent')} "
              f"| doctor_id={session_memory.get('doctor_id')} "
              f"| date={session_memory.get('date')} | time={session_memory.get('time')}")

        profile_lang = patient_profile.get("language", "—") if patient_profile else "—"
        profile_specialties = patient_profile.get("preferred_specialties", []) if patient_profile else []
        trace("MEMORY", state.session_id,
              f"profile loaded | lang={profile_lang} | specialties={profile_specialties}")

        # =====================================================
        # EXPIRED WORKFLOW GUARD
        # =====================================================

        if self.workflow_guard.is_expired(session_memory):
            trace("MEMORY", state.session_id, "WORKFLOW EXPIRED — clearing workflow state")
            await self.cleanup_service.clear_workflow(state.session_id)
            session_memory = await self.memory.get(state.session_id)
            trace("MEMORY", state.session_id, "workflow cleared, reloaded clean state")

        # =====================================================
        # INJECT REQUEST-LEVEL PATIENT ID
        # =====================================================

        if state.patient_id:
            session_memory["patient_id"] = state.patient_id
            trace("MEMORY", state.session_id, f"patient_id injected: {state.patient_id}")

        # =====================================================
        # APPLY PROFILE LANGUAGE DEFAULT
        # If the session has no language yet, seed it from the
        # patient's stored preference so the first response is
        # already in the right language.
        # =====================================================

        if not session_memory.get("language") and patient_profile.get("language"):
            session_memory["language"] = patient_profile["language"]
            trace("MEMORY", state.session_id,
                  f"language seeded from profile: {patient_profile['language']!r}")

        # =====================================================
        # POPULATE STATE — single source of truth for this turn
        # =====================================================

        state.memory = session_memory
        state.profile = patient_profile

        return state
