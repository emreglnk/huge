import httpx
import feedparser
from typing import List, Dict, Any, Callable

from .models import Tool

class ToolExecutionError(Exception):
    pass

async def execute_api_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes an API tool by making an HTTP request."""
    headers = {}
    if tool.auth and tool.auth.type == 'apiKey':
        # This is a simplified example. In a real application, you would handle different
        # auth types (e.g., header, query param) and secure key storage.
        headers['Authorization'] = f"Bearer {tool.auth.key}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(tool.endpoint, params=params, headers=headers)
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()
        except httpx.RequestError as e:
            raise ToolExecutionError(f"API request failed for tool {tool.toolId}: {e}")
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(f"API request for tool {tool.toolId} returned status {e.response.status_code}: {e.response.text}")

async def execute_rss_tool(tool: Tool, params: Dict[str, Any]) -> Dict[str, Any]:
    """Executes an RSS tool by parsing a feed URL."""
    try:
        feed = feedparser.parse(tool.url)
        if feed.bozo:
            raise ToolExecutionError(f"Failed to parse RSS feed for tool {tool.toolId}: {feed.bozo_exception}")
        return {"entries": [entry for entry in feed.entries]}
    except Exception as e:
        raise ToolExecutionError(f"Error fetching RSS feed for tool {tool.toolId}: {e}")

TOOL_REGISTRY: Dict[str, Callable] = {
    'API': execute_api_tool,
    'RSS': execute_rss_tool,
}

async def execute_tool(tool: Tool, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dynamically executes a tool based on its type.

    Args:
        tool: The Tool object from the agent's configuration.
        params: A dictionary of parameters to pass to the tool.

    Returns:
        The result of the tool's execution.
    """
    if params is None:
        params = {}

    executor = TOOL_REGISTRY.get(tool.type)
    if not executor:
        raise ToolExecutionError(f"Unsupported tool type: {tool.type}")

    return await executor(tool, params)
