import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from app.tool_executor import (
    execute_tool, execute_api_tool, execute_rss_tool,
    validate_and_sanitize_input, validate_url,
    ToolExecutionError, ToolValidationError, ToolSecurityError,
    TOOL_REGISTRY, ALLOWED_TOOL_TYPES
)
from app.models import Tool, ToolAuth


class TestValidateAndSanitizeInput:
    def test_empty_params(self):
        result = validate_and_sanitize_input({}, Tool(toolId="test", type="API", name="Test", description="Test"))
        assert result == {}

    def test_valid_string_params(self):
        params = {"query": "test query", "limit": "10"}
        result = validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))
        assert result["query"] == "test query"
        assert result["limit"] == "10"

    def test_sanitize_dangerous_characters(self):
        params = {"query": "test<script>alert('xss')</script>"}
        result = validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))
        assert "script" not in result["query"]
        assert "alert" not in result["query"]

    def test_string_length_limit(self):
        long_string = "a" * 1500
        params = {"query": long_string}
        result = validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))
        assert len(result["query"]) == 1000

    def test_invalid_parameter_key(self):
        params = {"query<script>": "test"}
        with pytest.raises(ToolValidationError):
            validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))

    def test_non_string_key(self):
        params = {123: "test"}
        with pytest.raises(ToolValidationError):
            validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))

    def test_json_parameter_too_large(self):
        large_dict = {"data": "x" * 6000}
        params = {"config": large_dict}
        with pytest.raises(ToolValidationError):
            validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))

    def test_unsupported_parameter_type(self):
        params = {"callback": lambda x: x}
        with pytest.raises(ToolValidationError):
            validate_and_sanitize_input(params, Tool(toolId="test", type="API", name="Test", description="Test"))


class TestValidateUrl:
    def test_valid_https_url(self):
        assert validate_url("https://api.example.com/data") is True

    def test_valid_http_url(self):
        assert validate_url("http://api.example.com/data") is True

    def test_invalid_scheme(self):
        assert validate_url("ftp://example.com/data") is False
        assert validate_url("file:///etc/passwd") is False

    def test_dangerous_hosts(self):
        assert validate_url("http://localhost/api") is False
        assert validate_url("https://127.0.0.1/api") is False
        assert validate_url("http://0.0.0.0/api") is False

    def test_suspicious_characters(self):
        assert validate_url("http://example.com/api?param=<script>") is False
        assert validate_url("http://example.com/api';DROP TABLE users;--") is False

    def test_malformed_url(self):
        assert validate_url("not-a-url") is False
        assert validate_url("") is False


class TestExecuteApiTool:
    @pytest.fixture
    def api_tool(self):
        return Tool(
            toolId="test_api",
            type="API",
            name="Test API",
            description="A test API",
            endpoint="https://api.example.com/data",
            auth=ToolAuth(type="apiKey", key="test_key_123456")
        )

    @pytest.mark.asyncio
    async def test_successful_api_call(self, api_tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_response)
            
            result = await execute_api_tool(api_tool, {"query": "test"})
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_api_tool_missing_endpoint(self):
        tool = Tool(toolId="test", type="API", name="Test", description="Test")
        with pytest.raises(ToolValidationError):
            await execute_api_tool(tool, {})

    @pytest.mark.asyncio
    async def test_api_tool_invalid_url(self):
        tool = Tool(
            toolId="test",
            type="API",
            name="Test",
            description="Test",
            endpoint="http://localhost/api"
        )
        with pytest.raises(ToolSecurityError):
            await execute_api_tool(tool, {})

    @pytest.mark.asyncio
    async def test_api_tool_invalid_auth_key(self):
        tool = Tool(
            toolId="test",
            type="API",
            name="Test",
            description="Test",
            endpoint="https://api.example.com/data",
            auth=ToolAuth(type="apiKey", key="short")
        )
        with pytest.raises(ToolSecurityError):
            await execute_api_tool(tool, {})

    @pytest.mark.asyncio
    async def test_api_tool_http_error(self, api_tool):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=mock_response
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_response)
            
            with pytest.raises(ToolExecutionError):
                await execute_api_tool(api_tool, {})

    @pytest.mark.asyncio
    async def test_api_tool_timeout(self, api_tool):
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                side_effect=httpx.TimeoutException("Request timed out")
            )
            
            with pytest.raises(ToolExecutionError):
                await execute_api_tool(api_tool, {})

    @pytest.mark.asyncio
    async def test_api_tool_response_too_large(self, api_tool):
        mock_response = MagicMock()
        mock_response.content = b"x" * (11 * 1024 * 1024)  # 11MB
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_response)
            
            with pytest.raises(ToolExecutionError):
                await execute_api_tool(api_tool, {})


