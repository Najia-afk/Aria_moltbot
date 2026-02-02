# aria_skills/hourly_goals.py
"""
Hourly goals and micro-task management skill.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.hourly_goals")


@SkillRegistry.register
class HourlyGoalsSkill(BaseSkill):
    """
    Skill for managing hourly goals and micro-tasks.
    """
    
    name = "hourly_goals"
    description = "Manage Aria's hourly goals for short-term focus"
    
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
            logger.error(f"Hourly goals API health check failed: {e}")
            return SkillStatus.UNHEALTHY
    
    async def create(
        self,
        title: str,
        description: Optional[str] = None,
        target_hour: Optional[str] = None,
        priority: str = "medium",
        parent_goal_id: Optional[int] = None
    ) -> SkillResult:
        """
        Create an hourly goal.
        
        Args:
            title: Goal title
            description: Detailed description
            target_hour: Target hour (ISO timestamp)
            priority: Priority level (low, medium, high, critical)
            parent_goal_id: Link to parent main goal
        """
        try:
            payload = {
                "title": title,
                "priority": priority,
            }
            if description:
                payload["description"] = description
            if target_hour:
                payload["target_hour"] = target_hour
            if parent_goal_id:
                payload["parent_goal_id"] = parent_goal_id
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/hourly-goals",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to create hourly goal: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def list(
        self,
        status: Optional[str] = None,
        date: Optional[str] = None
    ) -> SkillResult:
        """
        List hourly goals.
        
        Args:
            status: Filter by status (pending, in_progress, completed, failed)
            date: Filter by date (YYYY-MM-DD)
        """
        try:
            params = {}
            if status:
                params["status"] = status
            if date:
                params["date"] = date
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/hourly-goals",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to list hourly goals: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def update(
        self,
        goal_id: int,
        status: Optional[str] = None,
        notes: Optional[str] = None
    ) -> SkillResult:
        """
        Update an hourly goal's status.
        
        Args:
            goal_id: Goal ID to update
            status: New status
            notes: Progress notes
        """
        try:
            payload = {}
            if status:
                payload["status"] = status
            if notes:
                payload["notes"] = notes
            
            async with httpx.AsyncClient() as client:
                response = await client.patch(
                    f"{self.api_base}/hourly-goals/{goal_id}",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to update hourly goal: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def stats(self, days: int = 7) -> SkillResult:
        """
        Get hourly goal completion statistics.
        
        Args:
            days: Days to analyze
        """
        result = await self.list()
        if not result.success:
            return result
        
        goals = result.data or []
        completed = sum(1 for g in goals if g.get("status") == "completed")
        total = len(goals)
        
        return SkillResult(success=True, data={
            "total": total,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "days_analyzed": days
        })
