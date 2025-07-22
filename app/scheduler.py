import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .agent_loader import load_agent_config, AgentNotFoundException
from .workflow_engine import WorkflowExecutor, WorkflowExecutionError
from .session_manager import session_manager
from .agent_loader import load_agent_config, AgentNotFoundException
from .telegram_scheduler_helper import telegram_scheduler_helper
from .models import AgentModel, Schedule
from .db import agent_collection

logger = logging.getLogger(__name__)

# Create a global scheduler
scheduler = AsyncIOScheduler()

async def run_scheduled_workflow(agent_id: str, workflow_id: str, schedule_id: str):
    """
    Loads an agent and executes a specific workflow for it based on a schedule.
    
    Args:
        agent_id: The ID of the agent
        workflow_id: The ID of the workflow to execute
        schedule_id: The ID of the schedule that triggered this execution
    """
    logger.info(f"Executing scheduled workflow '{workflow_id}' for agent '{agent_id}' (schedule: {schedule_id})")
    try:
        # Load agent with full initialization
        agent_config = await load_agent_config(agent_id, initialize=True)
        
        if not agent_config:
            raise AgentNotFoundException(f"Agent {agent_id} not found")
        
        # Create a unique session for this scheduled run
        system_user_id = f"system_scheduler_{schedule_id}"
        session = await session_manager.get_or_create_session(system_user_id, agent_id)
        session_id = session.get("session_id") if session else None
        
        if not session_id:
            raise Exception("Failed to create session for scheduled workflow")
        
        # Set up initial context with schedule information
        initial_context = {
            "scheduled_execution": True,
            "schedule_id": schedule_id,
            "execution_time": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "agent_id": agent_id,
            "workflow_id": workflow_id
        }
        
        # Execute the workflow
        executor = WorkflowExecutor(agent_config)
        final_context = await executor.run(workflow_id, initial_context)
        
        # Update session with results
        if final_context:
            await session_manager.update_session_context(session_id, final_context)
        
        # Log completion
        logger.info(f"Successfully executed scheduled workflow '{workflow_id}' for agent '{agent_id}'.")
        
        # Send Telegram notification if enabled and user has Telegram connected
        try:
            if final_context and telegram_scheduler_helper.enabled:
                # Extract user from agent owner or session
                agent_owner = agent_config.get('owner')
                if agent_owner:
                    # Generate notification based on workflow results
                    notification_data = {
                        'agent_name': agent_config.get('agentName', agent_id),
                        'workflow_id': workflow_id,
                        'execution_time': datetime.utcnow().strftime('%H:%M'),
                        'results': final_context.get('output', 'Workflow başarıyla tamamlandı!')
                    }
                    
                    # Send notification
                    await telegram_scheduler_helper.send_agent_notification(
                        user_id=agent_owner,
                        agent_id=agent_id,
                        notification_type='daily_report',
                        data=notification_data
                    )
                    logger.info(f"Telegram notification sent for agent {agent_id} to user {agent_owner}")
        except Exception as telegram_error:
            logger.warning(f"Failed to send Telegram notification: {str(telegram_error)}")
        
        # Store this execution in the agent's schedule history
        await record_schedule_execution(agent_id, schedule_id, workflow_id, True, None)
        
    except AgentNotFoundException as e:
        error_msg = f"Agent {agent_id} not found for scheduled workflow '{workflow_id}': {str(e)}"
        logger.error(error_msg)
        await record_schedule_execution(agent_id, schedule_id, workflow_id, False, error_msg)
        
    except WorkflowExecutionError as e:
        error_msg = f"Error executing workflow '{workflow_id}': {str(e)}"
        logger.error(f"Error for agent '{agent_id}': {error_msg}")
        await record_schedule_execution(agent_id, schedule_id, workflow_id, False, error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Agent {agent_id}, workflow {workflow_id}: {error_msg}")
        await record_schedule_execution(agent_id, schedule_id, workflow_id, False, error_msg)

async def record_schedule_execution(agent_id: str, schedule_id: str, workflow_id: str, 
                                    success: bool, error_message: Optional[str] = None) -> None:
    """
    Records the execution of a scheduled workflow in the database.
    
    Args:
        agent_id: The ID of the agent
        schedule_id: The ID of the schedule
        workflow_id: The ID of the workflow
        success: Whether the execution was successful
        error_message: Optional error message if the execution failed
    """
    history_entry = {
        "agent_id": agent_id,
        "schedule_id": schedule_id,
        "workflow_id": workflow_id,
        "timestamp": datetime.utcnow(),
        "success": success
    }
    
    if error_message:
        history_entry["error_message"] = error_message
    
    # Store in a dedicated collection for schedule execution history
    db = agent_collection.database
    await db.schedule_executions.insert_one(history_entry)

def schedule_workflow_for_agent(agent: AgentModel) -> List[Dict[str, Any]]:
    """
    Schedules all workflows for a given agent based on their schedules defined in the agent config.
    
    Args:
        agent: The agent model containing schedules and workflows
        
    Returns:
        List of scheduled job details
    """
    scheduled_jobs = []
    
    # Check if the agent has schedules defined
    if not agent.schedules:
        logger.info(f"Agent {agent.agentId} has no schedules defined")
        return scheduled_jobs
    
    for schedule in agent.schedules:
        # Find the workflow referenced by this schedule
        workflow_id = schedule.workflowId
        
        # Check if the referenced workflow exists
        workflow_exists = any(w.workflowId == workflow_id for w in agent.workflows)
        if not workflow_exists:
            logger.warning(f"Schedule {schedule.scheduleId} references non-existent workflow {workflow_id}")
            continue
        
        try:
            # Create a unique job ID
            job_id = f"agent_{agent.agentId}_schedule_{schedule.scheduleId}"
            
            # Parse the cron expression
            cron_parts = schedule.cron.split()
            
            # Create the job with APScheduler
            scheduler.add_job(
                run_scheduled_workflow,
                CronTrigger.from_crontab(schedule.cron),
                id=job_id,
                args=[agent.agentId, workflow_id, schedule.scheduleId],
                replace_existing=True,
                name=f"{schedule.description if schedule.description else 'Scheduled workflow'}"
            )
            
            scheduled_jobs.append({
                "job_id": job_id,
                "agent_id": agent.agentId,
                "schedule_id": schedule.scheduleId,
                "workflow_id": workflow_id,
                "cron": schedule.cron,
                "description": schedule.description
            })
            
            logger.info(f"Scheduled job '{job_id}' with cron '{schedule.cron}' for agent {agent.agentId}")
            
        except Exception as e:
            logger.error(f"Failed to schedule workflow {workflow_id} for agent {agent.agentId}: {e}")
    
    return scheduled_jobs

async def load_all_agent_schedules() -> Dict[str, List[Dict[str, Any]]]:
    """
    Loads all agents from the database and schedules their workflows.
    
    Returns:
        Dictionary mapping agent IDs to their scheduled jobs
    """
    all_scheduled_jobs = {}
    
    # Get all agents
    cursor = agent_collection.find({})
    
    async for agent_doc in cursor:
        try:
            agent = AgentModel(**agent_doc)
            scheduled_jobs = schedule_workflow_for_agent(agent)
            all_scheduled_jobs[agent.agentId] = scheduled_jobs
            logger.info(f"Scheduled {len(scheduled_jobs)} jobs for agent {agent.agentId}")
        except Exception as e:
            logger.error(f"Error scheduling jobs for agent {agent_doc.get('agentId', 'unknown')}: {e}")
    
    return all_scheduled_jobs

async def refresh_agent_schedules(agent_id: str) -> List[Dict[str, Any]]:
    """
    Refreshes schedules for a specific agent, typically after the agent has been updated.
    
    Args:
        agent_id: The ID of the agent whose schedules should be refreshed
        
    Returns:
        List of scheduled jobs for the agent
    """
    # Remove any existing jobs for this agent
    for job in scheduler.get_jobs():
        if job.id.startswith(f"agent_{agent_id}_schedule_"):
            scheduler.remove_job(job.id)
            logger.info(f"Removed existing schedule job {job.id}")
    
    # Load agent and schedule new jobs
    try:
        agent_config = await load_agent_config(agent_id)
        scheduled_jobs = schedule_workflow_for_agent(agent_config)
        logger.info(f"Refreshed {len(scheduled_jobs)} schedules for agent {agent_id}")
        return scheduled_jobs
    except AgentNotFoundException:
        logger.warning(f"Cannot refresh schedules for non-existent agent {agent_id}")
        return []
    except Exception as e:
        logger.error(f"Error refreshing schedules for agent {agent_id}: {e}")
        return []
