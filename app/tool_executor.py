import asyncio
import logging
import re
import json
from typing import List, Dict, Any, Callable, Optional
from urllib.parse import urlparse, parse_qs
import httpx
import feedparser

from .models import Tool

logger = logging.getLogger(__name__)

class ToolExecutionError(Exception):
    pass

class ToolValidationError(Exception):
    pass

class ToolSecurityError(Exception):
    pass

def validate_and_sanitize_input(params: Dict[str, Any], tool: Tool) -> Dict[str, Any]:
    """Validate and sanitize input parameters for security"""
    if not params:
        return {}
    
    sanitized_params = {}
    
    for key, value in params.items():
        # Basic input validation
        if not isinstance(key, str):
            raise ToolValidationError(f"Parameter key must be string, got {type(key)}")
        
        # Sanitize key name (alphanumeric and underscore only)
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            raise ToolValidationError(f"Invalid parameter key: {key}")
        
        # Sanitize values based on type
        if isinstance(value, str):
            # Remove potentially dangerous characters
            sanitized_value = re.sub(r'[<>"\';\\]', '', value)
            # Limit string length
            if len(sanitized_value) > 1000:
                sanitized_value = sanitized_value[:1000]
            sanitized_params[key] = sanitized_value
        elif isinstance(value, (int, float, bool)):
            sanitized_params[key] = value
        elif isinstance(value, (list, dict)):
            # Convert to JSON string and sanitize
            try:
                json_str = json.dumps(value)
                if len(json_str) > 5000:  # Limit JSON size
                    raise ToolValidationError(f"Parameter {key} JSON too large")
                sanitized_params[key] = value
            except (TypeError, ValueError) as e:
                raise ToolValidationError(f"Invalid JSON in parameter {key}: {str(e)}")
        else:
            raise ToolValidationError(f"Unsupported parameter type for {key}: {type(value)}")
    
    return sanitized_params

def validate_url(url: str) -> bool:
    """Validate URL for security"""
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            return False
        
        # Check for dangerous patterns
        if any(dangerous in url.lower() for dangerous in ['localhost', '127.0.0.1', '0.0.0.0', 'file://']):
            return False
        
        # Check for suspicious characters
        if re.search(r'[<>"\';\\]', url):
            return False
            
        return True
    except Exception:
        return False

