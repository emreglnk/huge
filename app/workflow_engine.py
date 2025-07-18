import logging
import asyncio
from typing import Dict, Any, List, Optional
from functools import wraps

from .models import AgentModel, Workflow, WorkflowNode
from .data_handler import get_user_data_collection
from .tool_executor import execute_tool, ToolExecutionError
from .llm_handler import get_llm_response

# Configure logging
logger = logging.getLogger(__name__)

class WorkflowExecutionError(Exception):
    pass

class WorkflowStepError(Exception):
    """Raised when a specific workflow step fails"""
    def __init__(self, node_id: str, message: str, original_error: Exception = None):
        self.node_id = node_id
        self.original_error = original_error
        super().__init__(f"Step {node_id} failed: {message}")

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying async functions on failure"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. Retrying in {delay}s...")
                        await asyncio.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {str(e)}")
            raise last_exception
        return wrapper
    return decorator

class WorkflowExecutor:
    def __init__(self, agent_config: AgentModel):
        self.agent_config = agent_config
        self.context: Dict[str, Any] = {}
        self.execution_log: List[Dict[str, Any]] = []
        self.failed_steps: List[Dict[str, Any]] = []

    def _log_step(self, node_id: str, step_type: str, status: str, details: Dict[str, Any] = None):
        """Log workflow step execution"""
        log_entry = {
            "node_id": node_id,
            "step_type": step_type,
            "status": status,
            "timestamp": asyncio.get_event_loop().time(),
            "details": details or {}
        }
        self.execution_log.append(log_entry)
        
        if status == "failed":
            self.failed_steps.append(log_entry)
            logger.error(f"Workflow step failed - Node: {node_id}, Type: {step_type}, Details: {details}")
        else:
            logger.info(f"Workflow step {status} - Node: {node_id}, Type: {step_type}")

    async def execute_node(self, node: WorkflowNode) -> bool:
        """Execute a workflow node with comprehensive error handling"""
        node_id = node.nodeId
        node_type = node.type
        
        try:
            logger.info(f"Executing workflow node {node_id} of type {node_type}")
            
            if node_type == 'llm_prompt':
                await self._execute_llm_node(node)
            elif node_type == 'data_store':
                await self._execute_data_store_node(node)
            elif node_type == 'tool_call':
                await self._execute_tool_call_node(node)
            elif node_type == 'send_response':
                await self._execute_send_response_node(node)
            elif node_type == 'conditional_logic':
                return await self._execute_conditional_node(node)
            else:
                raise WorkflowStepError(node_id, f"Unsupported node type: {node_type}")
                
            self._log_step(node_id, node_type, "success")
            return True
            
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "node_config": node.dict()
            }
            self._log_step(node_id, node_type, "failed", error_details)
            
            # Handle on_failure if defined
            if hasattr(node, 'on_failure') and node.on_failure:
                logger.info(f"Executing on_failure action for node {node_id}: {node.on_failure}")
                return await self._handle_failure_action(node, e)
            
            # Re-raise the error if no failure handling is defined
            raise WorkflowStepError(node_id, str(e), e)

    @retry_on_failure(max_retries=3, delay=1.0)
    async def _execute_llm_node(self, node: WorkflowNode):
        """Execute LLM prompt node with retry mechanism"""
        try:
            # Resolve prompt from context if it's a variable
            prompt_template = node.prompt or ""
            resolved_prompt = prompt_template.format(**self.context)

            llm_response = await get_llm_response(
                llm_config=self.agent_config.llmConfig,
                system_prompt=self.agent_config.systemPrompt,
                user_message=resolved_prompt
            )
            
            if node.output_variable:
                self.context[node.output_variable] = llm_response
                
            logger.debug(f"LLM response for node {node.nodeId}: {llm_response}")
            
        except Exception as e:
            logger.error(f"LLM execution failed for node {node.nodeId}: {str(e)}")
            raise

    async def _execute_data_store_node(self, node: WorkflowNode):
        """Execute data store node with error handling"""
        try:
            collection = get_user_data_collection(self.agent_config)
            action = node.action
            
            # Safely resolve data from context
            if node.data and node.data.startswith('$'):
                variable_name = node.data.strip('$')
                if variable_name not in self.context:
                    raise WorkflowStepError(node.nodeId, f"Variable '{variable_name}' not found in context")
                data_to_store = self.context[variable_name]
            else:
                data_to_store = node.data

            if action == 'append':
                result = await collection.insert_one(data_to_store)
                logger.debug(f"Data stored in {collection.name} with ID: {result.inserted_id}")
            elif action == 'update':
                # Implement update logic if needed
                raise WorkflowStepError(node.nodeId, "Update action not yet implemented")
            else:
                raise WorkflowStepError(node.nodeId, f"Unsupported data store action: {action}")
                
        except Exception as e:
            logger.error(f"Data store execution failed for node {node.nodeId}: {str(e)}")
            raise

    @retry_on_failure(max_retries=3, delay=1.0)
    async def _execute_tool_call_node(self, node: WorkflowNode):
        """Execute tool call node with retry mechanism"""
        try:
            tool_id = getattr(node, 'toolId', None)
            if not tool_id:
                raise WorkflowStepError(node.nodeId, "Tool ID not specified in node")
                
            tool_to_execute = next((t for t in self.agent_config.tools if t.toolId == tool_id), None)
            if not tool_to_execute:
                raise WorkflowStepError(node.nodeId, f"Tool {tool_id} not found in agent configuration")
            
            # Prepare parameters from context if specified
            params = {}
            if hasattr(node, 'params') and node.params:
                for key, value in node.params.items():
                    if isinstance(value, str) and value.startswith('$'):
                        variable_name = value.strip('$')
                        if variable_name in self.context:
                            params[key] = self.context[variable_name]
                        else:
                            logger.warning(f"Variable '{variable_name}' not found in context for tool {tool_id}")
                    else:
                        params[key] = value
            
            result = await execute_tool(tool_to_execute, params)
            
            if node.output_variable:
                self.context[node.output_variable] = result
                
            logger.debug(f"Tool {tool_id} executed successfully for node {node.nodeId}")
            
        except ToolExecutionError as e:
            logger.error(f"Tool execution failed for node {node.nodeId}: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in tool execution for node {node.nodeId}: {str(e)}")
            raise

    async def _execute_send_response_node(self, node: WorkflowNode):
        """Execute send response node"""
        try:
            message = node.message or ""
            
            # Resolve message from context if it's a variable
            if message.startswith('$'):
                variable_name = message.strip('$')
                if variable_name not in self.context:
                    raise WorkflowStepError(node.nodeId, f"Variable '{variable_name}' not found in context")
                resolved_message = self.context[variable_name]
            else:
                resolved_message = message.format(**self.context)
            
            # Store the response in context for potential use by calling code
            self.context['_last_response'] = resolved_message
            logger.info(f"Response prepared for node {node.nodeId}: {resolved_message}")
            
        except Exception as e:
            logger.error(f"Send response execution failed for node {node.nodeId}: {str(e)}")
            raise

    async def _execute_conditional_node(self, node: WorkflowNode) -> bool:
        """Execute conditional logic node"""
        try:
            condition = getattr(node, 'condition', None)
            if not condition:
                raise WorkflowStepError(node.nodeId, "Condition not specified in conditional node")
            
            # Simple condition evaluation (can be expanded)
            # For now, support basic comparisons like "variable > 10"
            # In production, you'd want a more sophisticated expression evaluator
            
            # This is a simplified implementation - in production, use a proper expression evaluator
            logger.warning(f"Conditional logic not fully implemented for node {node.nodeId}")
            return True
            
        except Exception as e:
            logger.error(f"Conditional execution failed for node {node.nodeId}: {str(e)}")
            raise

    async def _handle_failure_action(self, node: WorkflowNode, original_error: Exception) -> bool:
        """Handle failure actions defined in node configuration"""
        try:
            failure_action = getattr(node, 'on_failure', None)
            if not failure_action:
                return False
                
            if failure_action == 'continue':
                logger.info(f"Continuing workflow despite failure in node {node.nodeId}")
                return True
            elif failure_action == 'stop':
                logger.info(f"Stopping workflow due to failure in node {node.nodeId}")
                return False
            elif failure_action == 'retry':
                logger.info(f"Retrying node {node.nodeId} due to failure")
                # This would need additional retry logic specific to failure handling
                return False
            else:
                logger.warning(f"Unknown failure action '{failure_action}' for node {node.nodeId}")
                return False
                
        except Exception as e:
            logger.error(f"Error handling failure action for node {node.nodeId}: {str(e)}")
            return False

    async def run(self, workflow_id: str, initial_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run workflow with comprehensive error handling and logging"""
        try:
            logger.info(f"Starting workflow execution: {workflow_id}")
            
            if initial_context:
                self.context.update(initial_context)
                logger.debug(f"Initial context: {initial_context}")

            workflow_to_run = next((w for w in self.agent_config.workflows if w.workflowId == workflow_id), None)
            if not workflow_to_run:
                raise WorkflowExecutionError(f"Workflow {workflow_id} not found in agent configuration")

            # Sort nodes by nodeId for sequential execution
            sorted_nodes = sorted(workflow_to_run.nodes, key=lambda n: int(n.nodeId))
            
            for node in sorted_nodes:
                try:
                    should_continue = await self.execute_node(node)
                    if not should_continue:
                        logger.info(f"Workflow execution stopped at node {node.nodeId}")
                        break
                except WorkflowStepError as e:
                    logger.error(f"Workflow step failed: {str(e)}")
                    # Check if workflow should continue on error
                    if not getattr(node, 'continue_on_error', False):
                        raise WorkflowExecutionError(f"Workflow {workflow_id} failed at step {node.nodeId}: {str(e)}")
                    else:
                        logger.info(f"Continuing workflow despite error in node {node.nodeId}")

            logger.info(f"Workflow {workflow_id} completed successfully")
            
            # Add execution summary to context
            self.context['_execution_summary'] = {
                'workflow_id': workflow_id,
                'total_steps': len(sorted_nodes),
                'failed_steps': len(self.failed_steps),
                'execution_log': self.execution_log
            }
            
            return self.context
            
        except Exception as e:
            logger.error(f"Workflow execution failed for {workflow_id}: {str(e)}")
            raise WorkflowExecutionError(f"Workflow {workflow_id} execution failed: {str(e)}")

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get detailed execution summary"""
        return {
            'execution_log': self.execution_log,
            'failed_steps': self.failed_steps,
            'context': self.context,
            'total_steps_executed': len(self.execution_log),
            'failed_step_count': len(self.failed_steps)
        }
