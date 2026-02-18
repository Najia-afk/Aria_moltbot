# aria_skills/hourly_goals.py
"""
Hourly micro-goal skill.

Manages small, time-boxed goals for Aria's hourly cycles.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class HourlyGoalsSkill(BaseSkill):
    """
    Hourly micro-goal management.
    
    Creates and tracks small goals for each hour slot.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._hourly_goals: dict[int, list[Dict]] = {}  # fallback cache
        self._api = None
    
    @property
    def name(self) -> str:
        return "hourly_goals"
    
    async def initialize(self) -> bool:
        """Initialize hourly goals."""
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Hourly goals initialized (API-backed)")
        return True
    
    async def close(self):
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
    
    async def health_check(self) -> SkillStatus:
        """Check availability."""
        return self._status
    
    async def set_goal(
        self,
        hour: int,
        goal: str,
        priority: str = "normal",
    ) -> SkillResult:
        """
        Set a goal for a specific hour.
        
        Args:
            hour: Hour slot (0-23)
            goal: Goal description
            priority: low, normal, high
            
        Returns:
            SkillResult with goal data
        """
        if hour < 0 or hour > 23:
            return SkillResult.fail("Hour must be 0-23")
        
        goal_data = {
            "hour": hour,
            "goal": goal,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            resp = await self._api._client.post("/hourly-goals", json=goal_data)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else goal_data)
        except Exception as e:
            self.logger.warning(f"API set_goal failed, using fallback: {e}")
            if hour not in self._hourly_goals:
                self._hourly_goals[hour] = []
            goal_data["id"] = f"hg_{hour}_{len(self._hourly_goals[hour])}"
            self._hourly_goals[hour].append(goal_data)
            return SkillResult.ok(goal_data)
    
    async def get_current_goals(self) -> SkillResult:
        """Get goals for the current hour."""
        current_hour = datetime.now(timezone.utc).hour
        try:
            resp = await self._api._client.get("/hourly-goals", params={"hour": current_hour})
            resp.raise_for_status()
            api_data = resp.json()
            goals = api_data if isinstance(api_data, list) else api_data.get("goals", [])
            return SkillResult.ok({
                "hour": current_hour,
                "goals": goals,
                "pending": sum(1 for g in goals if g.get("status") == "pending"),
                "completed": sum(1 for g in goals if g.get("status") == "completed"),
            })
        except Exception as e:
            self.logger.warning(f"API get_current_goals failed, using fallback: {e}")
            goals = self._hourly_goals.get(current_hour, [])
            return SkillResult.ok({
                "hour": current_hour,
                "goals": goals,
                "pending": sum(1 for g in goals if g["status"] == "pending"),
                "completed": sum(1 for g in goals if g["status"] == "completed"),
            })
    
    async def complete_goal(self, goal_id: str) -> SkillResult:
        """Mark an hourly goal as complete."""
        update_data = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = await self._api._client.patch(f"/hourly-goals/{goal_id}", json=update_data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API complete_goal failed, using fallback: {e}")
            for hour, goals in self._hourly_goals.items():
                for goal in goals:
                    if goal["id"] == goal_id:
                        goal["status"] = "completed"
                        goal["completed_at"] = update_data["completed_at"]
                        return SkillResult.ok(goal)
            return SkillResult.fail(f"Goal not found: {goal_id}")
    
    async def get_day_summary(self) -> SkillResult:
        """Get summary of all hourly goals for today."""
        try:
            resp = await self._api._client.get("/hourly-goals")
            resp.raise_for_status()
            api_data = resp.json()
            goals_list = api_data if isinstance(api_data, list) else api_data.get("goals", [])
            total = len(goals_list)
            completed = sum(1 for g in goals_list if g.get("status") == "completed")
            return SkillResult.ok({
                "total_goals": total,
                "completed": completed,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            })
        except Exception as e:
            self.logger.warning(f"API get_day_summary failed, using fallback: {e}")
            total = sum(len(goals) for goals in self._hourly_goals.values())
            completed = sum(
                sum(1 for g in goals if g["status"] == "completed")
                for goals in self._hourly_goals.values()
            )
            return SkillResult.ok({
                "total_goals": total,
                "completed": completed,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
                "by_hour": {
                    hour: {
                        "total": len(goals),
                        "completed": sum(1 for g in goals if g["status"] == "completed"),
                    }
                    for hour, goals in self._hourly_goals.items()
                },
            })
    
    async def clear_past_goals(self) -> SkillResult:
        """Clear goals from past hours."""
        current_hour = datetime.now(timezone.utc).hour
        cleared = 0
        
        for hour in list(self._hourly_goals.keys()):
            if hour < current_hour:
                cleared += len(self._hourly_goals[hour])
                del self._hourly_goals[hour]
        
        return SkillResult.ok({
            "cleared": cleared,
            "remaining_hours": list(self._hourly_goals.keys()),
        })
