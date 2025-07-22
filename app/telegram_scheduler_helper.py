import os
import asyncio
import logging
import httpx
from typing import Optional, Dict, Any
from datetime import datetime

from .telegram_auth_manager import telegram_auth_manager

logger = logging.getLogger(__name__)

class TelegramSchedulerHelper:
    """Helper class for sending scheduled Telegram messages"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.enabled = bool(self.bot_token)
        
        if not self.enabled:
            logger.warning("TELEGRAM_BOT_TOKEN not set, Telegram scheduler disabled")
    
    async def send_scheduled_message(self, user_id: str, message: str, agent_name: str = None) -> bool:
        """
        Send a scheduled message to a user via Telegram
        
        Args:
            user_id: The user ID to send message to
            message: The message content
            agent_name: Optional agent name for context
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Telegram not enabled, cannot send message to user {user_id}")
            return False
        
        try:
            # Get chat_id for user
            chat_id = await telegram_auth_manager.get_chat_id_for_user(user_id)
            if not chat_id:
                logger.warning(f"No Telegram chat_id found for user {user_id}")
                return False
            
            # Format message with agent context
            if agent_name:
                formatted_message = f"🤖 **{agent_name}**\n\n{message}"
            else:
                formatted_message = f"🤖 **AI Agent**\n\n{message}"
            
            # Send message via Telegram API
            success = await self._send_telegram_message(chat_id, formatted_message)
            
            if success:
                logger.info(f"Scheduled message sent to user {user_id} (chat_id: {chat_id})")
            else:
                logger.error(f"Failed to send scheduled message to user {user_id}")
                
            return success
            
        except Exception as e:
            logger.error(f"Error sending scheduled message to user {user_id}: {str(e)}")
            return False
    
    async def _send_telegram_message(self, chat_id: str, message: str) -> bool:
        """
        Send message via Telegram Bot API
        
        Args:
            chat_id: Telegram chat ID
            message: Message content
            
        Returns:
            bool: True if sent successfully
        """
        try:
            telegram_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    telegram_url,
                    json=payload,
                    timeout=30.0
                )
            
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except httpx.TimeoutException:
            logger.error(f"Timeout sending Telegram message to {chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {str(e)}")
            return False
    
    async def send_agent_notification(self, user_id: str, agent_id: str, notification_type: str, data: Dict[str, Any]) -> bool:
        """
        Send agent-specific notifications to user
        
        Args:
            user_id: User ID
            agent_id: Agent ID
            notification_type: Type of notification (daily_report, reminder, alert, etc.)
            data: Additional data for the notification
            
        Returns:
            bool: Success status
        """
        if not self.enabled:
            return False
        
        try:
            # Generate message based on notification type
            message = self._generate_notification_message(notification_type, data)
            agent_name = data.get('agent_name', agent_id)
            
            return await self.send_scheduled_message(user_id, message, agent_name)
            
        except Exception as e:
            logger.error(f"Error sending agent notification: {str(e)}")
            return False
    
    def _generate_notification_message(self, notification_type: str, data: Dict[str, Any]) -> str:
        """Generate notification message based on type and data"""
        
        messages = {
            'daily_report': f"📊 **Günlük Rapor**\n\n{data.get('report', 'Günlük aktivite raporu hazır!')}",
            'reminder': f"⏰ **Hatırlatma**\n\n{data.get('reminder_text', 'Size bir hatırlatma!')}",
            'alert': f"🚨 **Uyarı**\n\n{data.get('alert_text', 'Dikkat gerektiren bir durum var!')}",
            'weekly_summary': f"📈 **Haftalık Özet**\n\n{data.get('summary', 'Haftalık performans özeti hazır!')}",
            'goal_achieved': f"🎉 **Hedef Başarıldı!**\n\n{data.get('achievement', 'Tebrikler! Bir hedefinizi başardınız!')}",
            'diet_reminder': f"🥗 **Beslenme Hatırlatması**\n\n{data.get('diet_message', 'Sağlıklı beslenme zamanı!')}",
            'workout_reminder': f"💪 **Egzersiz Hatırlatması**\n\n{data.get('workout_message', 'Hareket zamanı!')}"
        }
        
        return messages.get(notification_type, f"📱 **Bildirim**\n\n{data.get('message', 'Yeni bir bildiriminiz var!')}")

# Global instance
telegram_scheduler_helper = TelegramSchedulerHelper()
