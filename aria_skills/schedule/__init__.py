# aria_skills/schedule.py
"""
Job scheduling skill.

Manages scheduled jobs and recurring tasks.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class ScheduleSkill(BaseSkill):
    """
    Job scheduling and management.
    
    Handles scheduled tasks, recurring jobs, and time-based triggers.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._jobs: Dict[str, Dict] = {}  # fallback cache
        self._job_counter = 0
        self._api_url = os.environ.get('ARIA_API_URL', 'http://aria-api:8000/api')
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def name(self) -> str:
        return "schedule"
    
    async def initialize(self) -> bool:
        """Initialize scheduler."""
        self._client = httpx.AsyncClient(base_url=self._api_url, timeout=30.0)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Schedule skill initialized (API-backed)")
        return True
    
    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def health_check(self) -> SkillStatus:
        """Check scheduler availability."""
        return self._status
    
    @logged_method()
    async def create_job(
        self,
        name: str,
        schedule: str,  # cron-like or "every X minutes/hours"
        action: str,
        params: Optional[Dict] = None,
        enabled: bool = True,
    ) -> SkillResult:
        """
        Create a scheduled job.
        
        Args:
            name: Job name
            schedule: Schedule expression
            action: Action to perform
            params: Action parameters
            enabled: Whether job is active
            
        Returns:
            SkillResult with job details
        """
        self._job_counter += 1
        job_id = f"job_{self._job_counter}"
        
        job = {
            "id": job_id,
            "name": name,
            "schedule": schedule,
            "action": action,
            "params": params or {},
            "enabled": enabled,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_run": None,
            "next_run": self._calculate_next_run(schedule),
            "run_count": 0,
        }
        
        try:
            resp = await self._client.post("/schedule", json=job)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else job)
        except Exception as e:
            self.logger.warning(f"API create_job failed, using fallback: {e}")
            self._jobs[job_id] = job
            return SkillResult.ok(job)
    
    async def get_job(self, job_id: str) -> SkillResult:
        """Get a specific job."""
        try:
            resp = await self._client.get(f"/schedule/{job_id}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API get_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            return SkillResult.ok(self._jobs[job_id])
    
    async def list_jobs(self, enabled_only: bool = False) -> SkillResult:
        """List all scheduled jobs."""
        try:
            params: Dict[str, Any] = {}
            if enabled_only:
                params["enabled"] = True
            resp = await self._client.get("/schedule", params=params)
            resp.raise_for_status()
            api_data = resp.json()
            jobs = api_data if isinstance(api_data, list) else api_data.get("jobs", [])
            if enabled_only:
                jobs = [j for j in jobs if j.get("enabled")]
            return SkillResult.ok({
                "jobs": jobs,
                "total": len(jobs),
                "enabled": sum(1 for j in jobs if j.get("enabled")),
            })
        except Exception as e:
            self.logger.warning(f"API list_jobs failed, using fallback: {e}")
            jobs = list(self._jobs.values())
            if enabled_only:
                jobs = [j for j in jobs if j["enabled"]]
            return SkillResult.ok({
                "jobs": jobs,
                "total": len(jobs),
                "enabled": sum(1 for j in jobs if j["enabled"]),
            })
    
    async def enable_job(self, job_id: str) -> SkillResult:
        """Enable a job."""
        try:
            resp = await self._client.put(f"/schedule/{job_id}", json={"enabled": True})
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API enable_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            self._jobs[job_id]["enabled"] = True
            self._jobs[job_id]["next_run"] = self._calculate_next_run(self._jobs[job_id]["schedule"])
            return SkillResult.ok(self._jobs[job_id])
    
    async def disable_job(self, job_id: str) -> SkillResult:
        """Disable a job."""
        try:
            resp = await self._client.put(f"/schedule/{job_id}", json={"enabled": False})
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API disable_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            self._jobs[job_id]["enabled"] = False
            self._jobs[job_id]["next_run"] = None
            return SkillResult.ok(self._jobs[job_id])
    
    async def delete_job(self, job_id: str) -> SkillResult:
        """Delete a job."""
        try:
            resp = await self._client.delete(f"/schedule/{job_id}")
            resp.raise_for_status()
            return SkillResult.ok({"deleted": job_id})
        except Exception as e:
            self.logger.warning(f"API delete_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            job = self._jobs.pop(job_id)
            return SkillResult.ok({"deleted": job_id, "name": job["name"]})
    
    async def get_due_jobs(self) -> SkillResult:
        """Get jobs that are due to run."""
        now = datetime.now(timezone.utc)
        try:
            resp = await self._client.get("/schedule", params={"due": True})
            resp.raise_for_status()
            api_data = resp.json()
            jobs = api_data if isinstance(api_data, list) else api_data.get("jobs", [])
            return SkillResult.ok({
                "due_jobs": jobs,
                "count": len(jobs),
                "checked_at": now.isoformat(),
            })
        except Exception as e:
            self.logger.warning(f"API get_due_jobs failed, using fallback: {e}")
            due_jobs = []
            for job in self._jobs.values():
                if not job["enabled"]:
                    continue
                if job["next_run"]:
                    next_run = datetime.fromisoformat(job["next_run"])
                    if next_run <= now:
                        due_jobs.append(job)
            return SkillResult.ok({
                "due_jobs": due_jobs,
                "count": len(due_jobs),
                "checked_at": now.isoformat(),
            })
    
    async def mark_job_run(self, job_id: str, success: bool = True) -> SkillResult:
        """Mark a job as having run."""
        run_data = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_success": success,
        }
        try:
            resp = await self._client.put(f"/schedule/{job_id}", json=run_data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API mark_job_run failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            job = self._jobs[job_id]
            job["last_run"] = run_data["last_run"]
            job["run_count"] += 1
            job["next_run"] = self._calculate_next_run(job["schedule"])
            job["last_success"] = success
            return SkillResult.ok(job)
    
    def _calculate_next_run(self, schedule: str) -> Optional[str]:
        """Calculate next run time from schedule expression."""
        now = datetime.now(timezone.utc)

        # Simple parsingfor "every X minutes/hours/days"
        if schedule.startswith("every "):
            parts = schedule[6:].split()
            if len(parts) >= 2:
                try:
                    amount = int(parts[0])
                    unit = parts[1].lower()
                    
                    if "minute" in unit:
                        return (now + timedelta(minutes=amount)).isoformat()
                    elif "hour" in unit:
                        return (now + timedelta(hours=amount)).isoformat()
                    elif "day" in unit:
                        return (now + timedelta(days=amount)).isoformat()
                except ValueError:
                    pass
        
        # Default to 1 hour
        return (now + timedelta(hours=1)).isoformat()
