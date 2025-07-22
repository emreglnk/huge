#!/usr/bin/env python3
"""
Telegram Bot Test Script
Bu script Telegram bot'unun çalışıp çalışmadığını test eder.
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_telegram_bot():
    """Test Telegram bot functionality"""
    
    # Get bot token from environment
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN environment variable not set!")
        print("   .env dosyasına bot token'ınızı ekleyin:")
        print("   TELEGRAM_BOT_TOKEN=your_bot_token_here")
        return False
    
    print(f"✅ Bot token found: {bot_token[:10]}...{bot_token[-10:]}")
    
    # Test bot info
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
            if response.status_code == 200:
                bot_info = response.json()
                print(f"✅ Bot info: {bot_info['result']['first_name']} (@{bot_info['result']['username']})")
            else:
                print(f"❌ Bot token invalid: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Error getting bot info: {e}")
        return False
    
    # Get updates to find chat IDs
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://api.telegram.org/bot{bot_token}/getUpdates")
            if response.status_code == 200:
                updates = response.json()
                if updates['result']:
                    print("📨 Recent chats:")
                    for update in updates['result'][-5:]:  # Last 5 updates
                        if 'message' in update:
                            chat = update['message']['chat']
                            print(f"   Chat ID: {chat['id']} - {chat.get('first_name', 'Unknown')}")
                    
                    # Ask user for chat ID to test
                    print("\n🔧 Test mesajı göndermek için:")
                    print("1. Yukarıdaki chat ID'lerden birini seçin")
                    print("2. Veya botunuza /start mesajı gönderin ve scripti tekrar çalıştırın")
                    
                    chat_id = input("\nTest için Chat ID girin (Enter = skip): ").strip()
                    if chat_id:
                        # Send test message
                        test_message = "🤖 **Test Mesajı**\n\nTelegram bot başarıyla çalışıyor! ✅"
                        payload = {
                            "chat_id": chat_id,
                            "text": test_message,
                            "parse_mode": "Markdown"
                        }
                        
                        response = await client.post(
                            f"https://api.telegram.org/bot{bot_token}/sendMessage",
                            json=payload
                        )
                        
                        if response.status_code == 200:
                            print("✅ Test mesajı başarıyla gönderildi!")
                            return True
                        else:
                            print(f"❌ Mesaj gönderilemedi: {response.status_code} - {response.text}")
                            return False
                else:
                    print("📭 Henüz mesaj alınmamış. Botunuza /start mesajı gönderin.")
            else:
                print(f"❌ Updates alınamadı: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Error testing bot: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Telegram Bot Test Script")
    print("=" * 40)
    
    result = asyncio.run(test_telegram_bot())
    
    if result:
        print("\n🎉 Telegram bot test başarılı!")
        print("   Artık diyetisyen agent'ı size mesaj gönderebilir.")
    else:
        print("\n❌ Test başarısız. Lütfen bot token'ınızı kontrol edin.") 