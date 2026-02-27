# aria_skills/schedule.py
"""
Job scheduling skill.

Manages scheduled jobs and recurring tasks.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from aria_skills.api_client import get_api_client
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
        self._jobs: dict[str, dict] = {}  # fallback cache
        self._job_counter = 0
        self._api = None
    
    @property
    def name(self) -> str:
        return "schedule"
    
    async def initialize(self) -> bool:
        """Initialize scheduler."""
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Schedule skill initialized (API-backed)")
        return True
    
    async def close(self):
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
    
    async def health_check(self) -> SkillStatus:
        """Check scheduler availability."""
        return self._status
    
    @logged_method()
    async def create_job(
        self,
        name: str,
        schedule: str,  # cron-like or "every X minutes/hours"
        action: str | None = None,
        params: dict | None = None,
        enabled: bool = True,
        **kwargs,
    ) -> SkillResult:
        """
        Create a scheduled job.
        
        Args:
            name: Job name
            schedule: Schedule expression
            action: Action to perform (also accepts ``type`` alias from model payloads)
            params: Action parameters
            enabled: Whether job is active
            **kwargs: Extra fields are absorbed for caller compatibility
            
        Returns:
            SkillResult with job details
        """
        # Compatibility: some callers send `type` instead of `action`
        normalized_action = action or kwargs.get("type")
        if not normalized_action:
            return SkillResult.fail("action (or type) is required")
        self._job_counter += 1
        job_id = f"job_{self._job_counter}"
        
        job = {
            "id": job_id,
            "name": name,
            "schedule": schedule,
            "action": normalized_action,
            "params": params or {},
            "enabled": enabled,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_run": None,
            "next_run": self._calculate_next_run(schedule),
            "run_count": 0,
        }
        
        try:
            result = await self._api.post("/schedule", data=job)
            if not result:
                raise Exception(result.error)
            api_data = result.data
            return SkillResult.ok(api_data if api_data else job)
        except Exception as e:
            self.logger.warning(f"API create_job failed, using fallback: {e}")
            self._jobs[job_id] = job
            return SkillResult.ok(job)
    
    @logged_method()
    async def get_job(self, job_id: str) -> SkillResult:
        """Get a specific job."""
        try:
            result = await self._api.get(f"/schedule/{job_id}")
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            self.logger.warning(f"API get_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            return SkillResult.ok(self._jobs[job_id])
    
    @logged_method()
    async def list_jobs(self, enabled_only: bool = False) -> SkillResult:
        """List all scheduled jobs."""
        try:
            params: dict[str, Any] = {}
            if enabled_only:
                params["enabled"] = True
            resp = await self._api.get("/schedule", params=params)
            if not resp:
                raise Exception(resp.error)
            api_data = resp.data
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
    
    @logged_method()
    async def enable_job(self, job_id: str) -> SkillResult:
        """Enable a job."""
        try:
            result = await self._api.put(f"/schedule/{job_id}", data={"enabled": True})
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            self.logger.warning(f"API enable_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            self._jobs[job_id]["enabled"] = True
            self._jobs[job_id]["next_run"] = self._calculate_next_run(self._jobs[job_id]["schedule"])
            return SkillResult.ok(self._jobs[job_id])
    
    @logged_method()
    async def disable_job(self, job_id: str) -> SkillResult:
        """Disable a job."""
        try:
            result = await self._api.put(f"/schedule/{job_id}", data={"enabled": False})
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            self.logger.warning(f"API disable_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            self._jobs[job_id]["enabled"] = False
            self._jobs[job_id]["next_run"] = None
            return SkillResult.ok(self._jobs[job_id])
    
    @logged_method()
    async def delete_job(self, job_id: str) -> SkillResult:
        """Delete a job."""
        try:
            result = await self._api.delete(f"/schedule/{job_id}")
            if not result:
                raise Exception(result.error)
            return SkillResult.ok({"deleted": job_id})
        except Exception as e:
            self.logger.warning(f"API delete_job failed, using fallback: {e}")
            if job_id not in self._jobs:
                return SkillResult.fail(f"Job not found: {job_id}")
            job = self._jobs.pop(job_id)
            return SkillResult.ok({"deleted": job_id, "name": job["name"]})
    
    @logged_method()
    async def get_due_jobs(self) -> SkillResult:
        """Get jobs that are due to run."""
        now = datetime.now(timezone.utc)
        try:
            result = await self._api.get("/schedule", params={"due": True})
            if not result:
                raise Exception(result.error)
            api_data = result.data
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
    
    @logged_method()
    async def mark_job_run(self, job_id: str, success: bool = True) -> SkillResult:
        """Mark a job as having run."""
        run_data = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_success": success,
        }
        try:
            result = await self._api.put(f"/schedule/{job_id}", data=run_data)
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
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
    
    def _calculate_next_run(self, schedule: str) -> str | None:
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
