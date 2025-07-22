# 🏗️ AI Agent Platform - Detaylı Akış Diyagramı

## Ana Sistem Akışı

```mermaid
graph TB
    subgraph "Client Layer"
        UI[Web UI - React/HTML]
        TG[Telegram Client]
        API_CLIENT[API Clients]
    end

    subgraph "FastAPI Backend"
        MAIN[main.py - FastAPI App]
        AUTH[auth.py - JWT Authentication]
        
        subgraph "Core Modules"
            AGENT_LOADER[agent_loader.py]
            FILE_MGR[file_agent_manager.py]
            SESSION_MGR[session_manager.py]
            MASTER_AGENT[master_agent.py]
            SMART_MASTER[smart_master_agent.py]
        end
        
        subgraph "Execution Engines"
            WORKFLOW_ENGINE[workflow_engine.py]
            TOOL_EXECUTOR[tool_executor.py]
            SCHEDULER[scheduler.py - APScheduler]
        end
        
        subgraph "External Integrations"
            LLM_HANDLER[llm_handler.py - DeepSeek]
            TG_AUTH[telegram_auth_manager.py]
            TG_WEBHOOK[telegram_webhook.py]
        end
    end

    subgraph "Data Layer"
        MONGODB[(MongoDB Atlas)]
        FILESTORE[File-based Agent Storage]
        SQLITE[(SQLite - Local Cache)]
    end

    subgraph "External Services"
        DEEPSEEK[DeepSeek LLM API]
        TELEGRAM[Telegram Bot API]
        EXTERNAL_APIS[External APIs/RSS]
    end

    %% Client Connections
    UI --> MAIN
    TG --> TG_WEBHOOK
    API_CLIENT --> MAIN

    %% Authentication Flow
    MAIN --> AUTH
    AUTH --> SESSION_MGR

    %% Agent Management Flow
    MAIN --> AGENT_LOADER
    AGENT_LOADER --> FILE_MGR
    FILE_MGR --> FILESTORE

    %% Master Agent Flow
    MAIN --> SMART_MASTER
    SMART_MASTER --> LLM_HANDLER
    LLM_HANDLER --> DEEPSEEK

    %% Workflow Execution Flow
    MAIN --> WORKFLOW_ENGINE
    WORKFLOW_ENGINE --> TOOL_EXECUTOR
    TOOL_EXECUTOR --> EXTERNAL_APIS

    %% Scheduling Flow
    SCHEDULER --> WORKFLOW_ENGINE
    SCHEDULER --> TG_AUTH
    TG_AUTH --> TELEGRAM

    %% Data Storage
    MAIN --> MONGODB
    SESSION_MGR --> SQLITE
    FILE_MGR --> FILESTORE

    %% Telegram Integration
    TG_WEBHOOK --> TG_AUTH
    TG_AUTH --> MAIN
```

## Agent Yaşam Döngüsü Akışı

```mermaid
sequenceDiagram
    participant User
    participant UI
    participant MasterAgent
    participant DeepSeek
    participant FileManager
    participant WorkflowEngine
    participant ToolExecutor

    User->>UI: "Todo agent oluştur"
    UI->>MasterAgent: process_smart_conversation()
    MasterAgent->>DeepSeek: Prompt + Requirements
    DeepSeek-->>MasterAgent: Agent Configuration JSON
    MasterAgent-->>UI: Suggested Agent Config
    User->>UI: Approve Agent
    UI->>FileManager: save_agent()
    FileManager->>FileSystem: Store agent.json
    
    Note over FileManager: Agent Created Successfully
    
    User->>UI: Chat with Agent
    UI->>WorkflowEngine: execute_workflow()
    WorkflowEngine->>ToolExecutor: execute_tool()
    ToolExecutor->>External APIs: API Calls
    External APIs-->>ToolExecutor: Response
    ToolExecutor-->>WorkflowEngine: Tool Result
    WorkflowEngine-->>UI: Final Response
    UI-->>User: Agent Response
```

## Workflow Execution Akışı