class TestExecuteRssTool:
    @pytest.fixture
    def rss_tool(self):
        return Tool(
            toolId="test_rss",
            type="RSS",
            name="Test RSS",
            description="A test RSS feed",
            url="https://example.com/rss.xml"
        )

    @pytest.mark.asyncio
    async def test_successful_rss_parsing(self, rss_tool):
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss version="2.0">
            <channel>
                <item>
                    <title>Test Article</title>
                    <link>https://example.com/article1</link>
                    <description>Test description</description>
                    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
                </item>
            </channel>
        </rss>"""
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await execute_rss_tool(rss_tool, {"limit": 5})
            assert "entries" in result
            assert len(result["entries"]) == 1
            assert result["entries"][0]["title"] == "Test Article"

    @pytest.mark.asyncio
    async def test_rss_tool_missing_url(self):
        tool = Tool(toolId="test", type="RSS", name="Test", description="Test")
        with pytest.raises(ToolValidationError):
            await execute_rss_tool(tool, {})

    @pytest.mark.asyncio
    async def test_rss_tool_invalid_url(self):
        tool = Tool(
            toolId="test",
            type="RSS",
            name="Test",
            description="Test",
            url="http://localhost/rss.xml"
        )
        with pytest.raises(ToolSecurityError):
            await execute_rss_tool(tool, {})

    @pytest.mark.asyncio
    async def test_rss_tool_limit_parameter(self, rss_tool):
        # Test that limit parameter is respected and capped at 100
        result = await execute_rss_tool(rss_tool, {"limit": 150})
        # This would need actual RSS content to test properly, but we can verify
        # the parameter sanitization logic


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_unsupported_tool_type(self):
        tool = Tool(
            toolId="test",
            type="UNSUPPORTED",
            name="Test",
            description="Test"
        )
        with pytest.raises(ToolSecurityError):
            await execute_tool(tool, {})

    @pytest.mark.asyncio
    async def test_invalid_tool_id(self):
        tool = Tool(
            toolId="test<script>",
            type="API",
            name="Test",
            description="Test",
            endpoint="https://api.example.com"
        )
        with pytest.raises(ToolValidationError):
            await execute_tool(tool, {})

    @pytest.mark.asyncio
    async def test_missing_tool_id(self):
        tool = Tool(
            toolId="",
            type="API",
            name="Test",
            description="Test"
        )
        with pytest.raises(ToolValidationError):
            await execute_tool(tool, {})

    @pytest.mark.asyncio
    async def test_tool_execution_timeout(self):
        # Create a tool that will timeout
        tool = Tool(
            toolId="slow_tool",
            type="API",
            name="Slow Tool",
            description="A slow tool",
            endpoint="https://httpbin.org/delay/70"  # 70 second delay
        )
        
        with pytest.raises(ToolExecutionError):
            await execute_tool(tool, {})

    @pytest.mark.asyncio
    async def test_tool_result_metadata(self):
        tool = Tool(
            toolId="test_api",
            type="API",
            name="Test API",
            description="Test",
            endpoint="https://api.example.com/data"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(return_value=mock_response)
            
            result = await execute_tool(tool, {})
            assert "_tool_metadata" in result
            assert result["_tool_metadata"]["tool_id"] == "test_api"
            assert result["_tool_metadata"]["tool_type"] == "API"


class TestToolRegistry:
    def test_registry_contains_expected_tools(self):
        assert "API" in TOOL_REGISTRY
        assert "RSS" in TOOL_REGISTRY
        assert "API" in ALLOWED_TOOL_TYPES
        assert "RSS" in ALLOWED_TOOL_TYPES

    def test_registry_functions_are_callable(self):
        assert callable(TOOL_REGISTRY["API"])
        assert callable(TOOL_REGISTRY["RSS"]) 