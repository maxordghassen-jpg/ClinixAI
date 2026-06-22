"""
MemoryRepository — CRUD for three longitudinal memory collections:

  user_memories       — structured key/value memories with confidence + frequency scoring
                        ALSO stores float[] embedding vectors for semantic retrieval
  workflow_snapshots  — serialized in-progress workflow state for cross-session resume
  memory_summaries    — (collection exists in DB; writer/reader not yet wired into the runtime)

Design rules:
  - All methods return None / [] on MongoDB unavailability (get_database() returns None).
  - No method raises — callers handle empty returns.
  - user_memories are upserted by (user_id, key) — one document per unique fact.
  - workflow_snapshots are upserted by (user_id, status="pending") — one active workflow at a time.
  - workflow_snapshots carry a MongoDB TTL index on expires_at (24 h default).

Vector storage strategy:
  Embeddings are stored as plain float[] arrays inside user_memories documents.
  Semantic search is performed in Python (cosine similarity via EmbedService).
  This works on local MongoDB AND MongoDB Atlas with zero schema changes.

  Atlas Vector Search upgrade path:
    When scaling beyond ~10K memories per user, replace get_memories_with_embeddings +
    Python cosine with a $vectorSearch aggregation pipeline targeting the 'embedding' field.
    Index type: "knnVector", dimensions: 384 (sentence_transformer) or 1536 (openai).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

WORKFLOW_TTL_HOURS = 24


class MemoryRepository:

    MEMORIES_COLLECTION   = "user_memories"
    SNAPSHOTS_COLLECTION  = "workflow_snapshots"

    # =========================================================================
    # user_memories — READ
    # =========================================================================

    async def get_ranked_memories(
        self,
        user_id: str,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """
        Return memories sorted by (frequency DESC, confidence DESC, updated_at DESC).
        Embedding vectors are intentionally excluded — they're large (~1.5 KB each)
        and not needed for structured ranking or LLM context injection.
        Use get_memories_with_embeddings() when vectors are required.
        """
        db = get_database()
        if db is None:
            return []
        try:
            cursor = (
                db[self.MEMORIES_COLLECTION]
                .find(
                    {"user_id": user_id},
                    {"_id": 0, "embedding": 0, "embedding_updated_at": 0},
                )
                .sort([("frequency", -1), ("confidence", -1), ("updated_at", -1)])
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.error(f"[MEM REPO] get_ranked_memories failed | user={user_id} | {exc}")
            return []

    async def get_memories_by_type(
        self,
        user_id: str,
        memory_type: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        db = get_database()
        if db is None:
            return []
        try:
            cursor = (
                db[self.MEMORIES_COLLECTION]
                .find({"user_id": user_id, "memory_type": memory_type}, {"_id": 0})
                .sort([("frequency", -1), ("updated_at", -1)])
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.error(f"[MEM REPO] get_memories_by_type failed | user={user_id} | {exc}")
            return []

    async def get_memories_with_embeddings(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Return memories that have a valid stored embedding vector.
        Used by EmbedService.rank_by_query() for semantic similarity search.

        Query uses "embedding.0 exists" — the most efficient way to check for
        a non-empty array in MongoDB without a full-collection scan.
        The embedding field IS included here (needed for cosine similarity).
        embedding_updated_at is excluded to keep the payload lean.
        """
        db = get_database()
        if db is None:
            return []
        try:
            cursor = (
                db[self.MEMORIES_COLLECTION]
                .find(
                    # "embedding.0 exists" = array has at least one element
                    {"user_id": user_id, "embedding.0": {"$exists": True}},
                    {"_id": 0, "embedding_updated_at": 0},
                )
                .sort([("frequency", -1), ("updated_at", -1)])
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.error(f"[MEM REPO] get_memories_with_embeddings failed | user={user_id} | {exc}")
            return []

    # =========================================================================
    # user_memories — WRITE
    # Upsert by (user_id, key). Increments frequency on every observed signal.
    # =========================================================================

    async def upsert_memory(
        self,
        user_id: str,
        role: str,
        memory_type: str,
        key: str,
        value: Any,
        confidence: float = 0.8,
        source: str = "chat",
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.MEMORIES_COLLECTION].update_one(
                {"user_id": user_id, "key": key},
                {
                    "$set": {
                        "value":       value,
                        "confidence":  confidence,
                        "role":        role,
                        "memory_type": memory_type,
                        "source":      source,
                        "updated_at":  now,
                    },
                    "$inc": {"frequency": 1},
                    "$setOnInsert": {
                        "user_id":    user_id,
                        "key":        key,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[MEM REPO] upsert_memory failed | user={user_id} key={key} | {exc}")

    async def update_embedding(
        self,
        user_id: str,
        key: str,
        embedding: list[float],
    ) -> None:
        """
        Attach (or overwrite) an embedding vector on an existing memory document.
        Called asynchronously after upsert_memory so embedding generation never
        blocks the response path.
        """
        db = get_database()
        if db is None:
            return
        if not embedding:
            return
        try:
            await db[self.MEMORIES_COLLECTION].update_one(
                {"user_id": user_id, "key": key},
                {"$set": {"embedding": embedding, "embedding_updated_at": datetime.now(timezone.utc)}},
            )
        except Exception as exc:
            logger.error(f"[MEM REPO] update_embedding failed | user={user_id} key={key} | {exc}")

    # =========================================================================
    # workflow_snapshots — READ
    # =========================================================================

    async def get_pending_workflow(self, user_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            now = datetime.now(timezone.utc)
            doc = await db[self.SNAPSHOTS_COLLECTION].find_one(
                {
                    "user_id": user_id,
                    "status":  "pending",
                    "expires_at": {"$gt": now},
                },
                {"_id": 0},
                sort=[("updated_at", -1)],
            )
            # [DEBUG] Log the raw MongoDB snapshot and its preconsultation fields
            if doc:
                _pc_keys = {
                    "preconsultation_done", "symptom_chief_complaint", "symptom_duration",
                    "symptom_severity", "symptom_associated", "recommended_specialty",
                    "preconsultation_summary",
                }
                _state  = doc.get("state", {}) or {}
                _pc_doc = {k: v for k, v in _state.items() if k in _pc_keys}
                logger.warning(
                    f"[DEBUG_PRECONSULT] get_pending_workflow | user={user_id} "
                    f"step={doc.get('step')!r} updated_at={doc.get('updated_at')} "
                    f"state_keys={sorted(_state.keys())} "
                    f"preconsult_in_snapshot={_pc_doc}"
                )
                logger.warning(
                    f"[DEBUG_SNAPSHOT] get_pending_workflow | user={user_id} "
                    f"workflow_type={doc.get('workflow_type')!r} full_state={_state}"
                )
            else:
                logger.warning(
                    f"[DEBUG_PRECONSULT] get_pending_workflow | user={user_id} — no pending snapshot"
                )
            return doc
        except Exception as exc:
            logger.error(f"[MEM REPO] get_pending_workflow failed | user={user_id} | {exc}")
            return None

    # =========================================================================
    # workflow_snapshots — WRITE
    # =========================================================================

    async def save_workflow_snapshot(
        self,
        user_id: str,
        role: str,
        workflow_type: str,
        state: dict[str, Any],
        step: str,
        context: dict[str, Any],
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=WORKFLOW_TTL_HOURS)
            await db[self.SNAPSHOTS_COLLECTION].update_one(
                {"user_id": user_id, "status": "pending"},
                {
                    "$set": {
                        "role":          role,
                        "workflow_type": workflow_type,
                        "state":         state,
                        "step":          step,
                        "context":       context,
                        "updated_at":    now,
                        "expires_at":    expires_at,
                        "status":        "pending",
                    },
                    "$setOnInsert": {
                        "user_id":    user_id,
                        "created_at": now,
                    },
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[MEM REPO] save_workflow_snapshot failed | user={user_id} | {exc}")

    async def complete_workflow_snapshot(self, user_id: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            await db[self.SNAPSHOTS_COLLECTION].update_many(
                {"user_id": user_id, "status": "pending"},
                {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}},
            )
        except Exception as exc:
            logger.error(f"[MEM REPO] complete_workflow_snapshot failed | user={user_id} | {exc}")


    # =========================================================================
    # Indexes — called once at startup from app/main.py
    # =========================================================================

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            memories = db[self.MEMORIES_COLLECTION]
            await memories.create_index([("user_id", 1), ("key", 1)], unique=True)
            await memories.create_index([("user_id", 1), ("memory_type", 1)])
            await memories.create_index([("user_id", 1), ("frequency", -1)])
            # Sparse index for efficient "has embedding" queries used by semantic retrieval.
            # sparse=True means documents without an embedding field are not indexed
            # (saves space, since embeddings are added asynchronously after upsert).
            await memories.create_index(
                [("user_id", 1), ("embedding", 1)],
                sparse=True,
                name="user_embedding_sparse",
            )

            snapshots = db[self.SNAPSHOTS_COLLECTION]
            await snapshots.create_index([("user_id", 1), ("status", 1)])
            # TTL: MongoDB deletes documents automatically when expires_at passes
            await snapshots.create_index("expires_at", expireAfterSeconds=0)

            logger.info("[MEM REPO] longitudinal memory indexes ensured")
        except Exception as exc:
            logger.error(f"[MEM REPO] create_indexes failed: {exc}")
