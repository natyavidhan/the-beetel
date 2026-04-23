"""
MongoDB connection via Motor (async driver).
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

logger = logging.getLogger("beetel")

client: AsyncIOMotorClient = None  # type: ignore
db = None


async def connect_db():
    """Open MongoDB connection and create indexes."""
    global client, db
    client = AsyncIOMotorClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5000,
    )
    db = client[settings.DB_NAME]

    # Ensure dial_code is unique — gracefully handle missing DB
    try:
        await db.songs.create_index("dial_code", unique=True)
        logger.info("Connected to MongoDB ✓")
    except Exception as e:
        logger.warning(f"MongoDB not reachable — starting anyway: {e}")


async def close_db():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()


def get_db():
    """Return the database handle."""
    return db
