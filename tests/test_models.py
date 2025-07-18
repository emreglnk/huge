import pytest
from pydantic import ValidationError
from app.models import (
    AgentModel, Tool, ToolAuth, DataSchema, 
    WorkflowNode, Workflow, Schedule, LlmConfig
)


class TestToolAuth:
    def test_valid_tool_auth(self):
        auth = ToolAuth(type="apiKey", key="test_key_123")
        assert auth.type == "apiKey"
        assert auth.key == "test_key_123"

    def test_tool_auth_missing_fields(self):
        with pytest.raises(ValidationError):
            ToolAuth(type="apiKey")  # Missing key


class TestTool:
    def test_valid_api_tool(self):
        tool = Tool(
            toolId="test_api",
            type="API",
            name="Test API",
            description="A test API tool",
            endpoint="https://api.example.com/data",
            auth=ToolAuth(type="apiKey", key="test_key")
        )
        assert tool.toolId == "test_api"
        assert tool.type == "API"
        assert tool.endpoint == "https://api.example.com/data"

    def test_valid_rss_tool(self):
        tool = Tool(
            toolId="test_rss",
            type="RSS",
            name="Test RSS",
            description="A test RSS tool",
            url="https://example.com/rss.xml"
        )
        assert tool.toolId == "test_rss"
        assert tool.type == "RSS"
        assert tool.url == "https://example.com/rss.xml"

    def test_tool_missing_required_fields(self):
        with pytest.raises(ValidationError):
            Tool(type="API", name="Test")  # Missing toolId and description


class TestDataSchema:
    def test_valid_data_schema(self):
        schema = DataSchema(
            collectionName="test_collection",
            schema_definition={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"}
                }
            }
        )
        assert schema.collectionName == "test_collection"
        assert schema.schema_definition["type"] == "object"

    def test_data_schema_with_alias(self):
        # Test that the 'schema' alias works
        schema_data = {
            "collectionName": "test_collection",
            "schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"}
                }
            }
        }
        schema = DataSchema(**schema_data)
        assert schema.collectionName == "test_collection"
        assert schema.schema_definition["type"] == "object"


class TestWorkflowNode:
    def test_basic_workflow_node(self):
        node = WorkflowNode(
            nodeId="1",
            type="llm_prompt",
            prompt="Test prompt",
            output_variable="result"
        )
        assert node.nodeId == "1"
        assert node.type == "llm_prompt"
        assert node.prompt == "Test prompt"
        assert node.output_variable == "result"

    def test_workflow_node_with_failure_handling(self):
        node = WorkflowNode(
            nodeId="1",
            type="tool_call",
            toolId="test_tool",
            on_failure="continue",
            continue_on_error=True,
            max_retries=5,
            retry_delay=2.0
        )
        assert node.on_failure == "continue"
        assert node.continue_on_error is True
        assert node.max_retries == 5
        assert node.retry_delay == 2.0

    def test_workflow_node_defaults(self):
        node = WorkflowNode(nodeId="1", type="llm_prompt")
        assert node.continue_on_error is False
        assert node.max_retries == 3
        assert node.retry_delay == 1.0
        assert node.timeout == 30
        assert node.validate_input is True
        assert node.sanitize_output is True


class TestWorkflow:
    def test_valid_workflow(self):
        nodes = [
            WorkflowNode(nodeId="1", type="llm_prompt", prompt="Test"),
            WorkflowNode(nodeId="2", type="send_response", message="Done")
        ]
        workflow = Workflow(
            workflowId="test_workflow",
            description="A test workflow",
            trigger="test_trigger",
            nodes=nodes
        )
        assert workflow.workflowId == "test_workflow"
        assert len(workflow.nodes) == 2
        assert workflow.nodes[0].nodeId == "1"


class TestSchedule:
    def test_valid_schedule(self):
        schedule = Schedule(
            scheduleId="daily_task",
            cron="0 9 * * *",
            description="Daily morning task",
            workflowId="morning_workflow"
        )
        assert schedule.scheduleId == "daily_task"
        assert schedule.cron == "0 9 * * *"
        assert schedule.workflowId == "morning_workflow"


class TestLlmConfig:
    def test_default_llm_config(self):
        config = LlmConfig()
        assert config.provider == "openai"
        assert config.model == "gpt-3.5-turbo"

    def test_custom_llm_config(self):
        config = LlmConfig(provider="gemini", model="gemini-pro")
        assert config.provider == "gemini"
        assert config.model == "gemini-pro"


class TestAgentModel:
    def test_minimal_agent_model(self):
        agent = AgentModel(
            owner="test_user",
            agentId="test_agent",
            agentName="Test Agent",
            version="1.0",
            systemPrompt="You are a test agent",
            dataSchema=DataSchema(
                collectionName="test_data",
                schema_definition={"type": "object", "properties": {}}
            ),
            tools=[],
            workflows=[],
            schedules=[]
        )
        assert agent.owner == "test_user"
        assert agent.agentId == "test_agent"
        assert agent.llmConfig.provider == "openai"  # Default value

    def test_complete_agent_model(self):
        tool = Tool(
            toolId="test_tool",
            type="API",
            name="Test Tool",
            description="A test tool",
            endpoint="https://api.example.com"
        )
        
        node = WorkflowNode(
            nodeId="1",
            type="llm_prompt",
            prompt="Test prompt"
        )
        
        workflow = Workflow(
            workflowId="test_workflow",
            description="Test workflow",
            trigger="test",
            nodes=[node]
        )
        
        schedule = Schedule(
            scheduleId="test_schedule",
            cron="0 * * * *",
            description="Hourly test",
            workflowId="test_workflow"
        )
        
        agent = AgentModel(
            owner="test_user",
            agentId="test_agent",
            agentName="Test Agent",
            version="1.0",
            systemPrompt="You are a test agent",
            llmConfig=LlmConfig(provider="gemini", model="gemini-pro"),
            dataSchema=DataSchema(
                collectionName="test_data",
                schema_definition={"type": "object", "properties": {}}
            ),
            tools=[tool],
            workflows=[workflow],
            schedules=[schedule]
        )
        
        assert len(agent.tools) == 1
        assert len(agent.workflows) == 1
        assert len(agent.schedules) == 1
        assert agent.llmConfig.provider == "gemini"

    def test_agent_model_validation_errors(self):
        # Test missing required fields
        with pytest.raises(ValidationError):
            AgentModel(
                agentId="test_agent",
                agentName="Test Agent"
                # Missing other required fields
            )

        # Test invalid data types
        with pytest.raises(ValidationError):
            AgentModel(
                owner="test_user",
                agentId="test_agent",
                agentName="Test Agent",
                version="1.0",
                systemPrompt="You are a test agent",
                dataSchema="invalid_schema",  # Should be DataSchema object
                tools=[],
                workflows=[],
                schedules=[]
            ) 