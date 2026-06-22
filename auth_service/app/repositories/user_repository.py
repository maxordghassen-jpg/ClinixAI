import logging
from typing import Any

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"


class UserRepository:

    async def find_by_email(self, email: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            return await db[USERS_COLLECTION].find_one(
                {"email": email.lower()}, {"_id": 0}
            )
        except Exception as exc:
            logger.error(f"[USER REPO] find_by_email failed | {exc}")
            return None

    async def create(self, user: dict[str, Any]) -> bool:
        db = get_database()
        if db is None:
            return False
        try:
            await db[USERS_COLLECTION].insert_one(user)
            return True
        except Exception as exc:
            logger.error(f"[USER REPO] create failed | {exc}")
            return False

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            await db[USERS_COLLECTION].create_index("email", unique=True)
            await db[USERS_COLLECTION].create_index("role")
            logger.info("[USER REPO] indexes ensured")
        except Exception as exc:
            logger.error(f"[USER REPO] create_indexes failed: {exc}")