async def execute_api_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes an API tool by making an HTTP request with enhanced security and error handling."""
    try:
        # Validate tool configuration
        if not tool.endpoint:
            raise ToolValidationError(f"Tool {tool.toolId} has no endpoint configured")
        
        if not validate_url(tool.endpoint):
            raise ToolSecurityError(f"Invalid or potentially dangerous URL: {tool.endpoint}")
        
        # Validate and sanitize input parameters
        sanitized_params = validate_and_sanitize_input(params, tool)
        
        # Prepare headers
        headers = {
            'User-Agent': 'AI-Agent-Platform/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Handle authentication
        if tool.auth:
            if tool.auth.type == 'apiKey':
                # Validate API key format
                if not tool.auth.key or len(tool.auth.key) < 10:
                    raise ToolSecurityError(f"Invalid API key for tool {tool.toolId}")
                headers['Authorization'] = f"Bearer {tool.auth.key}"
            elif tool.auth.type == 'basic':
                # Handle basic auth if needed (implementation depends on requirements)
                logger.warning(f"Basic auth not fully implemented for tool {tool.toolId}")
        
        # Create timeout configuration
        timeout = httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=10.0
        )
        
        # Use asyncio to run the HTTP request
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            try:
                response = await client.request(
                    method="GET",  # Default method, could be parametrized
                    url=tool.endpoint,
                    params=sanitized_params,
                    headers=headers
                )
                
                response.raise_for_status()
                
                # Validate response size
                if len(response.content) > 10 * 1024 * 1024:  # 10MB limit
                    raise ToolExecutionError(f"Response too large from tool {tool.toolId}")
                
                # Try to parse JSON, fall back to text
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    result = {"text": response.text}
                
                logger.info(f"API tool {tool.toolId} executed successfully")
                return result
                
            except httpx.TimeoutException:
                raise ToolExecutionError(f"Timeout occurred for tool {tool.toolId}")
            except httpx.HTTPStatusError as e:
                raise ToolExecutionError(f"HTTP error {e.response.status_code} for tool {tool.toolId}: {e.response.text}")
            except httpx.RequestError as e:
                raise ToolExecutionError(f"Network error for tool {tool.toolId}: {str(e)}")
                
    except ToolValidationError as e:
        logger.error(f"Validation error for tool {tool.toolId}: {str(e)}")
        raise
    except ToolSecurityError as e:
        logger.error(f"Security error for tool {tool.toolId}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in API tool {tool.toolId}: {str(e)}")
        raise ToolExecutionError(f"Unexpected error in tool {tool.toolId}: {str(e)}")

async def execute_rss_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes an RSS tool by parsing a feed URL with enhanced security and async processing."""
    try:
        # Validate tool configuration
        if not tool.url:
            raise ToolValidationError(f"Tool {tool.toolId} has no URL configured")
        
        if not validate_url(tool.url):
            raise ToolSecurityError(f"Invalid or potentially dangerous RSS URL: {tool.url}")
        
        # Validate and sanitize parameters
        sanitized_params = validate_and_sanitize_input(params, tool)
        limit = min(sanitized_params.get("limit", 10), 100)  # Cap at 100 items
        
        # Use asyncio to run the RSS parsing in executor to avoid blocking
        loop = asyncio.get_running_loop()
        
        async def fetch_rss_content():
            timeout = httpx.Timeout(connect=10.0, read=30.0)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.get(tool.url)
                response.raise_for_status()
                
                # Validate response size
                if len(response.content) > 5 * 1024 * 1024:  # 5MB limit for RSS
                    raise ToolExecutionError(f"RSS feed too large for tool {tool.toolId}")
                
                return response.text
        
        def parse_rss_feed(content: str) -> List[Dict[str, Any]]:
            """Parse RSS feed content synchronously"""
            try:
                feed = feedparser.parse(content)
                
                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"RSS feed parsing warning for tool {tool.toolId}: {feed.bozo_exception}")
                
                # Extract and sanitize entries
                result = []
                for entry in feed.entries[:limit]:
                    # Sanitize entry data
                    sanitized_entry = {
                        "title": re.sub(r'[<>"\';\\]', '', entry.get("title", ""))[:200],
                        "link": entry.get("link", "") if validate_url(entry.get("link", "")) else "",
                        "description": re.sub(r'[<>"\';\\]', '', entry.get("description", ""))[:500],
                        "published": entry.get("published", "")[:50],
                        "author": re.sub(r'[<>"\';\\]', '', entry.get("author", ""))[:100]
                    }
                    result.append(sanitized_entry)
                
                return result
                
            except Exception as e:
                raise ToolExecutionError(f"Error parsing RSS feed for tool {tool.toolId}: {str(e)}")
        
        # Fetch RSS content
        content = await fetch_rss_content()
        
        # Parse RSS feed in executor to avoid blocking
        entries = await loop.run_in_executor(None, parse_rss_feed, content)
        
        logger.info(f"RSS tool {tool.toolId} executed successfully, fetched {len(entries)} entries")
        return {"entries": entries}
        
    except ToolValidationError as e:
        logger.error(f"Validation error for RSS tool {tool.toolId}: {str(e)}")
        raise
    except ToolSecurityError as e:
        logger.error(f"Security error for RSS tool {tool.toolId}: {str(e)}")
        raise
    except httpx.TimeoutException:
        raise ToolExecutionError(f"Timeout occurred for RSS tool {tool.toolId}")
    except httpx.HTTPStatusError as e:
        raise ToolExecutionError(f"HTTP error {e.response.status_code} for RSS tool {tool.toolId}")
    except Exception as e:
        logger.error(f"Unexpected error in RSS tool {tool.toolId}: {str(e)}")
        raise ToolExecutionError(f"Unexpected error in RSS tool {tool.toolId}: {str(e)}")

