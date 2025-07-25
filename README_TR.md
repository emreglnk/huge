# 🤖 AI Agent Platform - Türkçe Kullanım Kılavuzu

> **Çoklu AI Agent Yönetim Sistemi** - Telegram entegrasyonu ile güçlendirilmiş, modern web arayüzlü AI asistan platformu

## 📋 İçindekiler

- [Özellikler](#-özellikler)
- [Hızlı Başlangıç](#-hızlı-başlangıç)
- [Detaylı Kurulum](#-detaylı-kurulum)
- [Kullanım Kılavuzu](#-kullanım-kılavuzu)
- [Komutlar](#-komutlar)
- [Sorun Giderme](#-sorun-giderme)

## 🚀 Özellikler

- **🤖 Çoklu AI Agent Sistemi**: Farklı uzmanlık alanlarında AI asistanları
- **📱 Telegram Entegrasyonu**: Bot üzerinden mesajlaşma ve otomatik bildirimler
- **🌐 Modern Web Arayüzü**: Responsive ve kullanıcı dostu interface
- **⏰ Zamanlanmış Görevler**: Otomatik hatırlatmalar ve proaktif mesajlar
- **🔐 Güvenli Kimlik Doğrulama**: JWT tabanlı güvenlik sistemi
- **💾 MongoDB Entegrasyonu**: Sohbet geçmişi ve kullanıcı verilerinin güvenli saklanması

## ⚡ Hızlı Başlangıç

### 1. Projeyi İndirin
```bash
git clone <repository-url>
cd huge
```

### 2. Çevre Değişkenlerini Ayarlayın
```bash
cp .env.example .env
nano .env  # Gerekli API anahtarlarını girin
```

### 3. Uygulamayı Başlatın
```bash
docker-compose up -d
```

### 4. Erişim Sağlayın
- **Web Arayüzü**: http://localhost:8000
- **API Dokümantasyonu**: http://localhost:8000/docs

## 🛠 Detaylı Kurulum

### Sistem Gereksinimleri

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **RAM**: Minimum 2GB
- **Disk**: Minimum 5GB boş alan

### Adım Adım Kurulum

#### 1. Bağımlılıkları Kontrol Edin
```bash
# Docker kurulu mu?
docker --version
docker-compose --version

# Port 8000 boş mu?
netstat -tlnp | grep 8000
```

#### 2. Çevre Değişkenlerini Yapılandırın
```bash
# .env dosyasını düzenleyin
cp .env.example .env

# Gerekli değişkenleri ayarlayın:
# - TELEGRAM_BOT_TOKEN (BotFather'dan alın)
# - OPENAI_API_KEY (OpenAI'dan alın)
# - DEEPSEEK_API_KEY (DeepSeek'ten alın)
# - GEMINI_API_KEY (Google'dan alın)
```

#### 3. Uygulamayı Başlatın
```bash
# Arka planda çalıştır
docker-compose up -d

# Logları takip et
docker-compose logs -f

# Durum kontrolü
docker-compose ps
```

## 📖 Kullanım Kılavuzu

### Web Arayüzü Kullanımı

#### 1. Giriş Yapma
```
1. http://localhost:8000 adresine gidin
2. Varsayılan kullanıcı bilgileri:
   - Kullanıcı Adı: test
   - Şifre: test123
3. "Giriş Yap" butonuna tıklayın
```

#### 2. Agent Seçimi
```
1. Ana sayfada mevcut agent'ları görün
2. İstediğiniz uzmanlık alanındaki agent'ı seçin:
   - 🥗 Diyetisyen Agent
   - 🏥 Fizyoterapist Agent
   - 🧬 Moleküler Biyolog Agent
   - 🏥 Ortopedi Cerrah Agent
3. "Sohbet Et" butonuna tıklayın
```

#### 3. Sohbet Etme
```
1. Mesaj kutusuna sorunuzu yazın
2. Enter'a basın veya "Gönder" butonuna tıklayın
3. Agent'ın yanıtını bekleyin
4. Sohbet geçmişi otomatik olarak kaydedilir
```

### Telegram Bot Kullanımı

#### 1. Bot'u Başlatma
```
1. Telegram'da bot'unuzu bulun (@your_bot_username)
2. /start komutunu gönderin
3. Bot size hoş geldin mesajı gönderecek
```

#### 2. Agent ile Konuşma
```
1. /agents komutunu kullanarak mevcut agent'ları görün
2. /select_agent [agent_id] ile agent seçin
3. Doğrudan mesaj yazarak sohbet edin
```

## 💻 Komutlar

### Docker Yönetimi

```bash
# 🚀 Uygulamayı başlat
docker-compose up -d

# 🛑 Uygulamayı durdur
docker-compose down

# 🔄 Yeniden başlat
docker-compose restart

# 🏗️ Yeniden oluştur ve başlat
docker-compose up --build -d

# 📊 Durum kontrolü
docker-compose ps

# 📋 Logları görüntüle
docker-compose logs -f

# 🧹 Temizlik (dikkatli kullanın!)
docker-compose down -v  # Verileri de siler
```

### Log İzleme

```bash
# 📋 Tüm loglar
docker-compose logs

# 🔴 Sadece hatalar
docker-compose logs | grep ERROR

# 📱 Telegram logları
docker-compose logs api | grep telegram

# 🤖 Agent logları
docker-compose logs api | grep agent

# ⏰ Son 50 log
docker-compose logs --tail=50

# 🔄 Canlı takip
docker-compose logs -f api
```

### Veritabanı Yönetimi

```bash
# 🔗 MongoDB'ye bağlan
docker-compose exec db mongo -u admin -p hugeMongo2024!

# 📊 Veritabanı durumu
use autogen_db
show collections
db.stats()

# 👥 Kullanıcıları listele
db.users.find().pretty()

# 💬 Sohbet geçmişi
db.chat_history.find().limit(10).pretty()

# 🗑️ Koleksiyonu temizle (dikkatli!)
db.chat_history.deleteMany({})
```

## 🔧 Sorun Giderme

### Yaygın Sorunlar ve Çözümleri

#### 🚫 MongoDB Bağlantı Hatası
```bash
# Problemi tespit et
docker-compose ps db
docker-compose logs db

# Çözüm 1: Container'ı yeniden başlat
docker-compose restart db

# Çözüm 2: Port kontrolü
netstat -tlnp | grep 27017

# Çözüm 3: Şifre kontrolü
grep MONGODB_URI .env
```

#### 📱 Telegram Bot Çalışmıyor
```bash
# Token kontrolü
echo $TELEGRAM_BOT_TOKEN
grep TELEGRAM_BOT_TOKEN .env

# Bot durumu
curl -X GET "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"

# Logları kontrol et
docker-compose logs api | grep -i telegram
```

#### 🌐 Web Arayüzü Açılmıyor
```bash
# Port kontrolü
netstat -tlnp | grep 8000
lsof -i :8000

# Container durumu
docker-compose ps api
docker-compose logs api
```

#### 🤖 Agent'lar Yüklenmiyor
```bash
# JSON dosyalarını kontrol et
for file in agents/*.json; do
    echo "Checking $file:"
    python -m json.tool "$file" > /dev/null && echo "✅ Valid" || echo "❌ Invalid"
done

# Agent yükleme logları
docker-compose logs api | grep -i "agent.*load"
```

### Debug Modu

```bash
# Debug logları aktif et
export LOG_LEVEL=DEBUG
docker-compose up -d

# Detaylı loglar
docker-compose logs -f api | grep DEBUG

# Container'a bağlan
docker-compose exec api bash
```

## ⚙️ Konfigürasyon

### Çevre Değişkenleri (.env)

```env
# 🔐 Güvenlik
SECRET_KEY=super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 💾 Veritabanı
MONGODB_URI=mongodb://admin:hugeMongo2024!@db:27017/?authSource=admin

# 📱 Telegram
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# 🤖 AI Sağlayıcıları
OPENAI_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=AIza...
```

### Agent Konfigürasyonu

```json
{
  "owner": "test",
  "agentId": "my_custom_agent",
  "agentName": "Özel AI Asistanım",
  "version": "1.0",
  "systemPrompt": "Sen yardımcı bir AI asistanısın...",
  "llmConfig": {
    "provider": "openai",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "tools": [
    {
      "name": "telegram_mesaj_gonder",
      "description": "Telegram'a mesaj gönderir"
    }
  ],
  "scheduledTasks": [
    {
      "name": "gunluk_hatirlatma",
      "description": "Günlük hatırlatma mesajı",
      "schedule": "0 9 * * *",
      "enabled": true
    }
  ]
}
```

## 🔒 Güvenlik

### Güvenlik Kontrol Listesi

- ✅ `.env` dosyasında güçlü şifreler kullanın
- ✅ JWT secret key'i benzersiz yapın
- ✅ Üretim ortamında HTTPS kullanın
- ✅ Firewall kurallarını ayarlayın
- ✅ Düzenli yedekleme yapın
- ✅ Logları düzenli kontrol edin

### Yedekleme

```bash
# 💾 MongoDB yedekle
docker-compose exec db mongodump --out /backup
docker cp huge-db-1:/backup ./backup

# 📁 Agent dosyalarını yedekle
cp -r agents/ ./backup/

# 🔄 Veritabanını geri yükle
docker-compose exec db mongorestore /backup/autogen_db
```

## 📞 Destek

### Yardım Alma

- 📧 **E-posta**: support@example.com
- 💬 **GitHub Issues**: Teknik sorunlar için
- 📱 **Telegram**: @support_bot

---

**Not**: Bu dokümantasyon sürekli güncellenmektedir. En son sürüm için GitHub repository'sini kontrol edin.
