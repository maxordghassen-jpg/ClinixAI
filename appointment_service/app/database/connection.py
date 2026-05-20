from motor.motor_asyncio import (
    AsyncIOMotorClient
)

from app.core.config import (
    settings
)

import logging


logger = logging.getLogger(__name__)


client = None
database = None


async def connect_to_mongo():

    global client
    global database
    client = AsyncIOMotorClient(
        settings.MONGODB_URI
    )

    database = client[
        settings.DATABASE_NAME
    ]

    logger.info(
        "Connected to MongoDB"
    )


async def close_mongo_connection():

    global client

    if client:

        client.close()

        logger.info(
            "MongoDB connection closed"
        )


def get_database():

    return database
