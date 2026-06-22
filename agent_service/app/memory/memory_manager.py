"""
MemoryManager — unified interface over all memory layers.

  Layer 1 — Redis  (short-term, session-scoped, 30-min TTL)
             Keys: {session_id}:memory
             Purpose: active workflow state within one conversation thread.

  Layer 2 — MongoDB user_memories (long-term, user-scoped, permanent)
             Keys: (user_id, key) compound unique index
             Purpose: cross-session preferences, episodic history, patterns.
             ALSO stores float[] embedding vectors for semantic retrieval.

  Layer 3 — MongoDB workflow_snapshots (medium-term, 24-h TTL)
             Keys: (user_id, status="pending")
             Purpose: resume interrupted workflows across sessions.

  Layer 4 — Semantic (ephemeral, per-turn)
             Source: EmbedService.rank_by_query() over Layer 2 embeddings.
             Purpose: surface memories most semantically relevant to the
             current user message, regardless of language.

Design notes:
  - EmbedService is instantiated once at module level (stateless, cache is
    process-wide via module-level LRU dict).
  - load_semantic() returns [] on ANY failure — callers always degrade
    gracefully to structured-only ranking.
  - All methods that touch MongoDB delegate entirely to MemoryRepository which
    is equally resilient (returns empty on DB unavailability).

Identity isolation guarantee:
  Every load_semantic query filters by user_id FIRST, THEN checks embedding
  presence.  There is no code path that retrieves vectors without a user_id
  predicate.  Cross-user leakage is structurally impossible.
"""

import asyncio
import logging
from typing import Any

from app.memory.redis_memory import RedisMemory
from app.repositories.memory_repo import MemoryRepository

logger = logging.getLogger(__name__)

# ── Module-level EmbedService singleton ──────────────────────────────────────
# EmbedService is stateless — all mutable state lives in the process-wide cache
# dict and the embedding provider singleton.  Reusing one instance avoids
# repeated object construction on every load_semantic() call.
_embed_svc: Any = None


def _get_embed_svc():
    global _embed_svc
    if _embed_svc is None:
        from app.embeddings.embed_service import EmbedService
        _embed_svc = EmbedService()
    return _embed_svc


# ── Workflow step classification ──────────────────────────────────────────────

_SNAPSHOTABLE_STEPS: frozenset[str] = frozenset({
    "awaiting_specialty",
    "searching_doctors",
    "selecting_doctor",
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",
    "awaiting_recovery_choice",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "awaiting_reschedule_slot_selection",
    "confirming_reschedule",
    "confirming_cancel",
})

_TERMINAL_STEPS: frozenset[str] = frozenset({
    "ready_to_book",
    "confirmed",
    "ready_to_cancel",
    "completed",
    # Preconsultation questionnaire finished — treat as terminal so that any
    # stale booking snapshot left over from before the questionnaire started
    # is marked complete and will not resurface via cross-session resume.
    "preconsultation_complete",
})

# Preconsultation steps that are active but not snapshotable.
# When the agent is at one of these steps, any pending booking snapshot in
# MongoDB must be deleted immediately: if Redis expires mid-questionnaire,
# the booking snapshot would otherwise be re-injected and override the active
# preconsultation flow.
_PRECONSULT_COLLECTING_STEPS: frozenset[str] = frozenset({
    "collecting_chief_complaint",
    "collecting_duration",
    "collecting_severity",
    "collecting_associated",
})

_CONTEXT_KEYS = (
    "specialty", "doctor_id", "doctor_name", "date", "time",
    "new_date", "new_time", "place_type", "intent",
)


