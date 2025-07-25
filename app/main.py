from fastapi import FastAPI, Body, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional, AsyncGenerator
from datetime import timedelta
import logging
import os
import json
import asyncio

from .db import agent_collection, close_db_client
from .models import AgentModel, UpdateAgentModel, User, Token
from .agent_loader import load_agent_config, AgentNotFoundException
from .file_agent_manager import file_agent_manager
from .data_handler import get_user_data_collection
from .tool_executor import execute_tool, ToolExecutionError
from .workflow_engine import WorkflowExecutor, WorkflowExecutionError
from .scheduler import scheduler, schedule_workflow_for_agent
from .llm_handler import get_llm_response
from .master_agent import process_user_input, create_agent_from_conversation
from .smart_master_agent import process_smart_conversation, create_agent_from_smart_conversation
from .session_manager import session_manager
from .auth import ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token, get_current_active_user, verify_password
from .users import create_user as create_db_user, get_user
from .telegram_auth_manager import telegram_auth_manager
from .telegram_webhook import telegram_webhook_handler
from .telegram_polling_service import telegram_polling_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Agent Platform",
    description="A unified platform for managing AI agents with dynamic workflows and tools",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Serve the main page
@app.get("/")
async def serve_main_page():
    return FileResponse("app/static/index.html")

# Serve the chat page
@app.get("/chat/{agent_id}")
async def serve_chat_page(agent_id: str):
    return FileResponse("app/static/chat.html")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up AI Agent Platform...")
    
    # Debug: Check if TELEGRAM_BOT_TOKEN is loaded
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    if telegram_token:
        logger.info(f"✅ TELEGRAM_BOT_TOKEN loaded successfully (length: {len(telegram_token)})")
    else:
        logger.warning("❌ TELEGRAM_BOT_TOKEN not found in environment variables")
    
    await session_manager.initialize()
    try:
        # Load agents from file system
        agents = file_agent_manager.list_agents()
        for agent in agents:
            try:
                schedule_workflow_for_agent(agent)
            except Exception as e:
                logger.error(f"Error loading agent {agent.agentId}: {str(e)}")
        
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started successfully")
        
        # Start Telegram polling service
        if telegram_polling_service.enabled:
            asyncio.create_task(telegram_polling_service.start_polling())
            logger.info("🤖 Telegram polling service started")
        else:
            logger.warning("⚠️ Telegram polling service disabled (no bot token)")
            
        # Log agent stats
        stats = file_agent_manager.get_agent_stats()
        logger.info(f"Loaded {stats['total_agents']} agents from {stats['agents_directory']}")
        
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Agent Platform...")
    try:
        # Stop Telegram polling service
        if telegram_polling_service.polling:
            await telegram_polling_service.stop_polling()
            logger.info("🤖 Telegram polling service stopped")
        
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped successfully")
        
        await session_manager.cleanup()
        await close_db_client()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")

# --- Authentication Endpoints ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        user = await get_user(form_data.username)
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/auth/login", response_model=Token)
async def login_endpoint(form_data: OAuth2PasswordRequestForm = Depends()):
    """Alternative login endpoint for frontend compatibility"""
    return await login_for_access_token(form_data)

@app.post("/register", response_model=User)
async def register_user(user: User):
    try:
        db_user = await get_user(user.username)
        if db_user:
            raise HTTPException(status_code=400, detail="Username already registered")
        created_user = await create_db_user(user)
        return created_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

# --- Basic Health Check ---
@app.get("/")
async def read_root():
    return FileResponse("app/static/index.html")

@app.get("/health")
async def health_check():
    try:
        # Check database connection
        await agent_collection.find_one()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}

# --- Agent Management Endpoints ---
@app.post("/agents/", response_description="Add new agent", response_model=AgentModel)
async def create_agent(agent: AgentModel = Body(...), current_user: User = Depends(get_current_active_user)):
    try:
        agent.owner = current_user.username
        
        # Save to file system
        if file_agent_manager.save_agent(agent):
            schedule_workflow_for_agent(agent)
            logger.info(f"Agent {agent.agentId} created successfully by {current_user.username}")
            return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(agent.model_dump(by_alias=True)))
        else:
            raise HTTPException(status_code=500, detail="Failed to save agent to file")
            
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create agent")

