from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

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
    owner: str # Username of the agent's creator
    agentId: str
    agentName: str
    version: str
    systemPrompt: str
    llmConfig: LlmConfig = Field(default_factory=LlmConfig, description="Configuration for the language model.")
    dataSchema: DataSchema
    tools: List[Tool]
    workflows: List[Workflow]
    schedules: List[Schedule]

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
                                        "date": {"type": "string", "format": "date-time"},
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
