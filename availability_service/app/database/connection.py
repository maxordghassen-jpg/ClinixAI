from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.logger import get_logger


logger = get_logger(__name__)


class MongoDB:

    client: AsyncIOMotorClient = None


mongodb = MongoDB()


async def connect_to_mongo():

    try:

        mongodb.client = AsyncIOMotorClient(
            settings.MONGODB_URI
        )

        logger.info("Connected to MongoDB")

    except Exception as e:

        logger.error(
            f"MongoDB connection failed: {str(e)}"
        )

        raise e


async def close_mongo_connection():

    if mongodb.client:

        mongodb.client.close()

        logger.info(
            "MongoDB connection closed"
        )


def get_database():

    return mongodb.client[
        settings.DATABASE_NAME
    ]