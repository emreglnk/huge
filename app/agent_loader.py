import logging
import json
from typing import Dict, Any, List, Optional
import pymongo
from pymongo.database import Database

from .db import agent_collection, db
from .models import AgentModel, Tool, Workflow, DataSchema
from .file_agent_manager import file_agent_manager

logger = logging.getLogger(__name__)

class AgentNotFoundException(Exception):
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent with ID '{agent_id}' not found.")

class AgentDataSchemaError(Exception):
    """Raised when there's an issue with the agent's data schema"""
    pass

class ToolInitializationError(Exception):
    """Raised when there's an issue initializing a tool"""
    pass

class WorkflowValidationError(Exception):
    """Raised when there's an issue with a workflow definition"""
    pass

async def load_agent_config(agent_id: str, initialize: bool = False) -> AgentModel:
    """
    Fetches an agent's configuration from file system and loads it into an AgentModel.

    Args:
        agent_id: The unique identifier for the agent.
        initialize: If True, also initialize the agent's tools, schemas, and workflows.

    Returns:
        An AgentModel instance containing the agent's configuration.

    Raises:
        AgentNotFoundException: If no agent with the given ID is found.
    """
    agent_config = file_agent_manager.get_agent(agent_id)
    
    if agent_config is None:
        raise AgentNotFoundException(agent_id)
    
    if initialize:
        await initialize_agent_components(agent_config)
    
    return agent_config

async def initialize_agent_components(agent_config: AgentModel) -> None:
    """
    Initialize all components of an agent including:
    1. Validate and setup data schema collections
    2. Initialize tools
    3. Validate workflows
    
    Args:
        agent_config: The AgentModel instance to initialize
        
    Raises:
        Various exceptions if initialization fails
    """
    try:
        await setup_data_schema(agent_config.dataSchema)
    except Exception as e:
        logger.error(f"Error setting up data schema for agent {agent_config.agentId}: {str(e)}")
        raise AgentDataSchemaError(f"Failed to set up data schema: {str(e)}") from e
    
    try:
        await initialize_tools(agent_config.tools)
    except Exception as e:
        logger.error(f"Error initializing tools for agent {agent_config.agentId}: {str(e)}")
        raise ToolInitializationError(f"Failed to initialize tools: {str(e)}") from e
    
    try:
        validate_workflows(agent_config.workflows)
    except Exception as e:
        logger.error(f"Error validating workflows for agent {agent_config.agentId}: {str(e)}")
        raise WorkflowValidationError(f"Failed to validate workflows: {str(e)}") from e

async def setup_data_schema(data_schema: DataSchema) -> None:
    """
    Set up the MongoDB collection based on the agent's data schema.
    This creates validators and indexes as needed.
    
    Args:
        data_schema: The DataSchema from the agent config
    """

    collection_name = data_schema.collectionName
    schema_definition = data_schema.schema_definition
    
    # Create a JSON Schema validator
    validator = {
        "$jsonSchema": schema_definition
    }
    
    try:
        # Check if collection already exists
        collections = await db.list_collection_names()
        
        if collection_name in collections:
            logger.info(f"Collection {collection_name} already exists, updating validator")
            await db.command("collMod", collection_name, validator=validator)
        else:
            logger.info(f"Creating collection {collection_name} with validator")
            await db.create_collection(collection_name, validator=validator)
            
        # Create any necessary indexes (example: if there's a userId field)
        if "properties" in schema_definition and "userId" in schema_definition["properties"]:
            collection = db[collection_name]
            await collection.create_index("userId")
            
    except Exception as e:
        logger.error(f"Error setting up collection {collection_name}: {str(e)}")
        raise

