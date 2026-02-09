# aria_skills/performance.py
"""
Performance logging skill.

Tracks and logs Aria's performance metrics.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class PerformanceSkill(BaseSkill):
    """
    Performance logging and tracking.
    
    Records successes, failures, and improvement areas.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._logs: List[Dict] = []  # fallback cache
        self._api_url = os.environ.get('ARIA_API_URL', 'http://aria-api:8000/api')
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "performance"
    
    async def initialize(self) -> bool:
        """Initialize performance skill."""
        self._client = httpx.AsyncClient(base_url=self._api_url, timeout=30.0)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Performance skill initialized (API-backed)")
        return True
    
    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> SkillStatus:
        """Check availability."""
        return self._status
    
    async def log_review(
        self,
        period: str,
        successes: List[str],
        failures: List[str],
        improvements: List[str],
    ) -> SkillResult:
        """
        Log a performance review.
        
        Args:
            period: Review period (e.g., "2024-01-15")
            successes: Things that went well
            failures: Things that didn't work
            improvements: Areas to improve
            
        Returns:
            SkillResult with log ID
        """
        log = {
            "period": period,
            "successes": successes,
            "failures": failures,
            "improvements": improvements,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            resp = await self._client.post("/performance", json=log)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else log)
        except Exception as e:
            self.logger.warning(f"API log_review failed, using fallback: {e}")
            log["id"] = f"perf_{len(self._logs) + 1}"
            self._logs.append(log)
            return SkillResult.ok(log)
    
    async def get_reviews(self, limit: int = 10) -> SkillResult:
        """Get recent performance reviews."""
        try:
            resp = await self._client.get("/performance", params={"limit": limit})
            resp.raise_for_status()
            api_data = resp.json()
            if isinstance(api_data, list):
                return SkillResult.ok({"reviews": api_data[-limit:], "total": len(api_data)})
            return SkillResult.ok(api_data)
        except Exception as e:
            self.logger.warning(f"API get_reviews failed, using fallback: {e}")
            return SkillResult.ok({
                "reviews": self._logs[-limit:],
                "total": len(self._logs),
            })
    
    async def get_improvement_summary(self) -> SkillResult:
        """Summarize improvement areas across reviews."""
        try:
            resp = await self._client.get("/performance")
            resp.raise_for_status()
            api_data = resp.json()
            logs = api_data if isinstance(api_data, list) else api_data.get("reviews", [])
        except Exception as e:
            self.logger.warning(f"API get_improvement_summary failed, using fallback: {e}")
            logs = self._logs
        
        all_improvements = []
        for log in logs:
            all_improvements.extend(log.get("improvements", []))
        
        # Count frequency
        counts = {}
        for item in all_improvements:
            counts[item] = counts.get(item, 0) + 1
        
        sorted_improvements = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        
        return SkillResult.ok({
            "top_improvements": sorted_improvements[:10],
            "total_reviews": len(logs),
        })
