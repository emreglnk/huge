 # 🤖 AI Agent Platform

Modern, ölçeklenebilir ve güvenli AI Agent yönetim platformu. **Agent Definition JSON** konsepti ile merkezi konfigürasyon yönetimi sağlar. FastAPI, MongoDB ve Docker ile geliştirilmiştir.

> 📋 **Roadmap Durumu**: Phase 1-4 tamamlandı. Sistem production-ready durumda.
> 📊 **Detaylı Mimari**: [Architecture Flow Diagram](./architecture-flow.md)

## ✨ Özellikler

### 🧠 Akıllı Master Agent
- **DeepSeek LLM** ile güçlendirilmiş agent oluşturma
- **Hardcoded fallback** ile hızlı yanıt garantisi
- **Server-Sent Events (SSE)** ile canlı streaming
- Kullanıcı ihtiyaçlarına göre otomatik agent konfigürasyonu

### 🔧 Agent Yönetimi
- **File-based storage** ile hızlı agent yönetimi
- **CRUD operasyonları** (Create, Read, Update, Delete)
- **Agent paylaşım sistemi** - Public marketplace
- **Workflow ve zamanlanmış görevler**

### 📱 Telegram Entegrasyonu
- **Proaktif mesajlaşma** desteği
- **Markdown formatı** ile zengin içerik
- **Zamanlanmış bildirimler**
- **Kullanıcı etkileşimi** takibi

### 🛡️ Güvenlik
- **JWT tabanlı authentication**
- **MongoDB şifre koruması**
- **Input validation ve sanitization**
- **Rate limiting ve timeout koruması**

### 🔄 Gelişmiş Araçlar
- **API calls** - HTTP istekleri
- **RSS feeds** - İçerik takibi  
- **Database operations** - MongoDB CRUD
- **Telegram messaging** - Bot entegrasyonu

## 🚀 Hızlı Başlangıç

### 1. Repository'yi Klonlayın
```bash
git clone <repository-url>
cd huge
```

### 2. Environment Değişkenlerini Ayarlayın
```bash
cp .env.example .env
# .env dosyasını düzenleyin:
# - TELEGRAM_BOT_TOKEN: @BotFather'dan alın
# - DEEPSEEK_API_KEY: DeepSeek API anahtarı
# - Diğer ayarları isteğe göre güncelleyin
```

### 3. Docker ile Başlatın
```bash
docker-compose up --build -d
```

### 4. Uygulamaya Erişin
- **Web UI**: http://localhost:8200
- **API Docs**: http://localhost:8200/docs
- **MongoDB**: localhost:27017 (admin/hugeMongo2024!)

## 📖 Kullanım Kılavuzu

### Kullanıcı Kaydı ve Giriş
1. http://localhost:8200 adresine gidin
2. "Register" ile yeni hesap oluşturun
3. Kullanıcı adı ve şifre ile giriş yapın

### Agent Oluşturma
1. **"Yeni Agent"** sekmesine gidin
2. İhtiyacınızı açıklayın (örn: "Todo agent oluştur")
3. Master Agent size özel konfigürasyon hazırlayacak
4. **"Evet"** diyerek agent'ı oluşturun

### Agent Paylaşımı
1. Agent listesinde **"Share"** butonuna tıklayın
2. Agent public marketplace'e eklenir
3. **"Public Agents"** sekmesinden diğer agent'ları keşfedin
4. **"Copy"** ile beğendiğiniz agent'ları kendi koleksiyonunuza ekleyin

### Telegram Entegrasyonu
1. @BotFather'dan bot token alın
2. `.env` dosyasına `TELEGRAM_BOT_TOKEN` ekleyin
3. Agent'ınızda Telegram tool'unu kullanın
4. Proaktif mesajlar ve bildirimler alın

## 🏗️ Mimari

### Agent Definition JSON Konsepti
Sistemde her agent, MongoDB'de saklanan kapsamlı bir JSON dokümaniyla tanımlanır:

```json
{
  "agentId": "dietitian_pro",
  "agentName": "Dietitian Pro", 
  "systemPrompt": "Expert dietitian providing personalized advice",
  "dataSchema": {
    "collectionName": "dietitian_user_data",
    "schema": {
      "measurements": { "type": "array" },
      "dietary_goals": { "type": "string" }
    }
  },
  "tools": [
    {
      "toolId": "recipe_api",
      "type": "API",
      "endpoint": "https://api.edamam.com/search"
    }
  ],
  "workflows": [
    {
      "workflowId": "weekly_checkin",
      "nodes": [
        { "type": "llm_prompt", "prompt": "Ask for weight update" },
        { "type": "data_store", "action": "append" },
        { "type": "conditional_logic", "condition": "weight_change > 2" },
        { "type": "send_response", "message": "Feedback" }
      ]
    }
  ],
  "schedules": [
    {
      "cron": "0 9 * * 1",
      "workflowId": "monday_motivation"
    }
  ]
}
```

### Sistem Mimarisi
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI       │    │   MongoDB       │
│   (Static)      │◄──►│   Backend       │◄──►│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Scheduler     │
                    │   (APScheduler) │
                    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   External      │
                    │   APIs/Services │
                    └─────────────────┘