async def initialize_tools(tools: List[Tool]) -> Dict[str, Any]:
    """
    Initialize the tools defined in the agent configuration.
    Returns a dictionary of initialized tool functions ready for use.
    
    Args:
        tools: List of Tool objects from the agent config
        
    Returns:
        Dict mapping tool IDs to callable functions
    """
    initialized_tools = {}
    
    for tool in tools:
        try:
            if tool.type == "API":
                initialized_tools[tool.toolId] = create_api_tool(tool)
            elif tool.type == "RSS":
                initialized_tools[tool.toolId] = create_rss_tool(tool)
            else:
                logger.warning(f"Unknown tool type {tool.type} for tool {tool.toolId}")
        except Exception as e:
            logger.error(f"Failed to initialize tool {tool.toolId}: {str(e)}")
            raise
            
    return initialized_tools

def create_api_tool(tool: Tool) -> callable:
    """
    Create a callable function for an API tool
    
    Args:
        tool: The Tool object defining the API
        
    Returns:
        A callable function that executes the API request
    """
    import httpx
    
    async def api_tool_function(params: Dict[str, Any] = None) -> Any:
        """Dynamic API tool function"""
        params = params or {}
        headers = {}
        endpoint = tool.endpoint
        
        if not endpoint:
            raise ValueError(f"Tool {tool.toolId} has no endpoint configured")
            
        if tool.auth:
            if tool.auth.type == "apiKey":
                headers["Authorization"] = f"Bearer {tool.auth.key}"
            elif tool.auth.type == "basic":
                # Handle basic auth if needed
                pass
                
        async with httpx.AsyncClient() as client:
            response = await client.request(
                "GET",  # Default method, could be parametrized
                endpoint,
                params=params,
                headers=headers,
                timeout=10.0
            )
            
            response.raise_for_status()
            return response.json()
            
    return api_tool_function

def create_rss_tool(tool: Tool) -> callable:
    """
    Create a callable function for an RSS feed tool
    
    Args:
        tool: The Tool object defining the RSS feed
        
    Returns:
        A callable function that fetches RSS feed items
    """
    import feedparser
    import httpx
    
    async def rss_tool_function(params: Dict[str, Any] = None) -> Any:
        """Dynamic RSS feed tool function"""
        params = params or {}
        url = tool.url
        
        if not url:
            raise ValueError(f"Tool {tool.toolId} has no URL configured")
            
        limit = params.get("limit", 10)  # Default to 10 items
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            content = response.text
            
        feed = feedparser.parse(content)
        
        # Return limited number of entries
        entries = feed.entries[:limit]
        
        # Convert to simple dicts without feedparser-specific attributes
        result = []
        for entry in entries:
            item = {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "description": entry.get("description", ""),
                "published": entry.get("published", "")
            }
            result.append(item)
            
        return result
            
    return rss_tool_function

def validate_workflows(workflows: List[Workflow]) -> None:
    """
    Validate that all workflows have the necessary components and valid references.
    
    Args:
        workflows: List of Workflow objects from agent config
        
    Raises:
        WorkflowValidationError: If any workflow definition is invalid
    """
    for workflow in workflows:
        # Check that all node IDs are unique
        node_ids = [node.nodeId for node in workflow.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise WorkflowValidationError(f"Workflow {workflow.workflowId} has duplicate node IDs")
            
        # Validate each node by type
        for node in workflow.nodes:
            if node.type == "llm_prompt":
                if not node.prompt:
                    raise WorkflowValidationError(f"Node {node.nodeId} in workflow {workflow.workflowId} is missing required 'prompt' field")
                if not node.output_variable:
                    raise WorkflowValidationError(f"Node {node.nodeId} in workflow {workflow.workflowId} is missing required 'output_variable' field")
            
            elif node.type == "data_store":
                if not node.action:
                    raise WorkflowValidationError(f"Node {node.nodeId} in workflow {workflow.workflowId} is missing required 'action' field")
                if not node.collection:
                    raise WorkflowValidationError(f"Node {node.nodeId} in workflow {workflow.workflowId} is missing required 'collection' field")
                    
            elif node.type == "send_response":
                if not node.message:
                    raise WorkflowValidationError(f"Node {node.nodeId} in workflow {workflow.workflowId} is missing required 'message' field")