```mermaid
flowchart TD
    START([Workflow Başlangıç]) --> LOAD_AGENT[Agent Config Yükle]
    LOAD_AGENT --> PARSE_WF[Workflow Parse Et]
    PARSE_WF --> INIT_CONTEXT[Context Initialize]
    INIT_CONTEXT --> PROCESS_NODE{Node İşle}
    
    PROCESS_NODE --> LLM_NODE[LLM Prompt Node]
    PROCESS_NODE --> TOOL_NODE[Tool Execution Node]
    PROCESS_NODE --> DATA_NODE[Data Store Node]
    PROCESS_NODE --> COND_NODE[Conditional Node]
    
    LLM_NODE --> LLM_CALL[DeepSeek API Call]
    LLM_CALL --> UPDATE_CTX[Context Güncelle]
    
    TOOL_NODE --> EXEC_TOOL[Tool Execute]
    EXEC_TOOL --> API_CALL[External API/RSS]
    API_CALL --> UPDATE_CTX
    
    DATA_NODE --> DB_OP[MongoDB Operation]
    DB_OP --> UPDATE_CTX
    
    COND_NODE --> EVAL_COND{Condition Check}
    EVAL_COND -->|True| BRANCH_A[Node A'ya git]
    EVAL_COND -->|False| BRANCH_B[Node B'ye git]
    BRANCH_A --> UPDATE_CTX
    BRANCH_B --> UPDATE_CTX
    
    UPDATE_CTX --> NEXT_NODE{Sonraki Node?}
    NEXT_NODE -->|Var| PROCESS_NODE
    NEXT_NODE -->|Yok| SEND_RESPONSE[Response Gönder]
    SEND_RESPONSE --> END([Workflow Bitiş])
    
    %% Error Handling
    LLM_CALL -->|Error| RETRY{Retry?}
    EXEC_TOOL -->|Error| RETRY
    DB_OP -->|Error| RETRY
    RETRY -->|Yes| PROCESS_NODE
    RETRY -->|No| ERROR_HANDLE[Error Response]
    ERROR_HANDLE --> END
```

## Scheduling System Akışı

```mermaid
graph LR
    subgraph "Scheduler Engine"
        CRON[Cron Jobs]
        APSCHEDULER[APScheduler]
    end
    
    subgraph "Agent Configs"
        AGENT1[Agent 1 - Schedule Config]
        AGENT2[Agent 2 - Schedule Config] 
        AGENT3[Agent 3 - Schedule Config]
    end
    
    subgraph "Execution"
        WF_ENGINE[Workflow Engine]
        TG_NOTIFY[Telegram Notifications]
        EMAIL_NOTIFY[Email Notifications]
    end
    
    AGENT1 --> APSCHEDULER
    AGENT2 --> APSCHEDULER
    AGENT3 --> APSCHEDULER
    
    APSCHEDULER --> WF_ENGINE
    WF_ENGINE --> TG_NOTIFY
    WF_ENGINE --> EMAIL_NOTIFY
    
    CRON --> APSCHEDULER
```

## Data Flow Diyagramı

```mermaid
graph TB
    subgraph "Input Sources"
        USER_INPUT[User Messages]
        SCHEDULED[Scheduled Tasks]
        WEBHOOK[Webhook Events]
    end
    
    subgraph "Processing Layer"
        SESSION[Session Management]
        VALIDATION[Input Validation]
        ROUTING[Request Routing]
    end
    
    subgraph "Business Logic"
        AGENT_LOGIC[Agent Processing]
        WORKFLOW[Workflow Execution]
        TOOL_EXEC[Tool Execution]
    end
    
    subgraph "Storage Layer"
        AGENT_STORE[(Agent Configs)]
        SESSION_STORE[(Session Data)]
        USER_DATA[(User Collections)]
        LOGS[(Execution Logs)]
    end
    
    subgraph "Output Channels"
        WEB_RESPONSE[Web Response]
        TG_MESSAGE[Telegram Message]
        API_RESPONSE[API Response]
    end
    
    USER_INPUT --> SESSION
    SCHEDULED --> ROUTING
    WEBHOOK --> VALIDATION
    
    SESSION --> ROUTING
    VALIDATION --> ROUTING
    ROUTING --> AGENT_LOGIC
    
    AGENT_LOGIC --> WORKFLOW
    WORKFLOW --> TOOL_EXEC
    
    AGENT_LOGIC <--> AGENT_STORE
    WORKFLOW <--> USER_DATA
    TOOL_EXEC --> LOGS
    
    AGENT_LOGIC --> WEB_RESPONSE
    WORKFLOW --> TG_MESSAGE
    TOOL_EXEC --> API_RESPONSE
```

## Security & Authentication Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant JWT_Auth
    participant MongoDB
    participant Session_Mgr

    Client->>FastAPI: Login Request
    FastAPI->>MongoDB: Verify Credentials
    MongoDB-->>FastAPI: User Data
    FastAPI->>JWT_Auth: Create Token
    JWT_Auth-->>FastAPI: JWT Token
    FastAPI->>Session_Mgr: Create Session
    Session_Mgr-->>FastAPI: Session ID
    FastAPI-->>Client: Token + Session

    Note over Client: Subsequent Requests

    Client->>FastAPI: API Request + JWT
    FastAPI->>JWT_Auth: Validate Token
    JWT_Auth-->>FastAPI: Token Valid
    FastAPI->>Session_Mgr: Get Session
    Session_Mgr-->>FastAPI: Session Data
    FastAPI-->>Client: Authorized Response
```
