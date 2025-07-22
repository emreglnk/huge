import json
import uuid
from typing import Dict, Optional, List

from pydantic import BaseModel, Field
from .models import AgentModel, LlmConfig

class MasterAgentMessage(BaseModel):
    role: str  # 'system', 'user', or 'assistant'
    content: str

class MasterAgentState(BaseModel):
    conversation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[MasterAgentMessage] = []
    current_step: int = 0
    agent_data: Dict = {}
    completed: bool = False

# Store active conversations (in a real app, this would be in a database)
active_conversations: Dict[str, MasterAgentState] = {}

def get_welcome_message() -> str:
    return "Welcome! I'm your Master Agent. I'll help you create a new AI agent. Let's start by defining your agent's basic properties. What would you like to name your new agent?"

def get_next_prompt(step: int, agent_data: Dict) -> Optional[str]:
    """
    Returns the prompt for the next step in creating an agent.
    Returns None when all steps are complete.
    """
    prompts = [
        # Step 0 - Welcome and ask for name
        "Merhaba! Ben Master Agent'ım. Yeni bir AI agent oluşturmanıza yardımcı olacağım. Agent'inize ne isim vermek istiyorsunuz?",
        
        # Step 1 - Ask for agent ID
        lambda data: f"Harika! Agent'inizin adı '{data.get('agentName', 'Yeni Agent')}' olacak. Şimdi ona benzersiz bir ID verelim (boşluk olmadan, alfanumerik ve alt çizgi kullanabilirsiniz):",
        
        # Step 2 - Ask for system prompt
        "Şimdi bu agent'e nasıl bir sistem promptu vermek istiyorsunuz? Bu, agent'in temel davranışını ve kişiliğini tanımlar. Lütfen detaylı bir şekilde açıklayın.",
        
        # Step 3 - Ask for LLM provider
        "Hangi LLM sağlayıcısını kullanmak istiyorsunuz? Seçenekler:\n- openai (GPT modelleri için)\n- deepseek (DeepSeek modelleri için)\n- gemini (Google Gemini için)",
        
        # Step 4 - Ask for specific model
        lambda data: get_model_prompt(data.get('llmProvider', 'openai')),
        
        # Step 5 - Confirmation
        lambda data: f"Mükemmel! Agent'inizi şu bilgilerle oluşturmaya hazırım:\n- İsim: {data.get('agentName')}\n- ID: {data.get('agentId')}\n- Model: {data.get('llmProvider')} ({data.get('llmModel')})\n\nAgent'i şimdi oluşturmak istiyor musunuz? (evet/hayır)"
    ]
    
    if step >= len(prompts):
        return None
    
    prompt = prompts[step]
    if callable(prompt):
        return prompt(agent_data)
    return prompt

def get_model_prompt(provider: str) -> str:
    """Get provider-specific model options"""
    if provider.lower() == 'openai':
        return "Hangi OpenAI modelini kullanmak istiyorsunuz? Seçenekler:\n- gpt-3.5-turbo (hızlı, verimli)\n- gpt-4 (daha yetenekli ama yavaş)"
    
    elif provider.lower() == 'deepseek':
        return "Hangi DeepSeek modelini kullanmak istiyorsunuz? Seçenekler:\n- deepseek-chat (genel sohbet modeli)\n- deepseek-coder (kod odaklı model)"
    
    elif provider.lower() == 'gemini':
        return "Hangi Google Gemini modelini kullanmak istiyorsunuz? Seçenekler:\n- gemini-pro (dengeli model)\n- gemini-pro-vision (görsel yetenekli)"
    
    else:
        return "Bu sağlayıcı için hangi modeli kullanmak istiyorsunuz?"

