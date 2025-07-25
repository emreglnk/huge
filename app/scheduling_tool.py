import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import json
import asyncio

from .db import db
from .models import Tool

logger = logging.getLogger(__name__)

class SchedulingTool:
    """Scheduling tool for AI agents to create and manage scheduled tasks"""
    
    def __init__(self):
        self.db = db
        self.scheduler = None
        self.collection_name = "scheduled_tasks"
    
    def get_scheduler(self):
        """Get or create scheduler instance"""
        if self.scheduler is None:
            self.scheduler = AsyncIOScheduler()
            if not self.scheduler.running:
                self.scheduler.start()
        return self.scheduler
    
    async def create_scheduled_task(self, 
                                  task_name: str,
                                  task_type: str,
                                  schedule_type: str,
                                  schedule_params: Dict[str, Any],
                                  task_params: Dict[str, Any],
                                  agent_id: str,
                                  user_id: str) -> Dict[str, Any]:
        """Create a new scheduled task"""
        try:
            scheduler = self.get_scheduler()
            
            # Create task document
            task_doc = {
                "task_name": task_name,
                "task_type": task_type,  # 'telegram_message', 'email', 'workflow', etc.
                "schedule_type": schedule_type,  # 'once', 'interval', 'cron'
                "schedule_params": schedule_params,
                "task_params": task_params,
                "agent_id": agent_id,
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "status": "active",
                "last_run": None,
                "next_run": None,
                "run_count": 0
            }
            
            # Create appropriate trigger based on schedule type
            trigger = None
            if schedule_type == "once":
                # Run once at specified datetime
                run_date = datetime.fromisoformat(schedule_params["run_date"])
                trigger = DateTrigger(run_date=run_date)
                task_doc["next_run"] = run_date
                
            elif schedule_type == "interval":
                # Run at regular intervals
                interval_params = {}
                if "seconds" in schedule_params:
                    interval_params["seconds"] = schedule_params["seconds"]
                if "minutes" in schedule_params:
                    interval_params["minutes"] = schedule_params["minutes"]
                if "hours" in schedule_params:
                    interval_params["hours"] = schedule_params["hours"]
                if "days" in schedule_params:
                    interval_params["days"] = schedule_params["days"]
                
                trigger = IntervalTrigger(**interval_params)
                next_run = datetime.utcnow() + timedelta(**interval_params)
                task_doc["next_run"] = next_run
                
            elif schedule_type == "cron":
                # Run based on cron expression
                cron_params = {}
                for key in ["second", "minute", "hour", "day", "month", "day_of_week", "year"]:
                    if key in schedule_params:
                        cron_params[key] = schedule_params[key]
                
                trigger = CronTrigger(**cron_params)
                task_doc["next_run"] = trigger.get_next_fire_time(None, datetime.utcnow())
            
            if not trigger:
                return {"success": False, "error": "Invalid schedule type or parameters"}
            
            # Save task to database
            collection = self.db[self.collection_name]
            result = await collection.insert_one(task_doc)
            task_id = str(result.inserted_id)
            
            # Add job to scheduler
            job = scheduler.add_job(
                func=self._execute_scheduled_task,
                trigger=trigger,
                args=[task_id],
                id=task_id,
                name=task_name,
                replace_existing=True
            )
            
            logger.info(f"Created scheduled task: {task_name} with ID: {task_id}")
            return {
                "success": True,
                "task_id": task_id,
                "message": f"Scheduled task '{task_name}' created successfully",
                "next_run": task_doc["next_run"].isoformat() if task_doc["next_run"] else None
            }
            
        except Exception as e:
            logger.error(f"Error creating scheduled task: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _execute_scheduled_task(self, task_id: str):
        """Execute a scheduled task"""
        try:
            collection = self.db[self.collection_name]
            task = await collection.find_one({"_id": task_id})
            
            if not task:
                logger.error(f"Scheduled task {task_id} not found")
                return
            
            logger.info(f"Executing scheduled task: {task['task_name']}")
            
            # Update task execution info
            await collection.update_one(
                {"_id": task_id},
                {
                    "$set": {"last_run": datetime.utcnow()},
                    "$inc": {"run_count": 1}
                }
            )
            
            # Execute task based on type
            if task["task_type"] == "telegram_message":
                await self._execute_telegram_task(task)
            elif task["task_type"] == "email":
                await self._execute_email_task(task)
            elif task["task_type"] == "workflow":
                await self._execute_workflow_task(task)
            else:
                logger.warning(f"Unknown task type: {task['task_type']}")
            
        except Exception as e:
            logger.error(f"Error executing scheduled task {task_id}: {str(e)}")
    
    async def _execute_telegram_task(self, task: Dict[str, Any]):
        """Execute a Telegram message task"""
        try:
            from .tool_executor import execute_telegram_tool
            from .models import Tool
            
            # Create a temporary Telegram tool
            telegram_tool = Tool(
                toolId="scheduled_telegram",
                name="Scheduled Telegram Message",
                type="TELEGRAM",
                description="Scheduled Telegram message",
                config={"bot_token": task["task_params"].get("bot_token", "")}
            )
            
            # Execute the Telegram tool
            params = {
                "message": task["task_params"]["message"],
                "chat_id": task["task_params"].get("chat_id"),
                "username": task["task_params"].get("username")
            }
            
            result = await execute_telegram_tool(telegram_tool, params)
            logger.info(f"Scheduled Telegram message sent: {result}")
            
        except Exception as e:
            logger.error(f"Error executing Telegram task: {str(e)}")
    
    async def _execute_email_task(self, task: Dict[str, Any]):
        """Execute an email task"""
        try:
            from .email_tool import execute_email_tool
            from .models import Tool
            
            # Create a temporary email tool
            email_tool = Tool(
                toolId="scheduled_email",
                name="Scheduled Email",
                type="EMAIL",
                description="Scheduled email",
                config=task["task_params"].get("email_config", {})
            )
            
            # Execute the email tool
            params = {
                "to": task["task_params"]["to"],
                "subject": task["task_params"]["subject"],
                "body": task["task_params"]["body"]
            }
            
            result = await execute_email_tool(email_tool, params)
            logger.info(f"Scheduled email sent: {result}")
            
        except Exception as e:
            logger.error(f"Error executing email task: {str(e)}")
    
    async def _execute_workflow_task(self, task: Dict[str, Any]):
        """Execute a workflow task"""
        try:
            # Import workflow execution logic
            from .workflow_engine import WorkflowEngine
            
            workflow_engine = WorkflowEngine()
            result = await workflow_engine.execute_workflow(
                task["task_params"]["workflow_id"],
                task["task_params"].get("input_data", {})
            )
            
            logger.info(f"Scheduled workflow executed: {result}")
            
        except Exception as e:
            logger.error(f"Error executing workflow task: {str(e)}")
    
    async def list_scheduled_tasks(self, agent_id: str = None, user_id: str = None) -> Dict[str, Any]:
        """List scheduled tasks"""
        try:
            collection = self.db[self.collection_name]
            query = {}
            
            if agent_id:
                query["agent_id"] = agent_id
            if user_id:
                query["user_id"] = user_id
            
            cursor = collection.find(query).sort("created_at", -1)
            tasks = await cursor.to_list(length=100)
            
            # Convert ObjectId to string
            for task in tasks:
                task["_id"] = str(task["_id"])
                if task.get("created_at"):
                    task["created_at"] = task["created_at"].isoformat()
                if task.get("last_run"):
                    task["last_run"] = task["last_run"].isoformat()
                if task.get("next_run"):
                    task["next_run"] = task["next_run"].isoformat()
            
            return {"success": True, "tasks": tasks}
            
        except Exception as e:
            logger.error(f"Error listing scheduled tasks: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def delete_scheduled_task(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """Delete a scheduled task"""
        try:
            collection = self.db[self.collection_name]
            
            # Check if task exists and belongs to user
            task = await collection.find_one({"_id": task_id, "user_id": user_id})
            if not task:
                return {"success": False, "error": "Task not found or access denied"}
            
            # Remove from scheduler
            scheduler = self.get_scheduler()
            try:
                scheduler.remove_job(task_id)
            except Exception as e:
                logger.warning(f"Job {task_id} not found in scheduler: {str(e)}")
            
            # Delete from database
            await collection.delete_one({"_id": task_id})
            
            logger.info(f"Deleted scheduled task: {task_id}")
            return {"success": True, "message": "Task deleted successfully"}
            
        except Exception as e:
            logger.error(f"Error deleting scheduled task: {str(e)}")
            return {"success": False, "error": str(e)}

# Global scheduling tool instance
scheduling_tool = SchedulingTool()

# Tool execution functions for integration with tool_executor
async def execute_scheduling_operation(operation: str, **kwargs) -> Dict[str, Any]:
    """Execute scheduling operation"""
    try:
        if operation == "create_task":
            return await scheduling_tool.create_scheduled_task(
                kwargs.get("task_name"),
                kwargs.get("task_type"),
                kwargs.get("schedule_type"),
                kwargs.get("schedule_params", {}),
                kwargs.get("task_params", {}),
                kwargs.get("agent_id"),
                kwargs.get("user_id")
            )
        elif operation == "list_tasks":
            return await scheduling_tool.list_scheduled_tasks(
                kwargs.get("agent_id"),
                kwargs.get("user_id")
            )
        elif operation == "delete_task":
            return await scheduling_tool.delete_scheduled_task(
                kwargs.get("task_id"),
                kwargs.get("user_id")
            )
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
            
    except Exception as e:
        logger.error(f"Error executing scheduling operation {operation}: {str(e)}")
        return {"success": False, "error": str(e)}
