"""
Telegram Authentication Manager
Manages user-telegram chat ID mapping and authentication codes
"""
import secrets
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from .database_tool import get_database
from .models import TelegramAuth
import logging

logger = logging.getLogger(__name__)

class TelegramAuthManager:
    def __init__(self):
        self.collection_name = "telegram_auth"
        self._db = None
    
    async def get_database(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self._db is None:
            self._db = get_database()
        return self._db
    
    def generate_auth_code(self, length: int = 8) -> str:
        """Generate a unique authentication code"""
        # Use uppercase letters and numbers for easy typing
        chars = string.ascii_uppercase + string.digits
        # Avoid confusing characters like 0, O, I, 1
        chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('1', '')
        return ''.join(secrets.choice(chars) for _ in range(length))
    
    async def create_auth_request(self, user_id: str) -> str:
        """Create a new authentication request and return the auth code"""
        try:
            db = await self.get_database()
            collection = db[self.collection_name]
            
            # Generate unique auth code
            auth_code = self.generate_auth_code()
            
            # Check if code already exists (very unlikely but let's be safe)
            existing = await collection.find_one({"auth_code": auth_code, "is_verified": False})
            while existing:
                auth_code = self.generate_auth_code()
                existing = await collection.find_one({"auth_code": auth_code, "is_verified": False})
            
            # Remove any existing unverified requests for this user
            await collection.delete_many({
                "user_id": user_id,
                "is_verified": False
            })
            
            # Create new auth request
            auth_request = TelegramAuth(
                user_id=user_id,
                chat_id="",  # Will be filled when user sends the code
                auth_code=auth_code,
                is_verified=False,
                created_at=datetime.utcnow().isoformat()
            )
            
            await collection.insert_one(auth_request.dict())
            
            logger.info(f"Created auth request for user {user_id} with code {auth_code}")
            return auth_code
            
        except Exception as e:
            logger.error(f"Error creating auth request: {str(e)}")
            raise
    
    async def verify_auth_code(self, auth_code: str, chat_id: str) -> Optional[str]:
        """Verify authentication code and link chat_id to user"""
        try:
            logger.info(f"Attempting to verify auth code: {auth_code} for chat_id: {chat_id}")
            db = await self.get_database()
            collection = db[self.collection_name]
            
            # Find the auth request
            auth_request = await collection.find_one({
                "auth_code": auth_code,
                "is_verified": False
            })
            
            logger.info(f"Found auth request: {auth_request}")
            
            if not auth_request:
                logger.warning(f"Invalid or expired auth code: {auth_code}")
                # Also check if there's any auth request with this code (even if verified)
                any_request = await collection.find_one({"auth_code": auth_code})
                logger.info(f"Any request with this code: {any_request}")
                return None
            
            # Check if code is expired (valid for 10 minutes)
            created_at_str = auth_request["created_at"]
            if isinstance(created_at_str, str):
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            else:
                created_at = created_at_str
            
            time_diff = datetime.utcnow() - created_at.replace(tzinfo=None)
            logger.info(f"Time difference: {time_diff}, Max allowed: 10 minutes")
            
            if time_diff > timedelta(minutes=10):
                logger.warning(f"Expired auth code: {auth_code}, created {time_diff} ago")
                await collection.delete_one({"auth_code": auth_code})
                return None
            
            # Update the auth request with chat_id and mark as verified
            update_result = await collection.update_one(
                {"auth_code": auth_code},
                {
                    "$set": {
                        "chat_id": str(chat_id),
                        "is_verified": True,
                        "verified_at": datetime.utcnow().isoformat()
                    }
                }
            )
            
            logger.info(f"Update result: matched={update_result.matched_count}, modified={update_result.modified_count}")
            
            user_id = auth_request["user_id"]
            logger.info(f"Successfully verified auth code {auth_code} for user {user_id} with chat_id {chat_id}")
            
            # Verify the update was successful
            updated_record = await collection.find_one({"auth_code": auth_code})
            logger.info(f"Updated record: {updated_record}")
            
            return user_id
            
        except Exception as e:
            logger.error(f"Error verifying auth code: {str(e)}", exc_info=True)
            return None
    
    async def get_chat_id_for_user(self, user_id: str) -> Optional[str]:
        """Get Telegram chat ID for a user"""
        try:
            db = await self.get_database()
            collection = db[self.collection_name]
            
            auth_record = await collection.find_one({
                "user_id": user_id,
                "is_verified": True
            })
            
            if auth_record:
                return auth_record["chat_id"]
            return None
            
        except Exception as e:
            logger.error(f"Error getting chat ID for user {user_id}: {str(e)}")
            return None
    
    async def get_user_for_chat_id(self, chat_id: str) -> Optional[str]:
        """Get user ID for a Telegram chat ID"""
        try:
            db = await self.get_database()
            collection = db[self.collection_name]
            
            auth_record = await collection.find_one({
                "chat_id": str(chat_id),
                "is_verified": True
            })
            
            if auth_record:
                return auth_record["user_id"]
            return None
            
        except Exception as e:
            logger.error(f"Error getting user for chat_id {chat_id}: {str(e)}")
            return None
    
    async def revoke_telegram_auth(self, user_id: str) -> bool:
        """Revoke Telegram authentication for a user"""
        try:
            db = await self.get_database()
            collection = db[self.collection_name]
            
            result = await collection.delete_many({"user_id": user_id})
            
            logger.info(f"Revoked Telegram auth for user {user_id}, deleted {result.deleted_count} records")
            return result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Error revoking telegram auth for user {user_id}: {str(e)}")
            return False
    
    async def cleanup_expired_codes(self):
        """Clean up expired authentication codes"""
        try:
            db = await self.get_database()
            collection = db[self.collection_name]
            
            # Delete codes older than 10 minutes
            cutoff_time = datetime.utcnow() - timedelta(minutes=10)
            
            result = await collection.delete_many({
                "is_verified": False,
                "created_at": {"$lt": cutoff_time.isoformat()}
            })
            
            if result.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} expired auth codes")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired codes: {str(e)}")

# Global instance
telegram_auth_manager = TelegramAuthManager() 