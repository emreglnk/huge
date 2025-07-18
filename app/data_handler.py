from motor.motor_asyncio import AsyncIOMotorCollection

from .db import db
from .models import AgentModel

def get_user_data_collection(agent_config: AgentModel) -> AsyncIOMotorCollection:
    """
    Retrieves the specific MongoDB collection for an agent's user data.

    Args:
        agent_config: The agent's configuration object.

    Returns:
        An AsyncIOMotorCollection instance for the agent's data.
    """
    collection_name = agent_config.dataSchema.collectionName
    if not collection_name:
        raise ValueError("Agent's dataSchema must specify a collectionName")
    return db.get_collection(collection_name)
