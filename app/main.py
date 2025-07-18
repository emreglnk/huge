from fastapi import FastAPI, Body, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import List, Optional
from datetime import timedelta
import logging
import os

from .db import agent_collection, close_db_client
from .models import AgentModel, UpdateAgentModel, User, Token
from .agent_loader import load_agent_config, AgentNotFoundException
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

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up AI Agent Platform...")
    await session_manager.initialize()
    try:
        agents_cursor = agent_collection.find()
        async for agent_data in agents_cursor:
            try:
                agent = AgentModel(**agent_data)
                schedule_workflow_for_agent(agent)
            except Exception as e:
                logger.error(f"Error loading agent {agent_data.get('agentId', 'unknown')}: {str(e)}")
        
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AI Agent Platform...")
    try:
        if scheduler.running:
            scheduler.shutdown()
        close_db_client()
        logger.info("Shutdown completed successfully")
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
        agent_data = agent.model_dump(by_alias=True)
        new_agent = await agent_collection.insert_one(agent_data)
        created_agent_doc = await agent_collection.find_one({"_id": new_agent.inserted_id})
        
        if created_agent_doc:
            created_agent_model = AgentModel(**created_agent_doc)
            schedule_workflow_for_agent(created_agent_model)
            logger.info(f"Agent {agent.agentId} created successfully by {current_user.username}")

        return JSONResponse(status_code=status.HTTP_201_CREATED, content=jsonable_encoder(created_agent_doc))
    except Exception as e:
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create agent")

@app.get("/agents/", response_description="List all agents for the current user", response_model=List[AgentModel])
async def list_agents(current_user: User = Depends(get_current_active_user)):
    try:
        agents = await agent_collection.find({"owner": current_user.username}).to_list(1000)
        return agents
    except Exception as e:
        logger.error(f"Error listing agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list agents")

@app.get("/agents/{id}", response_description="Get a single agent", response_model=AgentModel)
async def show_agent(id: str, current_user: User = Depends(get_current_active_user)):
    try:
        query = {"agentId": id, "owner": current_user.username}
        if (agent := await agent_collection.find_one(query)) is not None:
            return agent
        raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have permission to access it.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve agent")

@app.put("/agents/{id}", response_description="Update an agent", response_model=AgentModel)
async def update_agent(id: str, agent: UpdateAgentModel = Body(...), current_user: User = Depends(get_current_active_user)):
    try:
        agent_data = agent.model_dump(by_alias=True, exclude_unset=True)
        query = {"agentId": id, "owner": current_user.username}

        if len(agent_data) >= 1:
            update_result = await agent_collection.update_one(query, {"$set": agent_data})
            
            if update_result.matched_count == 1:
                if (updated_agent_doc := await agent_collection.find_one(query)) is not None:
                    updated_agent_model = AgentModel(**updated_agent_doc)
                    schedule_workflow_for_agent(updated_agent_model)
                    logger.info(f"Agent {id} updated successfully by {current_user.username}")
                    return updated_agent_doc

        raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have permission to update it.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update agent")

@app.delete("/agents/{id}", response_description="Delete an agent")
async def delete_agent(id: str, current_user: User = Depends(get_current_active_user)):
    try:
        query = {"agentId": id, "owner": current_user.username}
        agent_to_delete = await agent_collection.find_one(query)
        if not agent_to_delete:
            raise HTTPException(status_code=404, detail=f"Agent {id} not found or you don't have permission to delete it.")

        agent_model = AgentModel(**agent_to_delete)
        
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
        
        llm_response = await get_llm_response(
            llm_config=agent_config.llmConfig,
            system_prompt=enhanced_system_prompt,
            user_message=user_message
        )
        
        await session_manager.add_to_history(session_id, user_message, llm_response)
        await session_manager.update_session_context(session_id, {})
        
        return {
            "agent_system_prompt": agent_config.systemPrompt,
            "user_message": user_message,
            "response": llm_response,
            "session_id": session_id
        }
    except AgentNotFoundException:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# --- Chat History Endpoints ---
@app.get("/chat/history/{agent_id}")
async def get_chat_history(agent_id: str, session_id: Optional[str] = None, limit: int = 10, current_user: User = Depends(get_current_active_user)):
    """Get chat history for a specific session or agent"""
    try:
        # Verify agent exists and user has access
        agent = await agent_collection.find_one({"agentId": agent_id, "owner": current_user.username})
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found or you don't have access.")

        target_session_id = session_id
        
        if target_session_id:
            # Validate provided session_id
            session = await session_manager.get_session_by_id(target_session_id)
            if not session or session.get('user_id') != current_user.username:
                raise HTTPException(status_code=403, detail="You do not have permission to access this chat history.")
        else:
            # Find latest session for user and agent
            latest_session = await session_manager.find_latest_session(current_user.username, agent_id)
            if not latest_session:
                return []
            target_session_id = latest_session["session_id"]

        history = await session_manager.get_session_history(target_session_id, limit)
        return history
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving chat history for agent {agent_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")

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
                
                # Save the agent to the database
                agent_data = agent_model.model_dump(by_alias=True)
                new_agent = await agent_collection.insert_one(agent_data)
                created_agent_doc = await agent_collection.find_one({"_id": new_agent.inserted_id})
                
                if created_agent_doc:
                    created_agent_model = AgentModel(**created_agent_doc)
                    schedule_workflow_for_agent(created_agent_model)
                    logger.info(f"Agent {agent_model.agentId} created successfully by {current_user.username}")
                    
                    # Add success message to conversation
                    state.messages.append({
                        "role": "assistant", 
                        "content": f"Harika! '{agent_model.agentName}' adlı agent başarıyla oluşturuldu ve veritabanına kaydedildi. Artık bu agent ile sohbet edebilir ve özelleştirebilirsiniz."
                    })
                    
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