@app.get("/agents/", response_description="List all agents for the current user", response_model=List[AgentModel])
async def list_agents(current_user: User = Depends(get_current_active_user)):
    try:
        logger.info(f"Listing agents for user: {current_user.username}")
        agents = file_agent_manager.list_agents(owner=current_user.username)
        logger.info(f"Found {len(agents)} agents for user {current_user.username}")
        for agent in agents:
            logger.info(f"  - Agent: {agent.agentId}, Name: {agent.agentName}, Owner: {agent.owner}")
        return agents
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list agents")

@app.get("/agents/{id}", response_description="Get a single agent", response_model=AgentModel)
async def show_agent(id: str, current_user: User = Depends(get_current_active_user)):
    try:
        agent = file_agent_manager.get_agent(id, current_user.username)
        if agent:
            return agent
        else:
            raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have access.")
    except Exception as e:
        logger.error(f"Error retrieving agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent")

@app.put("/agents/{id}", response_description="Update an agent", response_model=AgentModel)
async def update_agent(id: str, agent_update: UpdateAgentModel = Body(...), current_user: User = Depends(get_current_active_user)):
    try:
        # Get existing agent
        existing_agent = file_agent_manager.get_agent(id, current_user.username)
        if not existing_agent:
            raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have access.")
        
        # Update agent with new data
        update_data = agent_update.model_dump(exclude_unset=True)
        updated_agent_data = existing_agent.model_dump()
        updated_agent_data.update(update_data)
        
        # Create updated agent model
        updated_agent = AgentModel(**updated_agent_data)
        
        # Save updated agent
        if file_agent_manager.save_agent(updated_agent):
            schedule_workflow_for_agent(updated_agent)
            logger.info(f"Agent {id} updated successfully by {current_user.username}")
            return updated_agent
        else:
            raise HTTPException(status_code=500, detail="Failed to save updated agent")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update agent")

@app.delete("/agents/{id}", response_description="Delete an agent")
async def delete_agent(id: str, current_user: User = Depends(get_current_active_user)):
    try:
        # Get agent to verify ownership
        agent = file_agent_manager.get_agent(id, current_user.username)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have access.")

        # Delete agent file
        if file_agent_manager.delete_agent(id, current_user.username):
            logger.info(f"Agent {id} deleted successfully by {current_user.username}")
            return {"message": f"Agent {id} deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete agent")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")

# --- Agent Sharing Endpoints ---
@app.post("/agents/{id}/share")
async def share_agent(id: str, current_user: User = Depends(get_current_active_user)):
    """Make agent public for sharing"""
    try:
        logger.info(f"Attempting to share agent {id} by user {current_user.username}")
        
        # Get the agent
        agent = file_agent_manager.get_agent(id, current_user.username)
        if not agent:
            logger.warning(f"Agent {id} not found or access denied for user {current_user.username}")
            raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have access.")
        
        logger.info(f"Agent {id} found, current public status: {getattr(agent, 'public', False)}")
        
        # Add public flag to agent
        try:
            # Use the existing agent and just update the public flag
            agent.public = True
            logger.info(f"Set public flag to True for agent {id}")
            
            # Validate the updated agent
            updated_agent = agent
            logger.info(f"Agent ready for sharing")
            
        except Exception as model_error:
            logger.error(f"Error updating agent model: {str(model_error)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to update agent model: {str(model_error)}")
        
        # Save the updated agent
        try:
            save_result = file_agent_manager.save_agent(updated_agent)
            logger.info(f"Save result: {save_result}")
            
            if save_result:
                logger.info(f"Agent {id} shared publicly by {current_user.username}")
                return {"message": f"Agent {id} is now public", "share_url": f"/agents/public/{id}"}
            else:
                logger.error(f"Failed to save shared agent {id}")
                raise HTTPException(status_code=500, detail="Failed to save shared agent")
                
        except Exception as save_error:
            logger.error(f"Error saving shared agent {id}: {str(save_error)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to save agent: {str(save_error)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error sharing agent {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/agents/public", response_description="List all public agents")
