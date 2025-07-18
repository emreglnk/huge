from typing import Dict, Any, List

from .models import AgentModel, Workflow, WorkflowNode
from .data_handler import get_user_data_collection
from .tool_executor import execute_tool, ToolExecutionError
from .llm_handler import get_llm_response

class WorkflowExecutionError(Exception):
    pass

class WorkflowExecutor:
    def __init__(self, agent_config: AgentModel):
        self.agent_config = agent_config
        self.context: Dict[str, Any] = {}

    async def execute_node(self, node: WorkflowNode):
        node_type = node.type
        if node_type == 'llm_prompt':
            # Resolve prompt from context if it's a variable
            prompt_template = node.prompt
            resolved_prompt = prompt_template.format(**self.context)

            # This could be customized further in the node definition.
            llm_response = await get_llm_response(
                llm_config=self.agent_config.llmConfig,
                system_prompt=self.agent_config.systemPrompt,
                user_message=resolved_prompt
            )
            if node.output_variable:
                self.context[node.output_variable] = llm_response
            print(f"LLM responded to prompt '{resolved_prompt}': {llm_response}")
        elif node_type == 'data_store':
            await self.execute_data_store_node(node)
        elif node_type == 'tool_call':
            await self.execute_tool_call_node(node)
        elif node_type == 'send_response':
            # In a real scenario, this would send a message to the user.
            print(f"Sending response: {self.context.get(node.message.strip('$'))}")
        else:
            raise WorkflowExecutionError(f"Unsupported node type: {node_type}")

    async def execute_data_store_node(self, node: WorkflowNode):
        collection = get_user_data_collection(self.agent_config)
        action = node.action
        data_to_store = self.context.get(node.data.strip('$')) if node.data.startswith('$') else node.data

        if action == 'append':
            await collection.insert_one(data_to_store)
            print(f"Stored data in {collection.name}: {data_to_store}")
        else:
            raise WorkflowExecutionError(f"Unsupported data store action: {action}")

    async def execute_tool_call_node(self, node: WorkflowNode):
        tool_to_execute = next((t for t in self.agent_config.tools if t.toolId == node.toolId), None)
        if not tool_to_execute:
            raise WorkflowExecutionError(f"Tool {node.toolId} not found in agent configuration.")
        
        # For simplicity, assuming params are not dynamically pulled from context for now
        result = await execute_tool(tool_to_execute)
        if node.output_variable:
            self.context[node.output_variable] = result
        print(f"Executed tool {node.toolId} with result: {result}")

    async def run(self, workflow_id: str, initial_context: Dict[str, Any] = None):
        if initial_context:
            self.context.update(initial_context)

        workflow_to_run = next((w for w in self.agent_config.workflows if w.workflowId == workflow_id), None)
        if not workflow_to_run:
            raise WorkflowExecutionError(f"Workflow {workflow_id} not found.")

        for node in sorted(workflow_to_run.nodes, key=lambda n: int(n.nodeId)):
            await self.execute_node(node)

        return self.context
