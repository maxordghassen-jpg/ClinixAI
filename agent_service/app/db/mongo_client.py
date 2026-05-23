"""
MongoDB Motor async client — module-level singleton.

One Motor client is created when connect_to_mongo() is called during
FastAPI lifespan startup. All repositories share this single client and
its underlying connection pool. The client is closed during lifespan
shutdown via close_mongo_connection().

If MONGODB_URI is empty (e.g. local dev without MongoDB), connect_to_mongo()
is a no-op and get_database() returns None. Repositories guard against this
and degrade gracefully — long-term memory is disabled, not fatal.
"""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global _client, _database

    if not settings.MONGODB_URI:
        logger.warning("MONGODB_URI not set — long-term patient memory disabled")
        return

    try:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        # Ping to verify the connection before accepting traffic
        await _client.admin.command("ping")
        _database = _client[settings.MONGO_DB_NAME]
        logger.info(f"MongoDB connected | db={settings.MONGO_DB_NAME}")
    except Exception as exc:
        logger.error(f"MongoDB connection failed: {exc} — long-term memory disabled")
        _client = None
        _database = None


async def close_mongo_connection() -> None:
    global _client, _database
    if _client:
        _client.close()
        _client = None
        _database = None
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase | None:
    return _database