async def list_public_agents():
    """List all publicly shared agents"""
    try:
        all_agents = file_agent_manager.list_agents()  # Get all agents
        public_agents = [agent for agent in all_agents if getattr(agent, 'public', False)]
        
        # Remove sensitive info for public listing
        public_agent_info = []
        for agent in public_agents:
            public_info = {
                "agentId": agent.agentId,
                "agentName": agent.agentName,
                "version": agent.version,
                "systemPrompt": agent.systemPrompt[:200] + "..." if len(agent.systemPrompt) > 200 else agent.systemPrompt,
                "owner": agent.owner,
                "tools": [{"name": tool.name, "type": tool.type, "description": tool.description} for tool in agent.tools]
            }
            public_agent_info.append(public_info)
        
        return public_agent_info
        
    except Exception as e:
        logger.error(f"Error listing public agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list public agents")

@app.post("/agents/public/{id}/copy")
async def copy_public_agent(id: str, current_user: User = Depends(get_current_active_user)):
    """Copy a public agent to user's collection"""
    try:
        # Get the public agent (without owner restriction)
        agent = file_agent_manager.get_agent(id)
        if not agent or not getattr(agent, 'public', False):
            raise HTTPException(status_code=404, detail=f"Public agent {id} not found.")
        
        # Create a copy with new ID and current user as owner
        agent_data = agent.model_dump()
        agent_data["agentId"] = f"{id}_copy_{current_user.username}"
        agent_data["agentName"] = f"{agent.agentName} (Copy)"
        agent_data["owner"] = current_user.username
        agent_data["public"] = False  # Copies are private by default
        
        copied_agent = AgentModel(**agent_data)
        
        if file_agent_manager.save_agent(copied_agent):
            logger.info(f"Public agent {id} copied by {current_user.username}")
            return {"message": "Agent copied successfully", "new_agent_id": copied_agent.agentId}
        else:
            raise HTTPException(status_code=500, detail="Failed to copy agent")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error copying public agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to copy agent")
        
        delete_result = await agent_collection.delete_one(query)

        if delete_result.deleted_count == 1:
            # Remove scheduled workflows
            for workflow in agent_model.workflows:
                if hasattr(workflow, 'schedule') and workflow.schedule:
                    job_id = f"agent_{agent_model.agentId}_workflow_{workflow.workflowId}"
                    try:
                        scheduler.remove_job(job_id)
                        logger.info(f"Removed job {job_id} from scheduler")
                    except Exception as e:
                        logger.warning(f"Job {job_id} not found in scheduler: {str(e)}")
            
            logger.info(f"Agent {id} deleted successfully by {current_user.username}")
            return JSONResponse(status_code=status.HTTP_204_NO_CONTENT)

        raise HTTPException(status_code=404, detail=f"Agent {id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete agent")

