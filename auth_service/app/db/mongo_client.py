import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global _client, _database

    if not settings.MONGODB_URI:
        logger.warning("MONGODB_URI not set — auth database unavailable")
        return

    try:
        _client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        await _client.admin.command("ping")
        _database = _client[settings.MONGO_DB_NAME]
        logger.info(f"MongoDB connected | db={settings.MONGO_DB_NAME}")
    except Exception as exc:
        logger.error(f"MongoDB connection failed: {exc}")
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


def get_client() -> AsyncIOMotorClient | None:
    return _client
