# aria_skills/performance.py
"""
Performance logging and self-assessment skill.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.performance")


@SkillRegistry.register
class PerformanceSkill(BaseSkill):
    """
    Skill for logging and querying performance reviews.
    """
    
    name = "performance"
    description = "Log and query Aria's performance reviews and self-assessments"
    
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
            logger.error(f"Performance API health check failed: {e}")
            return SkillStatus.UNHEALTHY
    
    async def log(
        self,
        period: str,
        summary: str,
        score: Optional[float] = None,
        strengths: Optional[List[str]] = None,
        improvements: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SkillResult:
        """
        Log a performance review entry.
        
        Args:
            period: Review period (daily, weekly, monthly)
            summary: Summary of performance
            score: Performance score (0-100)
            strengths: List of strengths identified
            improvements: Areas for improvement
            metadata: Additional metadata
        """
        try:
            payload = {
                "period": period,
                "summary": summary,
            }
            if score is not None:
                payload["score"] = score
            if strengths:
                payload["strengths"] = strengths
            if improvements:
                payload["improvements"] = improvements
            if metadata:
                payload["metadata"] = metadata
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/performance",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to log performance: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def list(
        self,
        period: Optional[str] = None,
        limit: int = 20
    ) -> SkillResult:
        """
        Get performance review history.
        
        Args:
            period: Filter by period type
            limit: Maximum entries to return
        """
        try:
            params = {"limit": limit}
            if period:
                params["period"] = period
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/performance",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to list performance: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def stats(self, days: int = 30) -> SkillResult:
        """
        Get performance statistics.
        
        Args:
            days: Number of days to analyze
        """
        # For now, fetch recent entries and calculate stats
        result = await self.list(limit=days)
        if not result.success:
            return result
        
        entries = result.data or []
        if not entries:
            return SkillResult(success=True, data={"message": "No performance data"})
        
        scores = [e.get("score", 0) for e in entries if e.get("score")]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return SkillResult(success=True, data={
            "total_entries": len(entries),
            "average_score": round(avg_score, 2),
            "days_analyzed": days
        })
