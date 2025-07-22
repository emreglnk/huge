import json
import uuid
import logging
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field

from .models import AgentModel, LlmConfig, Tool, Workflow, WorkflowNode, Schedule, DataSchema
from .llm_handler import get_llm_response
import asyncio

logger = logging.getLogger(__name__)

class SmartMasterAgentState(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[Dict[str, str]] = []
    user_requirements: str = ""
    agent_config: Optional[Dict[str, Any]] = None
    completed: bool = False
    current_phase: str = "gathering_requirements"  # gathering_requirements, analyzing, generating, confirming

# Store active conversations
smart_conversations: Dict[str, SmartMasterAgentState] = {}

# DeepSeek configuration for Master Agent
MASTER_AGENT_LLM_CONFIG = LlmConfig(
    provider="deepseek",
    model="deepseek-chat"
)

MASTER_AGENT_SYSTEM_PROMPT = """Sen bir uzman AI Agent tasarımcısısın. Kullanıcının ihtiyaçlarını analiz ederek onlara özel AI agent konfigürasyonları oluşturuyorsun.

Görevin:
1. Kullanıcının ihtiyaçlarını detaylı şekilde anla
2. Bu ihtiyaçlara göre kapsamlı bir AI agent JSON konfigürasyonu oluştur
3. Agent'in sistem promptunu, araçlarını, workflow'larını ve veri şemasını tasarla
4. Türkçe olarak açık ve anlaşılır şekilde iletişim kur

MEVCUT ARAÇLAR (TOOLS):
- API: HTTP API çağrıları yapabilir (GET, POST, PUT, DELETE)
- RSS: RSS feed'lerini okuyabilir ve parse edebilir
- DATABASE: MongoDB veritabanı işlemleri yapabilir (create_collection, insert_document, find_documents, update_document, delete_document, aggregate, count_documents, get_collection_stats)

DATABASE TOOL OPERATIONS:
- create_collection: Yeni koleksiyon oluşturur
- insert_document: Dokuman ekler
- find_documents: Dokuman arar
- update_document: Dokuman günceller
- delete_document: Dokuman siler
- aggregate: Karmaşık sorgular yapar
- count_documents: Dokuman sayar
- get_collection_stats: Koleksiyon istatistikleri alır

Önemli kurallar:
- Kullanıcının ihtiyaçlarını tam olarak anladığından emin ol
- Agent'in sistem promptu detaylı ve işlevsel olmalı
- Mevcut araçları kullanarak gerekli tool'ları tanımla
- Veri şemasını kullanıcının ihtiyaçlarına göre tasarla
- JSON formatında valid bir konfigürasyon üret (tüm string'ler çift tırnak içinde olmalı)
- Workflow'larda DATABASE tool'unu kullanarak veri işlemleri yap

Kullanıcı ile Türkçe konuş ve profesyonel bir ton kullan."""

async def process_smart_conversation(conversation_id: str, user_message: str) -> SmartMasterAgentState:
    """Process conversation with smart master agent using DeepSeek"""
    
    # Get or create conversation state
    if not conversation_id or conversation_id == "new_conversation" or conversation_id not in smart_conversations:
        state = SmartMasterAgentState()
        smart_conversations[state.conversation_id] = state
        logger.info(f"Created new conversation: {state.conversation_id}")
    else:
        state = smart_conversations[conversation_id]
        logger.info(f"Continuing conversation: {conversation_id}")
    
    # Add user message
    state.messages.append({"role": "user", "content": user_message})
    
    try:
        if state.current_phase == "gathering_requirements":
            # First interaction - gather requirements
            if len(state.messages) == 1:  # First message
                state.user_requirements = user_message
                
                # Create a simple hardcoded agent instead of using LLM
                logger.info("Creating hardcoded agent for immediate response")
                state.current_phase = "confirming"
                
                # Create a simple agent config based on user request
                agent_name = "Custom Agent"
                agent_id = f"custom_agent_{len(state.messages)}"
                
                if "not" in user_message.lower() or "note" in user_message.lower():
                    agent_name = "Not Alma Assistant"
                    agent_id = "not_alma_agent"
                elif "todo" in user_message.lower() or "görev" in user_message.lower():
                    agent_name = "Todo List Manager"
                    agent_id = "todo_manager_agent"
                elif "kitap" in user_message.lower() or "book" in user_message.lower():
                    agent_name = "Kitap Takip Assistant"
                    agent_id = "kitap_takip_agent"
                
                # Create simple agent config
                state.agent_config = {
                    "agentId": agent_id,
                    "agentName": agent_name,
                    "version": "1.0",
                    "systemPrompt": f"Sen bir {agent_name} asistanısın. Kullanıcılara yardımcı ol ve DATABASE araçlarını kullanarak verileri yönet.",
                    "llmConfig": {"provider": "deepseek", "model": "deepseek-chat"},
                    "dataSchema": {
                        "collectionName": f"{agent_id}_data",
                        "schema": {"type": "object", "properties": {"title": {"type": "string"}, "content": {"type": "string"}, "created_at": {"type": "string"}}}
                    },
                    "tools": [
                        {"toolId": "database_ops", "name": "Database Operations", "type": "DATABASE", "description": "Veritabanı işlemleri"}
                    ],
                    "workflows": [],
                    "schedules": []
                }
                
                response = f"✅ **{agent_name}** agent'i hazırlandı!\n\n**Özellikler:**\n- Veritabanı desteği\n- Basit veri yönetimi\n- Chat arayüzü\n\nAgent'i oluşturmak için 'Evet' yazın."
                state.messages.append({"role": "assistant", "content": response})
                
            else:
                # Continue gathering requirements
                state.user_requirements += f"\n\nEk bilgi: {user_message}"
                
                # Decide if we have enough information
                decision_prompt = f"""
                Kullanıcının ihtiyaçları:
                {state.user_requirements}
                
                Bu bilgiler bir AI agent tasarlamak için yeterli mi? 
                
                Eğer temel işlev (ne yapacağı) ve veri yapısı (neyi saklayacağı) belli ise YETERLI.
                
                KESINLIKLE "YETERLI" ile başla ve agent tasarımına geç. Sonra iki satır boşluk bırak.
                Eğer gerçekten eksik bilgi varsa daha fazla bilgi toplamak için soru sor.
                
                Çoğunlukla bilgiler yeterlidir, detayları kendin tamamlayabilirsin.
                """
                
                response = await get_llm_response(
                    llm_config=MASTER_AGENT_LLM_CONFIG,
                    system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
                    user_message=decision_prompt
                )
                
                if response.startswith("YETERLI"):
                    logger.info(f"Moving to analyzing phase for conversation {state.conversation_id}")
                    state.current_phase = "analyzing"
                    # Continue to analysis phase
                    logger.info("Starting agent generation...")
                    analysis_response = await analyze_and_generate_agent(state)
                    logger.info(f"Generated response length: {len(analysis_response)}")
                    state.messages.append({"role": "assistant", "content": analysis_response})
                else:
                    state.messages.append({"role": "assistant", "content": response})
        
        elif state.current_phase == "analyzing":
            # User provided feedback on the generated agent
            logger.info(f"In analyzing phase, user message: {user_message[:100]}...")
            if user_message.lower() in ["evet", "tamam", "onaylıyorum", "oluştur", "kabul"]:
                logger.info("User confirmed agent creation")
                state.completed = True
                state.current_phase = "completed"
                state.messages.append({
                    "role": "assistant", 
                    "content": "Mükemmel! Agent'iniz başarıyla tasarlandı ve oluşturulacak."
                })
            else:
                # User wants modifications
                modification_prompt = f"""
                Kullanıcı tasarlanan agent hakkında şu değişikliği istiyor: "{user_message}"
                
                Mevcut agent konfigürasyonu:
                {json.dumps(state.agent_config, indent=2, ensure_ascii=False)}
                
                Bu değişikliği uygula ve güncellenmiş agent konfigürasyonunu oluştur.
                """
                
                response = await get_llm_response(
                    llm_config=MASTER_AGENT_LLM_CONFIG,
                    system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
                    user_message=modification_prompt
                )
                
                # Try to extract updated config from response
                try:
                    if "```json" in response:
                        json_start = response.find("```json") + 7
                        json_end = response.find("```", json_start)
                        json_str = response[json_start:json_end].strip()
                        state.agent_config = json.loads(json_str)
                except:
                    logger.warning("Could not extract updated JSON from DeepSeek response")
                
                state.messages.append({"role": "assistant", "content": response})
        
        return state
        
    except Exception as e:
        logger.error(f"Error in smart master agent conversation: {str(e)}")
        error_response = f"Üzgünüm, bir hata oluştu: {str(e)}. Lütfen tekrar deneyin."
        state.messages.append({"role": "assistant", "content": error_response})
        return state

async def analyze_and_generate_agent(state: SmartMasterAgentState) -> str:
    """Analyze requirements and generate agent configuration"""
    
    try:
        generation_prompt = f"""
        Kullanıcı ihtiyaçları: {state.user_requirements}
        
        Bu ihtiyaçlara uygun basit bir AI agent JSON konfigürasyonu oluştur.
        
        Sadece DATABASE araçlarını kullan. JSON'dan önce kısa açıklama yap.
        
        JSON formatı:
        ```json
        {{
            "agentId": "not_alma_agent",
            "agentName": "Not Alma Assistant",
            "version": "1.0",
            "systemPrompt": "Sen kullanıcıların notlarını yöneten bir asistansın...",
            "llmConfig": {{"provider": "deepseek", "model": "deepseek-chat"}},
            "dataSchema": {{
                "collectionName": "notes_data",
                "schema": {{"type": "object", "properties": {{"title": {{"type": "string"}}, "content": {{"type": "string"}}, "category": {{"type": "string"}}, "created_at": {{"type": "string"}}}}}}
            }},
            "tools": [
                {{"toolId": "database_ops", "name": "Database Operations", "type": "DATABASE", "description": "Not veritabanı işlemleri"}}
            ],
            "workflows": [],
            "schedules": []
        }}
        ```
        """
        
        logger.info("Calling DeepSeek API for agent generation...")
        response = await get_llm_response(
            llm_config=MASTER_AGENT_LLM_CONFIG,
            system_prompt=MASTER_AGENT_SYSTEM_PROMPT,
            user_message=generation_prompt
        )
        
        logger.info(f"Raw LLM response length: {len(response)}")
        logger.info(f"Raw LLM response preview: {response[:200]}...")
        
    except Exception as e:
        logger.error(f"Error calling LLM for agent generation: {str(e)}")
        return f"Agent oluşturma sırasında hata oluştu: {str(e)}"
    
    # Try to extract JSON from response
    try:
        logger.info("Attempting to extract JSON from response...")
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            json_str = response[json_start:json_end].strip()
            logger.info(f"Extracted JSON string length: {len(json_str)}")
            
            # Clean up JSON string - remove comments and fix common issues
            lines = json_str.split('\n')
            cleaned_lines = []
            for line in lines:
                # Remove lines that start with // (comments)
                if line.strip().startswith('//'):
                    continue
                # Remove inline comments
                if '//' in line:
                    line = line.split('//')[0].rstrip()
                cleaned_lines.append(line)
            
            cleaned_json = '\n'.join(cleaned_lines)
            logger.info(f"Cleaned JSON string length: {len(cleaned_json)}")
            
            # Try to parse JSON
            agent_config = json.loads(cleaned_json)
            logger.info(f"Successfully parsed agent config with keys: {list(agent_config.keys())}")
            state.agent_config = agent_config
            state.current_phase = "confirming"
            
            # Add confirmation question
            response += "\n\nBu agent konfigürasyonu sizin ihtiyaçlarınıza uygun mu? 'Evet' derseniz agent'i oluşturacağım, değilse hangi değişiklikleri istediğinizi belirtin."
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        logger.error(f"Failed JSON content (first 500 chars): {cleaned_json[:500] if 'cleaned_json' in locals() else 'N/A'}")
        response += f"\n\nJSON ayrıştırma hatası: {str(e)}. Lütfen JSON formatını düzeltmemi için bana söyleyin."
    except Exception as e:
        logger.error(f"Error parsing generated agent config: {str(e)}")
        logger.error(f"Response content (first 500 chars): {response[:500]}")
        response += f"\n\nKonfigürasyon ayrıştırma hatası: {str(e)}"
    
    return response

def create_agent_from_smart_conversation(state: SmartMasterAgentState, owner: str) -> AgentModel:
    """Create AgentModel from smart conversation state"""
    
    if not state.agent_config:
        raise ValueError("No agent configuration found in conversation state")
    
    config = state.agent_config
    
    # Create tools from config
    tools = []
    for tool_config in config.get("tools", []):
        tool = Tool(**tool_config)
        tools.append(tool)
    
    # Create workflows from config
    workflows = []
    for workflow_config in config.get("workflows", []):
        # Create workflow nodes
        nodes = []
        for node_config in workflow_config.get("nodes", []):
            node = WorkflowNode(**node_config)
            nodes.append(node)
        
        workflow = Workflow(
            workflowId=workflow_config.get("workflowId"),
            description=workflow_config.get("description", ""),
            trigger=workflow_config.get("trigger"),
            nodes=nodes
        )
        workflows.append(workflow)
    
    # Create schedules from config
    schedules = []
    for schedule_config in config.get("schedules", []):
        schedule = Schedule(**schedule_config)
        schedules.append(schedule)
    
    # Create data schema
    data_schema = DataSchema(**config.get("dataSchema", {
        "collectionName": f"{config.get('agentId', 'default')}_data",
        "schema": {"type": "object", "properties": {}}
    }))
    
    # Create LLM config
    llm_config = LlmConfig(**config.get("llmConfig", {
        "provider": "deepseek",
        "model": "deepseek-chat"
    }))
    
    # Create the agent model
    agent_model = AgentModel(
        owner=owner,
        agentId=config.get("agentId"),
        agentName=config.get("agentName"),
        version=config.get("version", "1.0"),
        systemPrompt=config.get("systemPrompt"),
        llmConfig=llm_config,
        dataSchema=data_schema,
        tools=tools,
        workflows=workflows,
        schedules=schedules
    )
    
    return agent_model 