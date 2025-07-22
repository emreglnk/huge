import os
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from .models import AgentModel

logger = logging.getLogger(__name__)

class FileAgentManager:
    """File-based agent management system"""
    
    def __init__(self, agents_dir: str = "agents"):
        self.agents_dir = Path(agents_dir)
        self.agents_dir.mkdir(exist_ok=True)
        logger.info(f"FileAgentManager initialized with directory: {self.agents_dir}")
    
    def get_agent_file_path(self, agent_id: str) -> Path:
        """Get the file path for an agent"""
        return self.agents_dir / f"{agent_id}.json"
    
    def list_agents(self, owner: str = None) -> List[AgentModel]:
        """List all agents from JSON files"""
        agents = []
        
        try:
            for json_file in self.agents_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        agent_data = json.load(f)
                    
                    # Add owner if not present
                    if 'owner' not in agent_data:
                        agent_data['owner'] = owner or 'system'
                    
                    # Filter by owner if specified
                    if owner and agent_data.get('owner') != owner:
                        continue
                    
                    agent = AgentModel(**agent_data)
                    agents.append(agent)
                    
                except Exception as e:
                    logger.error(f"Error loading agent from {json_file}: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error listing agents: {str(e)}")
        
        logger.info(f"Found {len(agents)} agents")
        return agents
    
    def get_agent(self, agent_id: str, owner: str = None) -> Optional[AgentModel]:
        """Get a specific agent by ID"""
        file_path = self.get_agent_file_path(agent_id)
        
        if not file_path.exists():
            logger.warning(f"Agent file not found: {file_path}")
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                agent_data = json.load(f)
            
            # Add owner if not present
            if 'owner' not in agent_data:
                agent_data['owner'] = owner or 'system'
            
            # Check owner permission
            if owner and agent_data.get('owner') != owner:
                logger.warning(f"Access denied for agent {agent_id} by user {owner}")
                return None
            
            agent = AgentModel(**agent_data)
            logger.info(f"Loaded agent: {agent_id}")
            return agent
            
        except Exception as e:
            logger.error(f"Error loading agent {agent_id}: {str(e)}")
            return None
    
    def save_agent(self, agent: AgentModel) -> bool:
        """Save agent to JSON file"""
        file_path = self.get_agent_file_path(agent.agentId)
        
        try:
            # Convert to dict and ensure proper formatting
            agent_data = agent.model_dump(by_alias=True, exclude_none=True)
            
            # Write to file with proper formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(agent_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Agent saved to file: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving agent {agent.agentId}: {str(e)}")
            return False
    
    def delete_agent(self, agent_id: str, owner: str = None) -> bool:
        """Delete agent file"""
        try:
            # First verify ownership
            agent = self.get_agent(agent_id, owner)
            if not agent:
                logger.warning(f"Cannot delete agent {agent_id}: not found or access denied")
                return False
            
            file_path = self.get_agent_file_path(agent_id)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Agent file deleted: {file_path}")
                return True
            else:
                logger.warning(f"Agent file not found: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting agent {agent_id}: {str(e)}")
            return False
    

    
    def update_agent(self, agent_id: str, updates: Dict[str, Any], owner: str = None) -> Optional[AgentModel]:
        """Update agent file with new data"""
        agent = self.get_agent(agent_id, owner)
        if not agent:
            return None
        
        try:
            # Get current data
            agent_data = agent.model_dump(by_alias=True, exclude_none=True)
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(agent, key):
                    agent_data[key] = value
            
            # Create updated agent
            updated_agent = AgentModel(**agent_data)
            
            # Save to file
            if self.save_agent(updated_agent):
                logger.info(f"Agent updated: {agent_id}")
                return updated_agent
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error updating agent {agent_id}: {str(e)}")
            return None
    
    def agent_exists(self, agent_id: str) -> bool:
        """Check if agent file exists"""
        file_path = self.get_agent_file_path(agent_id)
        return file_path.exists()
    
    def get_agent_stats(self) -> Dict[str, Any]:
        """Get statistics about agents"""
        try:
            json_files = list(self.agents_dir.glob("*.json"))
            total_agents = len(json_files)
            
            owners = {}
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        agent_data = json.load(f)
                    
                    owner = agent_data.get('owner', 'system')
                    owners[owner] = owners.get(owner, 0) + 1
                    
                except Exception:
                    continue
            
            return {
                'total_agents': total_agents,
                'agents_by_owner': owners,
                'agents_directory': str(self.agents_dir)
            }
            
        except Exception as e:
            logger.error(f"Error getting agent stats: {str(e)}")
            return {'total_agents': 0, 'agents_by_owner': {}, 'agents_directory': str(self.agents_dir)}
    
    def import_from_json(self, json_data: Dict[str, Any], owner: str = None) -> Optional[AgentModel]:
        """Import agent from JSON data"""
        try:
            # Add owner if not present
            if 'owner' not in json_data:
                json_data['owner'] = owner or 'system'
            
            agent = AgentModel(**json_data)
            
            if self.save_agent(agent):
                logger.info(f"Agent imported: {agent.agentId}")
                return agent
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error importing agent: {str(e)}")
            return None
    
    def export_agent(self, agent_id: str, owner: str = None) -> Optional[Dict[str, Any]]:
        """Export agent to JSON data"""
        agent = self.get_agent(agent_id, owner)
        if agent:
            return agent.model_dump(by_alias=True, exclude_none=True)
        return None
    
    def backup_agents(self, backup_dir: str = "backup") -> bool:
        """Backup all agent files"""
        try:
            backup_path = Path(backup_dir)
            backup_path.mkdir(exist_ok=True)
            
            import shutil
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = backup_path / f"agents_backup_{timestamp}"
            
            shutil.copytree(self.agents_dir, backup_subdir)
            
            logger.info(f"Agents backed up to: {backup_subdir}")
            return True
            
        except Exception as e:
            logger.error(f"Error backing up agents: {str(e)}")
            return False

# Global file agent manager instance
file_agent_manager = FileAgentManager() 