```

## 📋 Roadmap Implementation Status

| Phase | Özellik | Durum | Açıklama |
|-------|---------|-------|----------|
| **Phase 1** | Core Engine & Master Agent | ✅ **Tamamlandı** | FastAPI, MongoDB, Master Agent UI |
| 1.1 | Backend Setup (FastAPI & MongoDB) | ✅ | Motor ile async MongoDB erişimi |
| 1.2 | Master Agent API | ✅ | CRUD endpoints için agents collection |
| 1.3 | Master Agent UI | ✅ | Agent oluşturma ve yönetim arayüzü |
| 1.4 | Agent Runtime Loader | ✅ | File-based agent loading system |
| **Phase 2** | Agent Execution & Dynamic Tooling | ✅ **Tamamlandı** | LLM integration, tools, data handling |
| 2.1 | Basic Chat Endpoint | ✅ | `/chat/{agentId}` endpoint |
| 2.2 | Dynamic Data Handling | ✅ | User-specific collections |
| 2.3 | Tool Execution Engine | ✅ | API, RSS, Database tools |
| **Phase 3** | Workflow Engine | ✅ **Tamamlandı** | Multi-step process execution |
| 3.1 | Workflow JSON Schema | ✅ | Node types: llm_prompt, data_store, tool_call, conditional_logic |
| 3.2 | Workflow Executor | ✅ | Step-by-step workflow interpretation |
| 3.3 | Trigger Mechanism | ✅ | Message-based workflow triggers |
| **Phase 4** | Scheduling & Deployment | ✅ **Tamamlandı** | Production-ready deployment |
| 4.1 | Scheduler Integration | ✅ | APScheduler ile cron jobs |
| 4.2 | Security and Scalability | ✅ | JWT auth, Docker containerization |
| 4.3 | Deployment | ✅ | Docker Compose, production MongoDB |

### 🚀 Ek Özellikler (Roadmap'in Ötesinde)
- **Telegram Integration**: Proaktif mesajlaşma ve webhook desteği
- **Smart Master Agent**: DeepSeek LLM ile gelişmiş agent oluşturma
- **Agent Sharing System**: Public marketplace
- **Session Management**: Kullanıcı oturum takibi
- **Comprehensive Logging**: Detaylı sistem logları

## 📁 Proje Yapısı

```
huge/
├── app/
│   ├── main.py              # FastAPI uygulaması
│   ├── models.py            # Pydantic modelleri
│   ├── auth.py              # Authentication
│   ├── tool_executor.py     # Tool çalıştırıcı
│   ├── smart_master_agent.py # Akıllı Master Agent
│   ├── file_agent_manager.py # Agent dosya yönetimi
│   ├── database_tool.py     # MongoDB araçları
│   └── static/              # Web UI
├── agents/                  # Agent JSON dosyaları
├── docker-compose.yml       # Container konfigürasyonu
├── requirements.txt         # Python bağımlılıkları
└── .env.example            # Environment değişkenleri
```

## 🔧 API Endpoints

### Authentication
- `POST /register` - Kullanıcı kaydı
- `POST /token` - Login ve token alma

### Agents
- `GET /agents` - Agent listesi
- `POST /agents` - Yeni agent oluştur
- `GET /agents/{id}` - Agent detayı
- `PUT /agents/{id}` - Agent güncelle
- `DELETE /agents/{id}` - Agent sil

### Agent Sharing
- `POST /agents/{id}/share` - Agent'ı public yap
- `GET /agents/public` - Public agent'ları listele
- `POST /agents/public/{id}/copy` - Public agent'ı kopyala

### Master Agent
- `POST /master-agent/conversation` - Master Agent sohbeti
- `POST /master-agent/stream` - Canlı streaming

### Chat
- `POST /chat/{agent_id}` - Agent ile sohbet
- `GET /chat/{agent_id}/history` - Sohbet geçmişi

## 🛠️ Geliştirme

### Local Development
```bash
# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Bağımlılıkları yükle
pip install -r requirements.txt

# MongoDB başlat (Docker ile)
docker run -d --name mongo -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=hugeMongo2024! \
  mongo:latest

# Uygulamayı başlat
uvicorn app.main:app --reload --port 8200
```

### Testing
```bash
# Unit testleri çalıştır
pytest

# Coverage raporu
pytest --cov=app --cov-report=html
```

## 📊 Örnek Agent: SmartDiet AI

Platform ile birlikte gelen örnek diyetisyen agent'ı:

- **Proaktif beslenme takibi**
- **Telegram bildirimleri**
- **Kişiselleştirilmiş planlar**
- **İlerleme raporları**
- **Motivasyon mesajları**

## 🤝 Katkıda Bulunma

1. Fork yapın
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'Add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. Pull Request oluşturun

## 📄 Lisans

Bu proje MIT lisansı altında lisanslanmıştır.

## 🆘 Destek

- **Issues**: GitHub Issues kullanın
- **Docs**: `/docs` endpoint'inde API dokümantasyonu
- **Logs**: `docker logs huge-api-1` ile hata ayıklama

---

**🎯 Hedef**: Herkesin kolayca AI agent'ları oluşturabileceği, paylaşabileceği ve yönetebileceği bir platform sunmak.