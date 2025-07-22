"""
Telegram Webhook Handler
Processes incoming messages from Telegram bot
"""
import os
import re
import logging
from typing import Dict, Any, Optional
from .telegram_auth_manager import telegram_auth_manager
from .models import TelegramAuth

logger = logging.getLogger(__name__)

class TelegramWebhookHandler:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, webhook handler disabled")
    
    async def process_update(self, update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process incoming Telegram update"""
        try:
            if 'message' not in update:
                return None
            
            message = update['message']
            chat_id = str(message['chat']['id'])
            text = message.get('text', '').strip()
            
            # Check if message is an auth code (8 characters, uppercase letters and numbers)
            if self._is_auth_code(text):
                return await self._handle_auth_code(chat_id, text, message)
            
            # Handle other commands
            if text.startswith('/start'):
                return await self._handle_start_command(chat_id, message)
            
            elif text.startswith('/help'):
                return await self._handle_help_command(chat_id, message)
            
            elif text.startswith('/status'):
                return await self._handle_status_command(chat_id, message)
            
            # If user is registered, this could be a regular conversation
            # For now, we'll just acknowledge the message
            user_id = await telegram_auth_manager.get_user_for_chat_id(chat_id)
            if user_id:
                return {
                    "method": "sendMessage",
                    "chat_id": chat_id,
                    "text": f"Mesajınızı aldım! Platformdaki agent'larınız size zamanlanmış mesajlar gönderecek. 🤖"
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing Telegram update: {str(e)}")
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "Bir hata oluştu. Lütfen daha sonra tekrar deneyin."
            }
    
    def _is_auth_code(self, text: str) -> bool:
        """Check if text looks like an auth code"""
        return bool(re.match(r'^[A-Z2-9]{8}$', text))
    
    async def _handle_auth_code(self, chat_id: str, auth_code: str, message: Dict) -> Dict[str, Any]:
        """Handle authentication code from user"""
        user_id = await telegram_auth_manager.verify_auth_code(auth_code, chat_id)
        
        if user_id:
            user_name = message['from'].get('first_name', 'Kullanıcı')
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"🎉 Harika {user_name}! Telegram hesabınız başarıyla bağlandı.\n\n"
                       f"Artık AI agent'larınız size otomatik mesajlar gönderebilir. "
                       f"Diyetisyen agent'ınız size günlük beslenme takibi, haftalık raporlar ve motivasyon mesajları gönderecek.\n\n"
                       f"📱 Platform: http://dev.iyi.im:8200\n"
                       f"🤖 Agent'larınızla sohbet edebilir ve yeni agent'lar oluşturabilirsiniz!",
                "parse_mode": "Markdown"
            }
        else:
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": "❌ Geçersiz veya süresi dolmuş kod!\n\n"
                       "Lütfen platformdan yeni bir kod alın ve 10 dakika içinde gönderin.\n"
                       "Kod 8 haneli olmalı (örn: ABC123XY)",
                "parse_mode": "Markdown"
            }
    
    async def _handle_start_command(self, chat_id: str, message: Dict) -> Dict[str, Any]:
        """Handle /start command"""
        user_name = message['from'].get('first_name', 'Kullanıcı')
        
        # Check if user is already registered
        user_id = await telegram_auth_manager.get_user_for_chat_id(chat_id)
        if user_id:
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"👋 Merhaba {user_name}!\n\n"
                       f"Telegram hesabınız zaten bağlı. AI agent'larınız size otomatik mesajlar gönderebilir.\n\n"
                       f"📱 Platform: http://dev.iyi.im:8200",
                "parse_mode": "Markdown"
            }
        
        return {
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": f"👋 Merhaba {user_name}! AI Agent Platform Telegram Bot'una hoş geldiniz!\n\n"
                   f"🔗 **Hesap Bağlama:**\n"
                   f"1. http://dev.iyi.im:8200 adresine gidin\n"
                   f"2. Giriş yapın veya kayıt olun\n"
                   f"3. 'Telegram Bağla' butonuna tıklayın\n"
                   f"4. Size verilen 8 haneli kodu buraya gönderin\n\n"
                   f"🤖 **Ne Yapabilir:**\n"
                   f"• Diyetisyen agent'ınız günlük beslenme takibi yapar\n"
                   f"• Haftalık ilerleme raporları gönderir\n"
                   f"• Motivasyon mesajları ve ipuçları paylaşır\n"
                   f"• Diğer agent'larınız da size otomatik mesajlar gönderebilir\n\n"
                   f"❓ Yardım için: /help",
            "parse_mode": "Markdown"
        }
    
    async def _handle_help_command(self, chat_id: str, message: Dict) -> Dict[str, Any]:
        """Handle /help command"""
        return {
            "method": "sendMessage",
            "chat_id": chat_id,
            "text": "🆘 **Yardım**\n\n"
                   "**Komutlar:**\n"
                   "• /start - Bot'u başlat\n"
                   "• /help - Bu yardım mesajı\n"
                   "• /status - Bağlantı durumu\n\n"
                   "**Hesap Bağlama:**\n"
                   "1. Platform'a giriş yapın: http://dev.iyi.im:8200\n"
                   "2. 'Telegram Bağla' butonuna tıklayın\n"
                   "3. 8 haneli kodu buraya gönderin\n\n"
                   "**Sorun mu var?**\n"
                   "• Kodun 8 haneli olduğundan emin olun\n"
                   "• Kodu 10 dakika içinde gönderin\n"
                   "• Büyük harflerle yazın (ABC123XY gibi)",
            "parse_mode": "Markdown"
        }
    
    async def _handle_status_command(self, chat_id: str, message: Dict) -> Dict[str, Any]:
        """Handle /status command"""
        user_id = await telegram_auth_manager.get_user_for_chat_id(chat_id)
        
        if user_id:
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"✅ **Bağlantı Durumu: Aktif**\n\n"
                       f"👤 Kullanıcı ID: `{user_id}`\n"
                       f"💬 Chat ID: `{chat_id}`\n\n"
                       f"🤖 AI agent'larınız size mesaj gönderebilir.\n"
                       f"📱 Platform: http://dev.iyi.im:8200",
                "parse_mode": "Markdown"
            }
        else:
            return {
                "method": "sendMessage",
                "chat_id": chat_id,
                "text": f"❌ **Bağlantı Durumu: Bağlı Değil**\n\n"
                       f"Telegram hesabınızı bağlamak için:\n"
                       f"1. http://dev.iyi.im:8200 adresine gidin\n"
                       f"2. 'Telegram Bağla' butonuna tıklayın\n"
                       f"3. Size verilen kodu buraya gönderin\n\n"
                       f"Yardım için: /help",
                "parse_mode": "Markdown"
            }

# Global instance
telegram_webhook_handler = TelegramWebhookHandler() 