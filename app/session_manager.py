"""
Session management for agent conversations.
This module handles user session state across conversations with agents.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import logging
from motor.motor_asyncio import AsyncIOMotorCollection

from .db import session_collection, chat_history_collection
from .models import AgentModel

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions for agent interactions.
    
    This class provides methods for:
    - Creating and retrieving user sessions
    - Storing conversation history
    - Maintaining user context across multiple interactions
    """
    
    def __init__(self):
        self._sessions_collection: AsyncIOMotorCollection = session_collection
        self._history_collection: AsyncIOMotorCollection = chat_history_collection
    
    async def initialize(self):
        """Initialize database connections and create indexes."""
        logger.info("Initializing SessionManager and creating indexes...")
        await self._sessions_collection.create_index([("user_id", 1), ("agent_id", 1)])
        await self._history_collection.create_index([("session_id", 1), ("timestamp", 1)])
        logger.info("SessionManager initialized successfully.")
    
    async def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a session by its ID.
        
        Args:
            session_id: The unique identifier for the session.
            
        Returns:
            The session document or None if not found.
        """
        logger.info(f"Querying for session with session_id: '{session_id}'")
        session = await self._sessions_collection.find_one({"session_id": session_id})
        if session:
            logger.info(f"Found session: {session}")
        else:
            logger.warning(f"Session with session_id: '{session_id}' not found.")
        return session
    
    async def get_or_create_session(self, user_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Get an existing session or create a new one for a user and agent.
        
        Args:
            user_id: The unique identifier for the user.
            agent_id: The unique identifier for the agent.
            
        Returns:
            The session document.
        """
        # Try to find existing session
        session = await self._sessions_collection.find_one({
            "user_id": user_id,
            "agent_id": agent_id,
            "active": True
        })
        
        if session:
            return session
        
        # Create new session
        session_id = str(uuid.uuid4())
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "agent_id": agent_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "active": True,
            "context": {}
        }
        
        await self._sessions_collection.insert_one(session)
        logger.info(f"Created new session {session_id} for user {user_id} with agent {agent_id}")
        return session
    
    async def update_session_context(self, session_id: str, context_updates: Dict[str, Any]) -> None:
        """
        Update the context of a session.
        
        Args:
            session_id: The unique identifier for the session.
            context_updates: Dictionary of context variables to update.
        """
        await self._sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "last_activity": datetime.utcnow(),
                    **{f"context.{key}": value for key, value in context_updates.items()}
                }
            }
        )
    
    async def add_to_history(self, session_id: str, user_message: str, agent_response: str) -> None:
        """
        Add a message exchange to the conversation history.
        
        Args:
            session_id: The unique identifier for the session.
            user_message: The message sent by the user.
            agent_response: The response from the agent.
        """
        history_entry = {
            "session_id": session_id,
            "timestamp": datetime.utcnow(),
            "user_message": user_message,
            "agent_response": agent_response
        }
        
        await self._history_collection.insert_one(history_entry)
    
    async def list_sessions(self, agent_id: str = None, user_id: str = None) -> List[Dict[str, Any]]:
        """
        List all sessions, optionally filtered by agent_id or user_id.
        
        Args:
            agent_id: Optional filter by agent ID.
            user_id: Optional filter by user ID.
            
        Returns:
            List of session documents.
        """
        # Build the filter
        filter_query = {}
        if agent_id:
            filter_query["agent_id"] = agent_id
        if user_id:
            filter_query["user_id"] = user_id
        
        cursor = self._sessions_collection.find(filter_query)
        # Sort by last activity, most recent first
        cursor = cursor.sort("last_activity", -1)
        
        sessions = await cursor.to_list(length=100)  # Limit to 100 sessions max
        return sessions
    
    async def find_latest_session(self, user_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Find the most recent active session for a given user and agent.

        Args:
            user_id: The ID of the user.
            agent_id: The ID of the agent.

        Returns:
            The latest session document or None if not found.
        """
        query = {"user_id": user_id, "agent_id": agent_id, "active": True}
        logger.info(f"Finding latest session with query: {query}")
        session = await self._sessions_collection.find_one(query, sort=[("last_activity", -1)])
        if session:
            logger.info(f"Found latest session: {session['session_id']}")
        else:
            logger.info("No latest session found.")
        return session

    async def get_session_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the conversation history for a specific session.

        Args:
            session_id: The ID of the session.
            limit: Maximum number of history entries to return.

        Returns:
            List of conversation history entries, sorted from oldest to newest.
        """
        logger.info(f"Fetching history for session_id: '{session_id}', limit: {limit}")
        cursor = self._history_collection.find({"session_id": session_id})
        cursor = cursor.sort("timestamp", -1).limit(limit)
        history = await cursor.to_list(length=limit)
        logger.info(f"Found {len(history)} history entries for session_id: '{session_id}'.")
        # Reversing to show oldest first
        return list(reversed(history))
    
    async def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current context for a session.
        
        Args:
            session_id: The unique identifier for the session.
            
        Returns:
            The session context dictionary.
        """
        session = await self._sessions_collection.find_one({"session_id": session_id})
        if not session:
            return {}
        
        return session.get("context", {})
    
    async def end_session(self, session_id: str) -> None:
        """
        Mark a session as inactive.
        
        Args:
            session_id: The unique identifier for the session.
        """
        await self._sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"active": False}}
        )

# Global session manager instance
session_manager = SessionManager()
