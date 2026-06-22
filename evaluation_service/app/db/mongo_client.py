"""
MongoDB async client for the evaluation service.

Uses motor (async MongoDB driver). Connection is established once at startup
via the FastAPI lifespan handler and stored as a module-level singleton.

Collection: evaluation_results
  - All EvalResult fields
  - MongoDB _id as ObjectId, exposed as string "id" in responses
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

_client:   AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect(mongo_uri: str, db_name: str = "clinix_eval") -> None:
    global _client, _database
    _client   = AsyncIOMotorClient(mongo_uri)
    _database = _client[db_name]
    # Create indexes on first connect
    await _database["evaluation_results"].create_index("scenario_id")
    await _database["evaluation_results"].create_index("evaluated_at")
    await _database["evaluation_results"].create_index("role")
    await _database["evaluation_results"].create_index("language")
    await _database["evaluation_results"].create_index("model_used")
    logger.info("[MongoDB] Connected to %s / %s", mongo_uri, db_name)


async def disconnect() -> None:
    global _client, _database
    if _client:
        _client.close()
        _client = _database = None
        logger.info("[MongoDB] Disconnected")


def get_db() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("MongoDB not connected — call connect() first.")
    return _database
