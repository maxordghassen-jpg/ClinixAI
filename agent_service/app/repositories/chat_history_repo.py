"""
ChatHistoryRepository — persistent conversation history in MongoDB.

Collection: chat_history
Unique index: (user_id, user_role, session_id)

Each document holds the entire message list for one conversation so
reads are a single document fetch (no pagination needed at this scale).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

COLLECTION = "chat_history"


class ChatHistoryRepository:

    # ── Indexes ───────────────────────────────────────────────────────────────

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        col = db[COLLECTION]
        await col.create_index(
            [("user_id", ASCENDING), ("user_role", ASCENDING), ("session_id", ASCENDING)],
            unique=True,
            name="user_role_session_unique",
        )
        await col.create_index(
            [("user_id", ASCENDING), ("user_role", ASCENDING), ("updated_at", DESCENDING)],
            name="user_history_list",
        )
        logger.info("[ChatHistory] Indexes ensured")

    # ── Write ─────────────────────────────────────────────────────────────────

    async def upsert_conversation(
        self,
        user_id: str,
        user_role: str,
        session_id: str,
        messages: list[dict[str, Any]],
        language: str = "en",
    ) -> None:
        db = get_database()
        if db is None:
            logger.warning("[ChatHistory] upsert skipped — MongoDB not connected")
            return
        try:
            col = db[COLLECTION]
            now = datetime.now(timezone.utc)

            # Title = first user message, truncated to 50 chars
            title = ""
            for msg in messages:
                if msg.get("role") == "user":
                    title = (msg.get("content") or "")[:50]
                    break

            # Pipeline-based update (not a plain "$set" dict): the frontend fires
            # one save per turn without awaiting the previous request, so two
            # saves for the same session can land out of order. If the save
            # carrying FEWER messages arrives last, a plain "$set" would
            # overwrite (wipe) the newer turn that the earlier save already
            # persisted. Compare array lengths server-side and keep whichever
            # is longer — "$setOnInsert" isn't available in pipeline updates,
            # so "$ifNull" against the existing field reproduces "set once".
            await col.update_one(
                {"user_id": user_id, "user_role": user_role, "session_id": session_id},
                [
                    {
                        "$set": {
                            "messages": {
                                "$cond": [
                                    {"$gte": [
                                        {"$size": {"$ifNull": ["$messages", []]}},
                                        len(messages),
                                    ]},
                                    {"$ifNull": ["$messages", []]},
                                    messages,
                                ]
                            },
                            "language":   language,
                            "updated_at": now,
                            "title":      {"$ifNull": ["$title", title]},
                            "created_at": {"$ifNull": ["$created_at", now]},
                        }
                    }
                ],
                upsert=True,
            )
            logger.debug(
                "[ChatHistory] upserted | user=%s role=%s session=%s msgs=%d",
                user_id, user_role, session_id, len(messages),
            )
        except Exception:
            logger.exception(
                "[ChatHistory] upsert FAILED | user=%s role=%s session=%s",
                user_id, user_role, session_id,
            )

    # ── Read ──────────────────────────────────────────────────────────────────

    async def list_conversations(
        self,
        user_id: str,
        user_role: str,
    ) -> list[dict[str, Any]]:
        """Return summary rows (no messages array) sorted newest first."""
        db = get_database()
        if db is None:
            return []
        try:
            col = db[COLLECTION]
            cursor = col.find(
                {"user_id": user_id, "user_role": user_role},
                {"_id": 0, "messages": 0},
            ).sort("updated_at", DESCENDING)
            docs = await cursor.to_list(length=200)
            # Motor returns datetime objects — convert to ISO strings for JSON serialisation
            for doc in docs:
                for field in ("created_at", "updated_at"):
                    if isinstance(doc.get(field), datetime):
                        doc[field] = doc[field].isoformat()
            return docs
        except Exception:
            logger.exception("list_conversations failed for user=%s", user_id)
            return []

    async def get_conversation(
        self,
        user_id: str,
        user_role: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            col = db[COLLECTION]
            doc = await col.find_one(
                {"user_id": user_id, "user_role": user_role, "session_id": session_id},
                {"_id": 0},
            )
            if doc:
                for field in ("created_at", "updated_at"):
                    if isinstance(doc.get(field), datetime):
                        doc[field] = doc[field].isoformat()
            return doc
        except Exception:
            logger.exception("get_conversation failed for session=%s", session_id)
            return None

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_conversation(
        self,
        user_id: str,
        user_role: str,
        session_id: str,
    ) -> int:
        db = get_database()
        if db is None:
            return 0
        col = db[COLLECTION]
        result = await col.delete_one(
            {"user_id": user_id, "user_role": user_role, "session_id": session_id}
        )
        return result.deleted_count

    async def delete_all_conversations(
        self,
        user_id: str,
        user_role: str,
    ) -> int:
        db = get_database()
        if db is None:
            return 0
        col = db[COLLECTION]
        result = await col.delete_many({"user_id": user_id, "user_role": user_role})
        return result.deleted_count