# --- Chat Endpoints ---
@app.get("/chat/{agent_id}")
async def chat_agent_ui(agent_id: str, current_user: User = Depends(get_current_active_user)):
    """Serve the chat UI for a specific agent"""
    try:
        # Verify that the agent exists and user has access
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to chat with this agent.")
        
        # Serve the chat interface HTML page
        return FileResponse('app/static/chat.html')
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving chat UI: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/chat/{agent_id}")
async def chat_with_agent(agent_id: str, message: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    try:
        # Verify agent exists and user has access
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to chat with this agent.")

        user_message = message.get("message", "")
        user_id = current_user.username
        session_id = message.get("sessionId", None)
        
        # Get or create user session
        if session_id:
            session = await session_manager.get_session_by_id(session_id)
            if not session or session.get('user_id') != user_id:
                session = await session_manager.get_or_create_session(user_id, agent_id)
        else:
            session = await session_manager.get_or_create_session(user_id, agent_id)
            
        session_id = session["session_id"]
        session_context = await session_manager.get_session_context(session_id)
        
        # Check for workflow triggers
        for workflow in agent_config.workflows:
            if workflow.trigger and workflow.trigger in user_message.lower():
                try:
                    executor = WorkflowExecutor(agent_config)
                    initial_context = {
                        "user_message": user_message,
                        "session_id": session_id,
                        "user_id": user_id,
                        **session_context
                    }
                    final_context = await executor.run(workflow.workflowId, initial_context)
                    
                    await session_manager.update_session_context(session_id, final_context)
                    await session_manager.add_to_history(
                        session_id,
                        user_message,
                        f"Workflow '{workflow.workflowId}' executed"
                    )
                    
                    return {
                        "status": f"Workflow '{workflow.workflowId}' executed.", 
                        "final_context": final_context,
                        "session_id": session_id
                    }
                except WorkflowExecutionError as e:
                    logger.error(f"Workflow execution error: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Error executing workflow {workflow.workflowId}: {e}")

        # If no workflow is triggered, get a response from the LLM
        history = await session_manager.get_session_history(session_id, limit=5)
        history_context = "\n".join([f"User: {h['user_message']}\nAssistant: {h['agent_response']}" for h in history])
        
        enhanced_system_prompt = agent_config.systemPrompt
        if history_context:
            enhanced_system_prompt = f"{agent_config.systemPrompt}\n\nPrevious conversation:\n{history_context}"
        
        # Add tool information to system prompt
        tools_info = ""
        if agent_config.tools:
            tools_info = "\n\n🔧 **Available Tools:**\n"
            for tool in agent_config.tools:
                tools_info += f"- **{tool.toolId}** ({tool.type}): {tool.description}\n"
            tools_info += "\n**To use a tool, include in your response:** `[TOOL_CALL: tool_id, {param1: value1, param2: value2}]`\n"
        
        enhanced_system_prompt_with_tools = enhanced_system_prompt + tools_info
        
        llm_response = await get_llm_response(
            llm_config=agent_config.llmConfig,
            system_prompt=enhanced_system_prompt_with_tools,
            user_message=user_message
        )
        
        # Check for tool calls in the response
        final_response = llm_response
        tool_results = []
        
        import re
        tool_call_pattern = r'\[TOOL_CALL:\s*([^,]+),\s*({[^}]*})\]'
        tool_calls = re.findall(tool_call_pattern, llm_response)
        
        for tool_id, params_str in tool_calls:
            tool_id = tool_id.strip()
            try:
                # Find the tool in agent config
                tool_config = None
                for tool in agent_config.tools:
                    if tool.toolId == tool_id:
                        tool_config = tool
                        break
                
                if tool_config:
                    # Parse parameters
                    import json
                    try:
                        params = json.loads(params_str)
                    except:
                        params = {}
                    
                    # Add user context for Telegram tools
                    if tool_config.type == "TELEGRAM":
                        if "chat_id" not in params:
                            params["chat_id"] = current_user.username
                    
                    logger.info(f"🔧 Executing tool {tool_id} with params: {params}")
                    
                    # Execute the tool
                    tool_result = await execute_tool(tool_config, params)
                    tool_results.append({
                        "tool_id": tool_id,
                        "result": tool_result
                    })
                    
                    logger.info(f"✅ Tool {tool_id} executed successfully: {tool_result}")
                    
                    # Remove the tool call from the response
                    final_response = final_response.replace(f"[TOOL_CALL: {tool_id}, {params_str}]", "")
                    
                else:
                    logger.warning(f"⚠️ Tool {tool_id} not found in agent configuration")
                    
            except Exception as e:
                logger.error(f"❌ Error executing tool {tool_id}: {str(e)}")
                tool_results.append({
                    "tool_id": tool_id,
                    "error": str(e)
                })
        
        await session_manager.add_to_history(session_id, user_message, final_response)
        await session_manager.update_session_context(session_id, {})
        
        response_data = {
            "agent_system_prompt": agent_config.systemPrompt,
            "user_message": user_message,
            "response": final_response,
            "session_id": session_id
        }
        
        if tool_results:
            response_data["tool_results"] = tool_results
            
        return response_data
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Debug Endpoints ---
@app.get("/debug/test")
async def debug_test():
    """Debug endpoint to test basic functionality"""
    try:
        return {"status": "ok", "message": "Debug endpoint working", "timestamp": "2025-07-18"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- Chat History Endpoints ---
@app.get("/chat/history/{agent_id}")
async def get_chat_history(agent_id: str, session_id: Optional[str] = None, limit: int = 10, current_user: User = Depends(get_current_active_user)):
    """Get chat history for a specific session or agent"""
    try:
        logger.info(f"Chat history request: agent={agent_id}, user={current_user.username}, session={session_id}, limit={limit}")
        
        # Verify agent exists and user has access
        logger.info(f"Verifying agent exists and user has access: {agent_id}")
        agent_config = await load_agent_config(agent_id)
        logger.info(f"Agent config loaded: {agent_id}, owner={agent_config.owner}")
        
        if agent_config.owner != current_user.username:
            logger.warning(f"Access denied: user {current_user.username} tried to access agent {agent_id} owned by {agent_config.owner}")
            raise HTTPException(status_code=403, detail="You do not have permission to access this agent's history.")
        
        user_id = current_user.username
        logger.info(f"Agent access verified for user {user_id}")
        
        if session_id:
            # Get history for specific session
            logger.info(f"Getting history for specific session: {session_id}")
            history = await session_manager.get_session_history(session_id, limit)
            logger.info(f"Retrieved history for session {session_id}: {len(history)} entries")
        else:
            # Get history from the latest session for this user and agent
            logger.info(f"Finding latest session for user={user_id}, agent={agent_id}")
            latest_session = await session_manager.find_latest_session(user_id, agent_id)
            if latest_session:
                session_id = latest_session.get('session_id')
                logger.info(f"Found latest session: {session_id}")
                history = await session_manager.get_session_history(session_id, limit)
                logger.info(f"Retrieved history for session {session_id}: {len(history)} entries")
            else:
                logger.info("No sessions found for user and agent")
                history = []
        
        logger.info(f"Returning {len(history)} history entries")
        return history
        
    except AgentNotFoundException:
        logger.error(f"Agent {agent_id} not found")
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting chat history: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return empty array on error to prevent 500 errors
        return []

# --- Scheduled Tasks Endpoints ---
@app.get("/agents/{agent_id}/scheduled-tasks")
async def get_agent_scheduled_tasks(agent_id: str, current_user: User = Depends(get_current_active_user)):
    """Get scheduled tasks for an agent"""
    try:
        # Verify agent ownership
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to view tasks for this agent.")
        
        from .scheduling_tool import scheduling_tool
        result = await scheduling_tool.list_scheduled_tasks(agent_id=agent_id, user_id=current_user.username)
        
        return result
        
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/agents/{agent_id}/scheduled-tasks")
async def create_scheduled_task(agent_id: str, task_data: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    """Create a new scheduled task for an agent"""
    try:
        # Verify agent ownership
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to create tasks for this agent.")
        
        from .scheduling_tool import scheduling_tool
        result = await scheduling_tool.create_scheduled_task(
            task_name=task_data.get("task_name"),
            task_type=task_data.get("task_type"),
            schedule_type=task_data.get("schedule_type"),
            schedule_params=task_data.get("schedule_params", {}),
            task_params=task_data.get("task_params", {}),
            agent_id=agent_id,
            user_id=current_user.username
        )
        
        return result
        
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Error creating scheduled task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/agents/{agent_id}/scheduled-tasks/{task_id}")
async def delete_scheduled_task(agent_id: str, task_id: str, current_user: User = Depends(get_current_active_user)):
    """Delete a scheduled task"""
    try:
        # Verify agent ownership
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to delete tasks for this agent.")
        
        from .scheduling_tool import scheduling_tool
        result = await scheduling_tool.delete_scheduled_task(task_id, current_user.username)
        
        return result
        
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Error deleting scheduled task: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/agents/{agent_id}/data")
async def get_agent_data(agent_id: str, current_user: User = Depends(get_current_active_user)):
    """Get stored data for an agent"""
    try:
        # Verify agent ownership
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to view data for this agent.")
        
        from .database_tool import database_tool
        
        # Get data from agent's collection if it has one
        data_collections = []
        if agent_config.dataSchema and agent_config.dataSchema.collectionName:
            collection_name = agent_config.dataSchema.collectionName
            result = await database_tool.find_documents(collection_name, {}, limit=50)
            if result.get("success"):
                data_collections.append({
                    "collection_name": collection_name,
                    "documents": result.get("documents", []),
                    "count": len(result.get("documents", []))
                })
        
        return {"success": True, "data_collections": data_collections}
        
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except Exception as e:
        logger.error(f"Error getting agent data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Tool Execution Endpoints ---
@app.post("/tools/{agent_id}/execute/{tool_id}")
async def execute_agent_tool(agent_id: str, tool_id: str, params: dict = Body(None), current_user: User = Depends(get_current_active_user)):
    try:
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to execute tools for this agent.")
        
        tool_to_execute = next((t for t in agent_config.tools if t.toolId == tool_id), None)
        
        if not tool_to_execute:
            raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found for agent {agent_id}")
            
        result = await execute_tool(tool_to_execute, params)
        return {"result": result}
        
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except ToolExecutionError as e:
        logger.error(f"Tool execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in tool execution: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Session Management Endpoints ---
@app.get("/sessions/")
async def list_sessions(current_user: User = Depends(get_current_active_user)):
    """List all sessions for the current user"""
    try:
        sessions = await session_manager.list_sessions(user_id=current_user.username)
        
        # Convert ObjectId to string for JSON serialization
        for session in sessions:
            if '_id' in session:
                session['_id'] = str(session['_id'])
                
        return sessions
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list sessions")

@app.get("/sessions/{session_id}")
async def get_session(session_id: str, current_user: User = Depends(get_current_active_user)):
    """Get details for a specific session"""
    try:
        session = await session_manager.get_session_by_id(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Ensure the session belongs to the current user
        if session.get('user_id') != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to access this session")
        
        # Convert ObjectId to string for JSON serialization
        if '_id' in session:
            session['_id'] = str(session['_id'])
            
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

# --- Settings Endpoints ---
@app.get("/settings/api-keys")
async def get_api_keys(current_user: User = Depends(get_current_active_user)):
    """Get API keys status (masked for security)"""
    try:
        import os
        
        def mask_api_key(key):
            """Mask API key for security"""
            if not key:
                return ""
            if len(key) <= 8:
                return "*" * len(key)
            return key[:4] + "*" * (len(key) - 8) + key[-4:]
        
        # Only return masked versions of the keys for security
        keys = {
            "OPENAI_API_KEY": mask_api_key(os.getenv("OPENAI_API_KEY", "")),
            "GEMINI_API_KEY": mask_api_key(os.getenv("GEMINI_API_KEY", "")),
            "DEEPSEEK_API_KEY": mask_api_key(os.getenv("DEEPSEEK_API_KEY", ""))
        }
        
        # Also indicate if the key is set (not empty)
        keys_status = {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "GEMINI_API_KEY": bool(os.getenv("GEMINI_API_KEY")),
            "DEEPSEEK_API_KEY": bool(os.getenv("DEEPSEEK_API_KEY"))
        }
        
        return {"keys": keys, "status": keys_status}
    except Exception as e:
        logger.error(f"Error getting API keys: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get API keys")

# --- Master Agent Endpoints ---
@app.post("/master-agent/conversation")
async def master_agent_conversation(message: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    """Handle conversation with the Smart Master Agent to create a new agent using DeepSeek"""
    try:
        user_message = message.get("message", "")
        conversation_id = message.get("conversation_id", "")
        
        # Process the conversation using the Smart Master Agent
        state = await process_smart_conversation(conversation_id, user_message)
        
        # If the agent creation is completed, create the actual agent
        if state.completed:
            try:
                agent_model = create_agent_from_smart_conversation(state, current_user.username)
                
                # Save the agent to file system
                if file_agent_manager.save_agent(agent_model):
                    schedule_workflow_for_agent(agent_model)
                    logger.info(f"Agent {agent_model.agentId} created successfully by {current_user.username}")
                    
                    # Add success message to conversation
                    state.messages.append({
                        "role": "assistant", 
                        "content": f"Harika! '{agent_model.agentName}' adlı agent başarıyla oluşturuldu ve dosya sistemine kaydedildi. Artık bu agent ile sohbet edebilir ve özelleştirebilirsiniz."
                    })
                else:
                    raise Exception("Agent dosya sistemine kaydedilemedi")
                    
            except Exception as e:
                logger.error(f"Error creating agent from smart conversation: {str(e)}")
                state.messages.append({
                    "role": "assistant", 
                    "content": f"Üzgünüm, agent oluşturulurken bir hata oluştu: {str(e)}"
                })
        
        return {
            "conversation_id": state.conversation_id,
            "messages": state.messages,
            "current_step": state.current_phase,
            "completed": state.completed
        }
    except Exception as e:
        logger.error(f"Error in smart master agent conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process conversation")

@app.post("/master-agent/stream")
async def master_agent_stream(message: dict = Body(...), current_user: User = Depends(get_current_active_user)):
    """Stream conversation with the Smart Master Agent using Server-Sent Events"""
    
    async def generate_stream():
        try:
            user_message = message.get("message", "")
            conversation_id = message.get("conversation_id", "")
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Master Agent düşünüyor...', 'status': 'thinking'})}\n\n"
            
            # Process the conversation using the Smart Master Agent
            state = await process_smart_conversation(conversation_id, user_message)
            
            # Send the conversation state
            yield f"data: {json.dumps({'type': 'conversation', 'data': {'conversation_id': state.conversation_id, 'messages': state.messages, 'current_step': state.current_phase, 'completed': state.completed}})}\n\n"
            
            # If the agent creation is completed, create the actual agent
            if state.completed:
                yield f"data: {json.dumps({'type': 'status', 'message': 'Agent oluşturuluyor...', 'status': 'creating'})}\n\n"
                
                try:
                    agent_model = create_agent_from_smart_conversation(state, current_user.username)
                    
                    # Save the agent to file system
                    if file_agent_manager.save_agent(agent_model):
                        schedule_workflow_for_agent(agent_model)
                        logger.info(f"Agent {agent_model.agentId} created successfully by {current_user.username}")
                        
                        # Send success message
                        yield f"data: {json.dumps({'type': 'success', 'message': f'Harika! {agent_model.agentName} adlı agent başarıyla oluşturuldu ve dosya sistemine kaydedildi.', 'agent_id': agent_model.agentId})}\n\n"
                    else:
                        raise Exception("Agent dosya sistemine kaydedilemedi")
                        
                except Exception as e:
                    logger.error(f"Error creating agent from smart conversation: {str(e)}")
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Üzgünüm, agent oluşturulurken bir hata oluştu: {str(e)}'})}\n\n"
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming master agent conversation: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': f'Bir hata oluştu: {str(e)}'})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        }
    )

# --- Workflow Execution Endpoints ---
@app.post("/workflows/{agent_id}/execute/{workflow_id}")
async def execute_agent_workflow(agent_id: str, workflow_id: str, initial_context: dict = Body(None), current_user: User = Depends(get_current_active_user)):
    try:
        agent_config = await load_agent_config(agent_id)
        if agent_config.owner != current_user.username:
            raise HTTPException(status_code=403, detail="You do not have permission to execute workflows for this agent.")
        
        executor = WorkflowExecutor(agent_config)
        final_context = await executor.run(workflow_id, initial_context)
        
        return {
            "status": "Workflow completed", 
            "final_context": final_context,
            "execution_summary": executor.get_execution_summary()
        }
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except WorkflowExecutionError as e:
        logger.error(f"Workflow execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in workflow execution: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Telegram Integration Endpoints ---
@app.post("/telegram/auth/request")
async def request_telegram_auth(current_user: User = Depends(get_current_active_user)):
    """Request Telegram authentication code for current user"""
    try:
        auth_code = await telegram_auth_manager.create_auth_request(current_user.username)
        
        # Create Telegram bot link with deep linking
        bot_username = "Dytaibot"  # Your actual bot username
        telegram_link = f"https://t.me/{bot_username}?start={auth_code}"
        
        return {
            "auth_code": auth_code,
            "telegram_link": telegram_link,
            "instructions": {
                "tr": [
                    f"1. Bu linke tıklayın: {telegram_link}",
                    f"2. Veya bot'a (@{bot_username}) gidin ve şu kodu gönderin: {auth_code}",
                    "3. Kod 10 dakika geçerlidir"
                ],
                "en": [
                    f"1. Click this link: {telegram_link}",
                    f"2. Or go to the bot (@{bot_username}) and send this code: {auth_code}",
                    "3. Code is valid for 10 minutes"
                ]
            },
            "expires_in_minutes": 10
        }
    except Exception as e:
        logger.error(f"Error creating Telegram auth request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create auth request")

@app.get("/telegram/auth/status")
async def get_telegram_auth_status(current_user: User = Depends(get_current_active_user)):
    """Get Telegram authentication status for current user"""
    try:
        chat_id = await telegram_auth_manager.get_chat_id_for_user(current_user.username)
        
        return {
            "is_connected": chat_id is not None,
            "chat_id": chat_id if chat_id else None,
            "user_id": current_user.username
        }
    except Exception as e:
        logger.error(f"Error getting Telegram auth status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get auth status")

@app.delete("/telegram/auth/revoke")
async def revoke_telegram_auth(current_user: User = Depends(get_current_active_user)):
    """Revoke Telegram authentication for current user"""
    try:
        success = await telegram_auth_manager.revoke_telegram_auth(current_user.username)
        
        if success:
            return {"message": "Telegram authentication revoked successfully"}
        else:
            return {"message": "No Telegram authentication found to revoke"}
    except Exception as e:
        logger.error(f"Error revoking Telegram auth: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to revoke auth")

@app.post("/telegram/webhook")
async def telegram_webhook(update: dict = Body(...)):
    """Handle incoming Telegram webhook updates"""
    try:
        logger.info(f"Received Telegram webhook update: {update}")
        
        # Process the update
        response = await telegram_webhook_handler.process_update(update)
        logger.info(f"Webhook handler response: {response}")
        
        if response:
            # Send response back to Telegram
            import httpx
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if bot_token and response.get('method') == 'sendMessage':
                telegram_payload = {
                    "chat_id": response["chat_id"],
                    "text": response["text"],
                    "parse_mode": response.get("parse_mode", "Markdown")
                }
                logger.info(f"Sending message to Telegram: {telegram_payload}")
                
                async with httpx.AsyncClient() as client:
                    telegram_response = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json=telegram_payload
                    )
                    logger.info(f"Telegram API response: {telegram_response.status_code} - {telegram_response.text}")
            else:
                logger.warning(f"Bot token missing or invalid response method: {response.get('method')}")
        else:
            logger.info("No response generated from webhook handler")
        
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {str(e)}", exc_info=True)
        return {"ok": False, "error": str(e)}