class MemoryManager:

    def __init__(self) -> None:
        self.redis = RedisMemory()
        self.repo  = MemoryRepository()

    # ── Load ──────────────────────────────────────────────────────────────────

    async def load_session(self, session_id: str) -> dict[str, Any]:
        try:
            return await self.redis.get(session_id)
        except Exception as exc:
            logger.error(f"[MEM MGR] load_session error | {exc}")
            return {}

    async def load_long_term(self, user_id: str, limit: int = 15) -> list[dict[str, Any]]:
        if not user_id:
            return []
        try:
            return await self.repo.get_ranked_memories(user_id, limit=limit)
        except Exception as exc:
            logger.error(f"[MEM MGR] load_long_term error | user={user_id} | {exc}")
            return []

    async def load_pending_workflow(self, user_id: str) -> dict[str, Any] | None:
        if not user_id:
            return None
        try:
            return await self.repo.get_pending_workflow(user_id)
        except Exception as exc:
            logger.error(f"[MEM MGR] load_pending_workflow error | user={user_id} | {exc}")
            return None

    async def load_all(
        self,
        session_id: str,
        user_id: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
        """
        Parallel load of all three persistent memory sources.
        Returns (session_memory, long_term_memories, pending_workflow).
        Never raises — each sub-load is independently resilient.
        """
        results = await asyncio.gather(
            self.load_session(session_id),
            self.load_long_term(user_id),
            self.load_pending_workflow(user_id),
            return_exceptions=True,
        )
        session   = results[0] if not isinstance(results[0], BaseException) else {}
        long_term = results[1] if not isinstance(results[1], BaseException) else []
        workflow  = results[2] if not isinstance(results[2], BaseException) else None
        return session, long_term, workflow

    # ── Semantic retrieval ────────────────────────────────────────────────────

    async def load_semantic(
        self,
        user_id: str,
        query_text: str,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return memories most semantically relevant to query_text.

        Flow:
          1. Embed query_text via cached EmbedService.
          2. Load all memories with a stored embedding vector from MongoDB.
          3. Compute cosine similarity + hybrid score (EmbedService.rank_by_query).
          4. Apply SEMANTIC_SIMILARITY_THRESHOLD filter.
          5. Return top_k annotated results.

        Identity safety: MongoDB query always filters by user_id first.
        Returns [] on any failure — callers always have structured fallback.

        Observability: logs candidate count, result count, and top similarity
        score at DEBUG level for tuning.
        """
        if not user_id or not query_text:
            return []
        try:
            from app.config.settings import settings
            svc = _get_embed_svc()
            k   = top_k if top_k is not None else settings.SEMANTIC_MEMORY_TOP_K

            # Embed query + load candidate memories in parallel
            query_vec, memories = await asyncio.gather(
                svc.embed_text(query_text),
                self.repo.get_memories_with_embeddings(user_id),
                return_exceptions=True,
            )

            if isinstance(query_vec, BaseException) or not query_vec:
                logger.debug(f"[MEM MGR] semantic: embed failed for user={user_id}")
                return []
            if isinstance(memories, BaseException) or not memories:
                return []

            ranked    = svc.rank_by_query(query_vec, memories, top_k=k)
            threshold = settings.SEMANTIC_SIMILARITY_THRESHOLD
            ranked    = [
                m for m in ranked
                if m.get("retrieval_meta", {}).get("similarity", 0.0) >= threshold
            ]

            # Structured observability log
            if ranked:
                top_sim   = ranked[0].get("retrieval_meta", {}).get("similarity", 0.0)
                top_topic = ranked[0].get("retrieval_meta", {}).get("matched_topic", "")
                logger.debug(
                    f"[MEM MGR] semantic | user={user_id} "
                    f"candidates={len(memories)} results={len(ranked)} "
                    f"top_sim={top_sim:.3f} top_topic={top_topic!r}"
                )
            else:
                logger.debug(
                    f"[MEM MGR] semantic | user={user_id} "
                    f"candidates={len(memories)} results=0 (below threshold)"
                )

            return ranked

        except Exception as exc:
            logger.warning(f"[MEM MGR] load_semantic failed (degraded): {exc}")
            return []

    # ── Save ──────────────────────────────────────────────────────────────────

    async def save_session(self, session_id: str, data: dict[str, Any]) -> None:
        try:
            await self.redis.update(session_id, data)
        except Exception as exc:
            logger.error(f"[MEM MGR] save_session error | {exc}")

    async def save_workflow_snapshot(
        self,
        user_id: str,
        role: str,
        session_memory: dict[str, Any],
    ) -> None:
        step = session_memory.get("step", "")
        if not step or step not in _SNAPSHOTABLE_STEPS:
            # Active preconsultation collecting steps are not themselves snapshotable,
            # but any stale booking snapshot from a previous session must be deleted
            # now — otherwise it will be re-injected by MemoryNode if Redis expires
            # while the questionnaire is in progress, overwriting the active flow.
            if step in _PRECONSULT_COLLECTING_STEPS:
                await self.complete_workflow(user_id)
            return
        context = {k: session_memory[k] for k in _CONTEXT_KEYS if k in session_memory}
        # [DEBUG] Log which preconsultation fields are being written into MongoDB snapshot
        _PC_SAVE_KEYS = {
            "preconsultation_done", "symptom_chief_complaint", "symptom_duration",
            "symptom_severity", "symptom_associated", "recommended_specialty",
            "preconsultation_summary",
        }
        _pc_in_state = {k: v for k, v in session_memory.items() if k in _PC_SAVE_KEYS}
        logger.warning(
            f"[DEBUG_PRECONSULT] save_workflow_snapshot | user={user_id} step={step!r} "
            f"preconsult_fields_in_state={_pc_in_state}"
        )
        try:
            await self.repo.save_workflow_snapshot(
                user_id=user_id,
                role=role,
                workflow_type=session_memory.get("intent", "unknown"),
                state=session_memory,
                step=step,
                context=context,
            )
        except Exception as exc:
            logger.error(f"[MEM MGR] save_workflow_snapshot error | user={user_id} | {exc}")

    async def complete_workflow(self, user_id: str) -> None:
        try:
            await self.repo.complete_workflow_snapshot(user_id)
        except Exception as exc:
            logger.error(f"[MEM MGR] complete_workflow error | user={user_id} | {exc}")

    def is_terminal_step(self, step: str) -> bool:
        return step in _TERMINAL_STEPS
