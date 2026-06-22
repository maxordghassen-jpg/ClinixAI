"""
CRIT-6 validation — doctor chat history auto-save must not be wiped by an
out-of-order race between two /chat/history/save requests.

Simulates: frontend fires save(turn2, 4 msgs) then save(turn1, 2 msgs) lands
late (out of order). Before the fix, the second (shorter) write would
overwrite "messages" via a plain $set, dropping turn2 from persisted history.
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.db.mongo_client import connect_to_mongo, close_mongo_connection, get_database  # noqa: E402
from app.repositories.chat_history_repo import ChatHistoryRepository  # noqa: E402

TEST_USER = "validation-test-doctor"
TEST_ROLE = "doctor"
TEST_SESSION = "validation-test-session-crit6"


async def main() -> None:
    await connect_to_mongo()
    db = get_database()
    if db is None:
        print("BLOCKED: MongoDB not connected")
        return

    repo = ChatHistoryRepository()
    col = db["chat_history"]
    await col.delete_one(
        {"user_id": TEST_USER, "user_role": TEST_ROLE, "session_id": TEST_SESSION}
    )

    msgs1 = [
        {"role": "user", "content": "turn1 user"},
        {"role": "assistant", "content": "turn1 assistant"},
    ]
    msgs2 = msgs1 + [
        {"role": "user", "content": "turn2 user"},
        {"role": "assistant", "content": "turn2 assistant"},
    ]
    msgs3 = msgs2 + [
        {"role": "user", "content": "turn3 user"},
        {"role": "assistant", "content": "turn3 assistant"},
    ]

    try:
        # Longer save (turn2) lands first.
        await repo.upsert_conversation(TEST_USER, TEST_ROLE, TEST_SESSION, msgs2, language="en")
        doc = await repo.get_conversation(TEST_USER, TEST_ROLE, TEST_SESSION)
        assert doc is not None and len(doc["messages"]) == 4, (
            f"setup failed — expected 4 msgs after turn2 save, got "
            f"{len(doc['messages']) if doc else 'None'}"
        )
        print("PASS: turn2 save (4 msgs) persisted")

        # Stale shorter save (turn1) arrives late.
        await repo.upsert_conversation(TEST_USER, TEST_ROLE, TEST_SESSION, msgs1, language="en")
        doc = await repo.get_conversation(TEST_USER, TEST_ROLE, TEST_SESSION)
        n = len(doc["messages"]) if doc else 0
        assert n == 4, f"STALE WRITE WIPED HISTORY — expected 4 msgs, got {n}"
        print("PASS: stale shorter save (2 msgs) did not wipe turn2's history")

        # Normal incremental save (turn3, strictly longer) still applies.
        await repo.upsert_conversation(TEST_USER, TEST_ROLE, TEST_SESSION, msgs3, language="en")
        doc = await repo.get_conversation(TEST_USER, TEST_ROLE, TEST_SESSION)
        n = len(doc["messages"]) if doc else 0
        assert n == 6, f"expected 6 msgs after turn3 save, got {n}"
        print("PASS: normal longer save (6 msgs) still applies")

        assert doc.get("title"), "title should be set"
        assert doc.get("created_at"), "created_at should be set"
        print(f"title={doc['title']!r}")
        print("ALL PASS")
    finally:
        await col.delete_one(
            {"user_id": TEST_USER, "user_role": TEST_ROLE, "session_id": TEST_SESSION}
        )
        await close_mongo_connection()


asyncio.run(main())
