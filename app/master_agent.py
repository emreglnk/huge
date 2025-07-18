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
        "Welcome! I'm your Master Agent. I'll help you create a new AI agent. Let's start by defining your agent's basic properties. What would you like to name your new agent?",
        
        # Step 1 - Ask for agent ID
        lambda data: f"Great! Your agent will be named '{data.get('agentName', 'New Agent')}'. Now, let's give it a unique ID (no spaces, alphanumeric with underscores):",
        
        # Step 2 - Ask for system prompt
        "Now, what system prompt would you like to give this agent? This defines its core behavior and personality.",
        
        # Step 3 - Ask for LLM provider
        "Which LLM provider would you like to use? Options include:\n- openai (for GPT models)\n- deepseek (for DeepSeek's models)\n- gemini (for Google's Gemini)",
        
        # Step 4 - Ask for specific model
        lambda data: get_model_prompt(data.get('llmProvider', 'openai')),
        
        # Step 5 - Confirmation
        lambda data: f"Perfect! I'm ready to create your agent with:\n- Name: {data.get('agentName')}\n- ID: {data.get('agentId')}\n- Using {data.get('llmProvider')} ({data.get('llmModel')})\n\nWould you like me to create this agent now? (yes/no)"
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
        return "Which OpenAI model would you like to use? Options include:\n- gpt-3.5-turbo (fast, efficient)\n- gpt-4 (more capable but slower)"
    
    elif provider.lower() == 'deepseek':
        return "Which DeepSeek model would you like to use? Options include:\n- deepseek-chat (general chat model)\n- deepseek-coder (code-specialized model)"
    
    elif provider.lower() == 'gemini':
        return "Which Google Gemini model would you like to use? Options include:\n- gemini-pro (balanced model)\n- gemini-pro-vision (with image capabilities)"
    
    else:
        return "Which model would you like to use for this provider?"

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
    state.messages.append(MasterAgentMessage(role="user", content=user_message))
    
    # Process based on current step
    if state.current_step == 0:  # First question was for agent name
        state.agent_data["agentName"] = user_message
    
    elif state.current_step == 1:  # Agent ID
        state.agent_data["agentId"] = user_message
    
    elif state.current_step == 2:  # System prompt
        state.agent_data["systemPrompt"] = user_message
    
    elif state.current_step == 3:  # LLM Provider
        state.agent_data["llmProvider"] = user_message.lower()
        
        # Initialize llmConfig if it doesn't exist
        if "llmConfig" not in state.agent_data:
            state.agent_data["llmConfig"] = {}
        
        state.agent_data["llmConfig"]["provider"] = user_message.lower()
    
    elif state.current_step == 4:  # LLM Model
        state.agent_data["llmModel"] = user_message
        state.agent_data["llmConfig"]["model"] = user_message
    
    elif state.current_step == 5:  # Confirmation
        if user_message.lower() in ["yes", "y", "ok", "sure"]:
            state.completed = True
    
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
