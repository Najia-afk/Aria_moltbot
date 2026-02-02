# aria_skills/schedule.py
"""
Schedule and task management skill.
"""
import logging
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.schedule")


@SkillRegistry.register
class ScheduleSkill(BaseSkill):
    """
    Skill for managing scheduled jobs and pending tasks.
    """
    
    name = "schedule"
    description = "Manage Aria's scheduled jobs, tasks, and background operations"
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self.api_base = config.settings.get("api_url", "http://aria-api:8000")
    
    async def _check_health(self) -> SkillStatus:
        """Check if the API is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/health", timeout=5.0)
                if response.status_code == 200:
                    return SkillStatus.HEALTHY
                return SkillStatus.DEGRADED
        except Exception as e:
            logger.error(f"Schedule API health check failed: {e}")
            return SkillStatus.UNHEALTHY
    
    async def list_jobs(
        self,
        status: Optional[str] = None
    ) -> SkillResult:
        """
        List all scheduled jobs.
        
        Args:
            status: Filter by job status (active, paused)
        """
        try:
            params = {}
            if status:
                params["status"] = status
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/schedule/jobs",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def tick(self) -> SkillResult:
        """
        Get current schedule tick status.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/schedule/tick",
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to get tick status: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def trigger(self, force: bool = False) -> SkillResult:
        """
        Manually trigger a schedule tick.
        
        Args:
            force: Force execution even if not due
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/schedule/tick",
                    json={"force": force},
                    timeout=30.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to trigger tick: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def sync(self) -> SkillResult:
        """
        Sync jobs from OpenClaw configuration.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/schedule/sync",
                    timeout=30.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to sync jobs: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def create_task(
        self,
        task_type: str,
        prompt: str,
        priority: str = "medium",
        context: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Create a pending complex task.
        
        Args:
            task_type: Task type (research, code, analysis)
            prompt: Task description/prompt
            priority: Task priority (low, medium, high, critical)
            context: Additional context
        """
        try:
            payload = {
                "type": task_type,
                "prompt": prompt,
                "priority": priority,
            }
            if context:
                payload["context"] = context
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/tasks",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def list_tasks(
        self,
        status: Optional[str] = None
    ) -> SkillResult:
        """
        List pending tasks.
        
        Args:
            status: Filter by status
        """
        try:
            params = {}
            if status:
                params["status"] = status
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/tasks",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def update_task(
        self,
        task_id: int,
        status: Optional[str] = None,
        result: Optional[str] = None
    ) -> SkillResult:
        """
        Update a pending task.
        
        Args:
            task_id: Task ID
            status: New status
            result: Task result/output
        """
        try:
            payload = {}
            if status:
                payload["status"] = status
            if result:
                payload["result"] = result
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.api_base}/tasks/{task_id}",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to update task: {e}")
            return SkillResult(success=False, error=str(e))