def process_user_input(conversation_id: str, user_message: str) -> MasterAgentState:
    """Process user input and update conversation state"""
    # Get or create conversation state
    if conversation_id not in active_conversations:
        state = MasterAgentState()
        active_conversations[state.conversation_id] = state
        conversation_id = state.conversation_id
    else:
        state = active_conversations[conversation_id]
    
    # Add user message to conversation
    state.messages.append(MasterAgentMessage(role="user", content=user_message.strip()))
    
    # Process based on current step
    if state.current_step == 0:  # First question was for agent name
        agent_name = user_message.strip()
        if len(agent_name) < 2:
            state.messages.append(MasterAgentMessage(role="assistant", content="Agent adı en az 2 karakter olmalıdır. Lütfen geçerli bir ad girin:"))
            return state
        state.agent_data["agentName"] = agent_name
    
    elif state.current_step == 1:  # Agent ID
        agent_id = user_message.strip().lower().replace(" ", "_")
        if not agent_id.replace("_", "").isalnum():
            state.messages.append(MasterAgentMessage(role="assistant", content="Agent ID sadece harf, rakam ve alt çizgi içerebilir. Lütfen geçerli bir ID girin:"))
            return state
        state.agent_data["agentId"] = agent_id
    
    elif state.current_step == 2:  # System prompt
        system_prompt = user_message.strip()
        if len(system_prompt) < 10:
            state.messages.append(MasterAgentMessage(role="assistant", content="Sistem promptu en az 10 karakter olmalıdır. Lütfen daha detaylı bir açıklama yapın:"))
            return state
        state.agent_data["systemPrompt"] = system_prompt
    
    elif state.current_step == 3:  # LLM Provider
        provider = user_message.lower().strip()
        valid_providers = ["openai", "deepseek", "gemini"]
        if provider not in valid_providers:
            state.messages.append(MasterAgentMessage(role="assistant", content=f"Geçersiz sağlayıcı. Lütfen şunlardan birini seçin: {', '.join(valid_providers)}"))
            return state
        
        state.agent_data["llmProvider"] = provider
        
        # Initialize llmConfig if it doesn't exist
        if "llmConfig" not in state.agent_data:
            state.agent_data["llmConfig"] = {}
        
        state.agent_data["llmConfig"]["provider"] = provider
    
    elif state.current_step == 4:  # LLM Model
        model = user_message.strip()
        if not model:
            state.messages.append(MasterAgentMessage(role="assistant", content="Model adı boş olamaz. Lütfen geçerli bir model adı girin:"))
            return state
        state.agent_data["llmModel"] = model
        state.agent_data["llmConfig"]["model"] = model
    
    elif state.current_step == 5:  # Confirmation
        response = user_message.lower().strip()
        if response in ["evet", "yes", "y", "ok", "tamam", "sure"]:
            state.completed = True
        elif response in ["hayır", "no", "n", "iptal", "cancel"]:
            state.messages.append(MasterAgentMessage(role="assistant", content="Agent oluşturma iptal edildi. Yeniden başlamak için yeni bir konuşma başlatın."))
            return state
        else:
            state.messages.append(MasterAgentMessage(role="assistant", content="Lütfen 'evet' veya 'hayır' ile yanıtlayın:"))
            return state
    
    # Get next prompt
    next_prompt = get_next_prompt(state.current_step + 1, state.agent_data)
    
    if next_prompt:
        state.messages.append(MasterAgentMessage(role="assistant", content=next_prompt))
        state.current_step += 1
    
    return state

def create_agent_from_conversation(state: MasterAgentState, owner: str) -> AgentModel:
    """Create an AgentModel from the conversation data"""
    # Build the agent with minimal required fields
    agent_model = AgentModel(
        owner=owner,
        agentId=state.agent_data.get("agentId"),
        agentName=state.agent_data.get("agentName"),
        systemPrompt=state.agent_data.get("systemPrompt"),
        llmConfig=LlmConfig(
            provider=state.agent_data.get("llmProvider"),
            model=state.agent_data.get("llmModel")
        ),
        version="1.0",
        dataSchema={"collectionName": f"{state.agent_data.get('agentId')}_data", "schema": {}},
        tools=[],
        workflows=[],
        schedules=[]
    )  
    return agent_model
