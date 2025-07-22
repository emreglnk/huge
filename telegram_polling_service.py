import os
import asyncio
import logging
import httpx
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from .telegram_webhook import TelegramWebhookHandler
from .db import get_database

logger = logging.getLogger(__name__)

class TelegramPollingService:
    """
    Telegram polling service using getUpdates API
    Similar to the PHP implementation provided by user
    """
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.enabled = bool(self.bot_token)
        self.webhook_handler = TelegramWebhookHandler()
        self.last_update_id = 0
        self.polling = False
        self.poll_interval = 2  # seconds
        
        if not self.enabled:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram polling disabled")
        else:
            logger.info("Telegram polling service initialized")
    
    async def start_polling(self):
        """Start the polling loop"""
        if not self.enabled:
            logger.warning("Cannot start polling: TELEGRAM_BOT_TOKEN not set")
            return
        
        self.polling = True
        logger.info("Starting Telegram polling...")
        
        # Load last update ID from database
        await self._load_last_update_id()
        
        while self.polling:
            try:
                await self._poll_updates()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in polling loop: {str(e)}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def stop_polling(self):
        """Stop the polling loop"""
        self.polling = False
        logger.info("Telegram polling stopped")
    
    async def _poll_updates(self):
        """Poll for new updates from Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 30,  # Long polling timeout
                "allowed_updates": ["message", "callback_query"]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=params,
                    timeout=35.0  # Slightly longer than Telegram timeout
                )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    updates = data.get("result", [])
                    await self._process_updates(updates)
                else:
                    logger.error(f"Telegram API error: {data.get('description', 'Unknown error')}")
            else:
                logger.error(f"HTTP error {response.status_code}: {response.text}")
                
        except httpx.TimeoutException:
            # Timeout is expected with long polling, just continue
            pass
        except Exception as e:
            logger.error(f"Error polling updates: {str(e)}")
    
    async def _process_updates(self, updates: List[Dict[str, Any]]):
        """Process received updates"""
        for update in updates:
            try:
                update_id = update.get("update_id")
                if update_id:
                    # Update last_update_id
                    if update_id > self.last_update_id:
                        self.last_update_id = update_id
                        await self._save_last_update_id()
                
                # Process the update using existing webhook handler
                response = await self.webhook_handler.process_update(update)
                
                # If there's a response, send it
                if response:
                    await self._send_response(response)
                    
                logger.debug(f"Processed update {update_id}")
                
            except Exception as e:
                logger.error(f"Error processing update {update.get('update_id', 'unknown')}: {str(e)}")
    
    async def _send_response(self, response: Dict[str, Any]):
        """Send response back to Telegram"""
        try:
            method = response.get("method", "sendMessage")
            
            if method == "sendMessage":
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                
                payload = {
                    "chat_id": response.get("chat_id"),
                    "text": response.get("text"),
                    "parse_mode": response.get("parse_mode", "Markdown")
                }
                
                async with httpx.AsyncClient() as client:
                    api_response = await client.post(
                        url,
                        json=payload,
                        timeout=30.0
                    )
                
                if api_response.status_code == 200:
                    logger.info(f"Message sent to chat {response.get('chat_id')}")
                else:
                    logger.error(f"Failed to send message: {api_response.status_code} - {api_response.text}")
            
        except Exception as e:
            logger.error(f"Error sending response: {str(e)}")
    
    async def _load_last_update_id(self):
        """Load last update ID from database"""
        try:
            db = await get_database()
            collection = db["telegram_polling"]
            
            doc = await collection.find_one({"service": "polling"})
            if doc:
                self.last_update_id = doc.get("last_update_id", 0)
                logger.info(f"Loaded last update ID: {self.last_update_id}")
            else:
                # Initialize document
                await collection.insert_one({
                    "service": "polling",
                    "last_update_id": 0,
                    "created_at": datetime.utcnow().isoformat()
                })
                logger.info("Initialized telegram polling document")
                
        except Exception as e:
            logger.error(f"Error loading last update ID: {str(e)}")
            self.last_update_id = 0
    
    async def _save_last_update_id(self):
        """Save last update ID to database"""
        try:
            db = await get_database()
            collection = db["telegram_polling"]
            
            await collection.update_one(
                {"service": "polling"},
                {
                    "$set": {
                        "last_update_id": self.last_update_id,
                        "updated_at": datetime.utcnow().isoformat()
                    }
                },
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error saving last update ID: {str(e)}")
    
    async def send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message directly (for scheduled messages)"""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                logger.info(f"Direct message sent to chat {chat_id}")
                return True
            else:
                logger.error(f"Failed to send direct message: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending direct message: {str(e)}")
            return False

# Global instance
telegram_polling_service = TelegramPollingService()
