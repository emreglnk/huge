import os
import sys
import logging
from motor.motor_asyncio import AsyncIOMotorClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Real MongoDB connection
    MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://db:27017")
    client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)

    # Ping to check if the connection is valid
    client.admin.command('ping')
    logger.info(f"Successfully connected to MongoDB at {MONGODB_URI}")

    db = client.get_database("autogen_db")

    agent_collection = db.get_collection("agents")
    session_collection = db.get_collection("sessions")
    chat_history_collection = db.get_collection("chat_history")

except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {e}")
    sys.exit(1)

def close_db_client():
    """Closes the MongoDB client connection."""
    client.close()
    logger.info("MongoDB connection closed.")

