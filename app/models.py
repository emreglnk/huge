from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class ToolAuth(BaseModel):
    type: str
    key: str

class Tool(BaseModel):
    toolId: str
    type: str
    name: str
    description: str
    endpoint: Optional[str] = None
    url: Optional[str] = None
    auth: Optional[ToolAuth] = None

class DataSchema(BaseModel):
    collectionName: str
    schema_definition: Dict[str, Any] = Field(..., alias="schema")

class WorkflowNode(BaseModel):
    nodeId: str
    type: str
    prompt: Optional[str] = None
    output_variable: Optional[str] = None
    action: Optional[str] = None
    collection: Optional[str] = None
    data: Optional[str] = None
    message: Optional[str] = None
    # Tool-specific fields
    toolId: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    # Conditional logic fields
    condition: Optional[str] = None
    # Failure handling
    on_failure: Optional[str] = Field(None, description="Action to take on failure: 'continue', 'stop', 'retry'")
    continue_on_error: Optional[bool] = Field(False, description="Whether to continue workflow execution if this node fails")
    max_retries: Optional[int] = Field(3, description="Maximum number of retries for this node")
    retry_delay: Optional[float] = Field(1.0, description="Delay between retries in seconds")
    # Timeout settings
    timeout: Optional[int] = Field(30, description="Timeout for this node in seconds")
    # Validation and sanitization
    validate_input: Optional[bool] = Field(True, description="Whether to validate input parameters")
    sanitize_output: Optional[bool] = Field(True, description="Whether to sanitize output data")

class Workflow(BaseModel):
    workflowId: str
    description: str
    trigger: str
    nodes: List[WorkflowNode]

class Schedule(BaseModel):
    scheduleId: str
    cron: str
    description: str
    workflowId: str

class LlmConfig(BaseModel):
    provider: str = Field(default="openai", description="The LLM provider to use (e.g., 'openai', 'deepseek', 'gemini').")
    model: str = Field(default="gpt-3.5-turbo", description="The specific model to use.")

class UpdateLlmConfig(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None

class AgentModel(BaseModel):
    owner: Optional[str] = None  # Username of the agent's creator, set automatically by API
    agentId: str
    agentName: str
    version: str
    systemPrompt: str
    llmConfig: LlmConfig = Field(default_factory=LlmConfig, description="Configuration for the language model.")
    dataSchema: Optional[DataSchema] = None
    tools: List[Tool] = Field(default_factory=list)
    workflows: List[Workflow] = Field(default_factory=list)
    schedules: List[Schedule] = Field(default_factory=list)
    public: Optional[bool] = False  # Whether the agent is publicly shareable

    class Config:
        validate_by_name = True
        json_schema_extra = {
            "example": {
                "agentId": "dietitian_pro_123",
                "agentName": "Dietitian Pro",
                "version": "1.0",
                "systemPrompt": "You are an expert dietitian...",
                "llmConfig": {
                    "provider": "openai",
                    "model": "gpt-3.5-turbo"
                },
                "dataSchema": {
                    "collectionName": "dietitian_user_data",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "measurements": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "date": {"type": "string"},
                                        "weight_kg": {"type": "number"},
                                        "body_fat_percentage": {"type": "number"}
                                    }
                                }
                            }
                        }
                    }
                },
                "tools": [],
                "workflows": [],
                "schedules": []
            }
        }

class UpdateAgentModel(BaseModel):
    agentName: Optional[str]
    version: Optional[str]
    systemPrompt: Optional[str] = None
    llmConfig: Optional[UpdateLlmConfig] = None
    dataSchema: Optional[DataSchema]
    tools: Optional[List[Tool]]
    workflows: Optional[List[Workflow]]
    schedules: Optional[List[Schedule]]

    class Config:
        json_schema_extra = {
            "example": {
                "agentName": "Dietitian Pro v2",
                "version": "1.1",
            }
        }

# Models for User Authentication
class User(BaseModel):
    username: str
    password: str

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class TelegramAuth(BaseModel):
    """Telegram authentication and chat ID mapping"""
    user_id: str  # Platform user ID
    chat_id: str  # Telegram chat ID
    auth_code: str  # Temporary authentication code
    is_verified: bool = False
    created_at: Optional[str] = None
    verified_at: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