# Enhanced tool registry with security validation
# Note: DATABASE tool will be added after function definition
TOOL_REGISTRY: Dict[str, Callable] = {
    'API': execute_api_tool,
    'RSS': execute_rss_tool,
}

# Allowed tool types for security
ALLOWED_TOOL_TYPES = {'API', 'RSS', 'DATABASE', 'TELEGRAM'}

async def execute_tool(tool: Tool, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dynamically executes a tool based on its type with comprehensive security and error handling.

    Args:
        tool: The Tool object from the agent's configuration.
        params: A dictionary of parameters to pass to the tool.

    Returns:
        The result of the tool's execution.
    """
    try:
        # Security validation
        if tool.type not in ALLOWED_TOOL_TYPES:
            raise ToolSecurityError(f"Tool type '{tool.type}' is not allowed for security reasons")
        
        # Validate tool configuration
        if not tool.toolId or not isinstance(tool.toolId, str):
            raise ToolValidationError("Tool must have a valid toolId")
        
        if not tool.name or not isinstance(tool.name, str):
            raise ToolValidationError("Tool must have a valid name")
        
        # Sanitize tool ID
        if not re.match(r'^[a-zA-Z0-9_-]+$', tool.toolId):
            raise ToolValidationError(f"Invalid tool ID format: {tool.toolId}")
        
        # Initialize parameters
        if params is None:
            params = {}
        
        # Get executor function
        executor = TOOL_REGISTRY.get(tool.type)
        if not executor:
            raise ToolExecutionError(f"Unsupported tool type: {tool.type}")
        
        # Execute with timeout
        try:
            result = await asyncio.wait_for(
                executor(tool, params),
                timeout=60.0  # 60 second timeout for tool execution
            )
            
            # Validate result
            if not isinstance(result, dict):
                logger.warning(f"Tool {tool.toolId} returned non-dict result, wrapping in dict")
                result = {"result": result}
            
            # Add metadata
            result["_tool_metadata"] = {
                "tool_id": tool.toolId,
                "tool_type": tool.type,
                "execution_time": asyncio.get_event_loop().time()
            }
            
            return result
            
        except asyncio.TimeoutError:
            raise ToolExecutionError(f"Tool {tool.toolId} execution timed out")
        
    except (ToolValidationError, ToolSecurityError, ToolExecutionError) as e:
        logger.error(f"Tool execution error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error executing tool {tool.toolId}: {str(e)}")
        raise ToolExecutionError(f"Unexpected error executing tool {tool.toolId}: {str(e)}")

async def execute_database_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute database operations"""
    try:
        from .database_tool import execute_database_operation
        
        # Get operation type from tool configuration or parameters
        operation = params.get("operation") or tool.config.get("operation", "find_documents")
        
        # Remove operation from params to avoid conflicts
        clean_params = {k: v for k, v in params.items() if k != "operation"}
        
        # Execute the database operation
        result = await execute_database_operation(operation, **clean_params)
        
        logger.info(f"Database tool {tool.toolId} executed operation {operation}")
        return result
        
    except Exception as e:
        logger.error(f"Error in database tool {tool.toolId}: {str(e)}")
        raise ToolExecutionError(f"Database operation failed: {str(e)}")

# Add DATABASE tool to registry after function definition
TOOL_REGISTRY['DATABASE'] = execute_database_tool

async def execute_telegram_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Telegram API tool to send messages.
    
    Args:
        tool: The Telegram tool configuration
        params: Parameters containing chat_id and message
    
    Returns:
        Dict containing the result of the Telegram API call
    """
    try:
        import os
        
        # Get Telegram bot token from environment
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not bot_token:
            raise ToolExecutionError("TELEGRAM_BOT_TOKEN environment variable not set")
        
        # Validate required parameters
        if not params:
            raise ToolExecutionError("Telegram tool requires parameters")
        
        chat_id = params.get('chat_id')
        message = params.get('message')
        
        if not chat_id:
            raise ToolExecutionError("chat_id parameter is required")
        if not message:
            raise ToolExecutionError("message parameter is required")
        
        # Sanitize inputs
        sanitized_params = validate_and_sanitize_input({'chat_id': str(chat_id), 'message': str(message)}, tool)
        chat_id = sanitized_params.get('chat_id', str(chat_id))
        message = sanitized_params.get('message', str(message))
        
        # If chat_id looks like a username, try to resolve it to actual chat_id
        if not chat_id.isdigit() and not chat_id.startswith('-'):
            from .telegram_auth_manager import telegram_auth_manager
            try:
                resolved_chat_id = await telegram_auth_manager.get_chat_id_for_user(chat_id)
                if resolved_chat_id:
                    chat_id = resolved_chat_id
                    logger.info(f"Resolved username {params.get('chat_id')} to chat_id {chat_id}")
                else:
                    logger.warning(f"Could not resolve username {params.get('chat_id')} to chat_id")
            except Exception as e:
                logger.warning(f"Error resolving username to chat_id: {str(e)}")
        
        # Prepare Telegram API request
        telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"  # Support Markdown formatting
        }
        
        # Make API request with timeout
        async with httpx.AsyncClient() as client:
            response = await client.post(
                telegram_url,
                json=payload,
                timeout=30.0
            )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Telegram message sent successfully to {chat_id}")
            return {
                "success": True,
                "message_id": result.get("result", {}).get("message_id"),
                "chat_id": chat_id,
                "status": "sent"
            }
        else:
            error_msg = f"Telegram API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise ToolExecutionError(error_msg)
            
    except httpx.TimeoutException:
        error_msg = f"Timeout while sending Telegram message to {chat_id}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error in Telegram tool {tool.toolId}: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(error_msg)

# Add Telegram tool to registry
TOOL_REGISTRY['TELEGRAM'] = execute_telegram_tool

# Add Scheduling tool to registry
async def execute_scheduling_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute scheduling tool operations"""
    try:
        from .scheduling_tool import execute_scheduling_operation
        
        # Get operation type from tool configuration or parameters
        operation = params.get("operation") or tool.config.get("operation", "create_task")
        
        # Remove operation from params to avoid conflicts
        clean_params = {k: v for k, v in params.items() if k != "operation"}
        
        # Execute the scheduling operation
        result = await execute_scheduling_operation(operation, **clean_params)
        
        logger.info(f"Scheduling tool {tool.toolId} executed operation {operation}")
        return result
        
    except Exception as e:
        logger.error(f"Error in scheduling tool {tool.toolId}: {str(e)}")
        raise ToolExecutionError(f"Scheduling operation failed: {str(e)}")

TOOL_REGISTRY['SCHEDULING'] = execute_scheduling_tool

# Add Email tool to registry
from .email_tool import execute_email_tool
TOOL_REGISTRY['EMAIL'] = execute_email_tool

def add_tool_type(tool_type: str, executor_func: Callable) -> None:
    """
    Safely add a new tool type to the registry.
    
    Args:
        tool_type: The type identifier for the tool
        executor_func: The async function to execute the tool
    """
    if tool_type in TOOL_REGISTRY:
        logger.warning(f"Tool type {tool_type} already exists, overwriting")
    
    # Validate tool type name
    if not re.match(r'^[A-Z][A-Z0-9_]*$', tool_type):
        raise ValueError(f"Invalid tool type name: {tool_type}")
    
    TOOL_REGISTRY[tool_type] = executor_func
    ALLOWED_TOOL_TYPES.add(tool_type)
    logger.info(f"Added tool type: {tool_type}")

def remove_tool_type(tool_type: str) -> None:
    """
    Safely remove a tool type from the registry.
    
    Args:
        tool_type: The type identifier to remove
    """
    if tool_type in TOOL_REGISTRY:
        del TOOL_REGISTRY[tool_type]
        ALLOWED_TOOL_TYPES.discard(tool_type)
        logger.info(f"Removed tool type: {tool_type}")
    else:
        logger.warning(f"Tool type {tool_type} not found in registry")
