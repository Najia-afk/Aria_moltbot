"""
Native Scheduler — APScheduler 4.x with PostgreSQL persistence.

Python-native scheduler replacing legacy Node.js cron.
Features:
- APScheduler 4.x async scheduler with SQLAlchemy data store
- Job definitions stored in aria_engine.cron_jobs table
- Job execution routed to agents via AgentPool
- Job state tracking (last_run, status, duration, next_run)
- Error handling with retry + exponential backoff
- Dynamic job management (add/remove/update at runtime)
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from apscheduler import AsyncScheduler
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SchedulerError

logger = logging.getLogger("aria.engine.scheduler")

# Maximum concurrent job executions
MAX_CONCURRENT_JOBS = 5

# Retry backoff cap (seconds)
MAX_BACKOFF_SECONDS = 600


def parse_schedule(schedule_str: str) -> CronTrigger | IntervalTrigger:
    """
    Parse a schedule string into an APScheduler trigger.

    Supports:
    - Cron expressions (6-field node-cron or 5-field standard):
      "0 0 6 * * *" → sec min hour dom month dow
    - Interval shorthand: "15m", "60m", "1h", "30s"

    Args:
        schedule_str: Cron expression or interval shorthand.

    Returns:
        APScheduler trigger instance.

    Raises:
        SchedulerError: If the schedule string cannot be parsed.
    """
    schedule_str = schedule_str.strip()

    # Interval shorthand: "15m", "60m", "1h", "30s"
    if schedule_str.endswith("m") and schedule_str[:-1].isdigit():
        minutes = int(schedule_str[:-1])
        return IntervalTrigger(minutes=minutes)
    if schedule_str.endswith("h") and schedule_str[:-1].isdigit():
        hours = int(schedule_str[:-1])
        return IntervalTrigger(hours=hours)
    if schedule_str.endswith("s") and schedule_str[:-1].isdigit():
        seconds = int(schedule_str[:-1])
        return IntervalTrigger(seconds=seconds)

    # Cron expression
    parts = schedule_str.split()
    if len(parts) == 6:
        # 6-field node-cron: sec min hour dom month dow
        second, minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            second=second,
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )
    elif len(parts) == 5:
        # 5-field standard cron: min hour dom month dow
        minute, hour, day, month, day_of_week = parts
        return CronTrigger(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
        )
    else:
        raise SchedulerError(f"Cannot parse schedule: {schedule_str!r}")


class EngineScheduler:
    """
    Native async scheduler backed by PostgreSQL.

    Lifecycle:
        scheduler = EngineScheduler(config, db_engine)
        await scheduler.start()   # loads jobs from DB, starts APScheduler
        ...
        await scheduler.stop()    # graceful shutdown

    Usage:
        scheduler = EngineScheduler(config, db_engine)
        await scheduler.start()

        # Jobs auto-loaded from DB on start
        # Manual trigger:
        await scheduler.trigger_job("work_cycle")

        # Dynamic management:
        await scheduler.add_job({...})
        await scheduler.update_job("work_cycle", {"enabled": False})
        await scheduler.remove_job("old_job")
    """

    def __init__(
        self,
        config: EngineConfig,
        db_engine: AsyncEngine,
        agent_pool: Any | None = None,
    ):
        self.config = config
        self._db_engine = db_engine
        self._agent_pool = agent_pool
        self._scheduler: AsyncScheduler | None = None
        self._running = False
        self._job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        self._active_executions: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """
        Start the scheduler: initialize APScheduler data store,
        load enabled jobs from DB, and begin scheduling.
        """
        if self._running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting EngineScheduler...")

        # Create APScheduler with PostgreSQL data store
        data_store = SQLAlchemyDataStore(engine=self._db_engine)
        self._scheduler = AsyncScheduler(data_store=data_store)

        # Load and register all enabled jobs from the DB
        await self._load_jobs_from_db()

        # Start the scheduler
        await self._scheduler.__aenter__()
        self._running = True
        logger.info("EngineScheduler started — jobs loaded and scheduled")

    async def stop(self) -> None:
        """Gracefully stop the scheduler and wait for active jobs."""
        if not self._running:
            return

        logger.info("Stopping EngineScheduler...")
        self._running = False

        # Cancel active executions
        for job_id, task in list(self._active_executions.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            logger.debug("Cancelled active execution: %s", job_id)

        self._active_executions.clear()

        # Shutdown APScheduler
        if self._scheduler is not None:
            await self._scheduler.__aexit__(None, None, None)
            self._scheduler = None

        logger.info("EngineScheduler stopped")

    async def _load_jobs_from_db(self) -> None:
        """Load all enabled cron jobs from aria_engine.cron_jobs and register them."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, name, schedule, agent_id, enabled,
                           payload_type, payload, session_mode,
                           max_duration_seconds, retry_count, metadata
                    FROM aria_engine.cron_jobs
                    WHERE enabled = true
                    ORDER BY name
                """)
            )
            rows = result.mappings().all()

        registered = 0
        for row in rows:
            try:
                trigger = parse_schedule(row["schedule"])
                await self._scheduler.add_schedule(
                    self._execute_job,
                    trigger=trigger,
                    id=row["id"],
                    kwargs={
                        "job_id": row["id"],
                        "agent_id": row["agent_id"],
                        "payload_type": row["payload_type"],
                        "payload": row["payload"],
                        "session_mode": row["session_mode"],
                        "max_duration": row["max_duration_seconds"],
                        "retry_count": row["retry_count"],
                    },
                )
                registered += 1
                logger.debug("Registered job: %s (%s)", row["name"], row["schedule"])
            except Exception as e:
                logger.error("Failed to register job %s: %s", row["id"], e)

        logger.info("Loaded %d/%d enabled cron jobs", registered, len(rows))

    async def _execute_job(
        self,
        job_id: str,
        agent_id: str,
        payload_type: str,
        payload: str,
        session_mode: str,
        max_duration: int,
        retry_count: int,
    ) -> None:
        """
        Execute a single cron job with concurrency control, timeout,
        and retry with exponential backoff.
        """
        async with self._job_semaphore:
            attempt = 0
            max_attempts = retry_count + 1
            last_error: str | None = None
            elapsed_ms = 0

            while attempt < max_attempts:
                start_time = time.monotonic()
                try:
                    # Update state: running
                    await self._update_job_state(
                        job_id,
                        status="running",
                        last_run_at=datetime.now(timezone.utc),
                    )

                    # Execute with timeout
                    await asyncio.wait_for(
                        self._dispatch_to_agent(
                            job_id=job_id,
                            agent_id=agent_id,
                            payload_type=payload_type,
                            payload=payload,
                            session_mode=session_mode,
                        ),
                        timeout=max_duration,
                    )

                    elapsed_ms = int((time.monotonic() - start_time) * 1000)

                    # Update state: success
                    await self._update_job_state(
                        job_id,
                        status="success",
                        last_duration_ms=elapsed_ms,
                        increment_success=True,
                    )
                    logger.info(
                        "Job %s completed in %dms", job_id, elapsed_ms
                    )
                    return

                except asyncio.TimeoutError:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    last_error = f"Timeout after {max_duration}s"
                    logger.warning("Job %s timed out (attempt %d)", job_id, attempt + 1)

                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    last_error = str(e)
                    logger.error(
                        "Job %s failed (attempt %d): %s", job_id, attempt + 1, e
                    )

                attempt += 1

                if attempt < max_attempts:
                    # Exponential backoff: 2^attempt seconds, capped
                    backoff = min(2**attempt, MAX_BACKOFF_SECONDS)
                    logger.info(
                        "Job %s retrying in %ds (attempt %d/%d)",
                        job_id, backoff, attempt + 1, max_attempts,
                    )
                    await asyncio.sleep(backoff)

            # All retries exhausted
            await self._update_job_state(
                job_id,
                status="failed",
                last_duration_ms=elapsed_ms,
                last_error=last_error,
                increment_fail=True,
            )
            logger.error(
                "Job %s failed after %d attempts: %s", job_id, max_attempts, last_error
            )

    async def _dispatch_to_agent(
        self,
        job_id: str,
        agent_id: str,
        payload_type: str,
        payload: str,
        session_mode: str,
    ) -> None:
        """
        Dispatch a job to the appropriate agent for execution.

        payload_type determines execution strategy:
        - 'prompt': send payload as chat message to agent
        - 'skill': execute a skill function directly
        - 'pipeline': run a pipeline by name
        """
        if self._agent_pool is None:
            logger.warning(
                "AgentPool not available — job %s logged but not dispatched", job_id
            )
            return

        agent = self._agent_pool.get_agent(agent_id)
        if agent is None:
            raise SchedulerError(f"Agent {agent_id!r} not found in pool")

        if payload_type == "prompt":
            # Send the payload text as a message to the agent
            await agent.process(payload)

        elif payload_type == "skill":
            # payload format: "skill_name.function_name {'arg': 'val'}"
            import json as _json

            parts = payload.strip().split(" ", 1)
            skill_func = parts[0]
            args_str = parts[1] if len(parts) > 1 else "{}"
            skill_name, func_name = skill_func.rsplit(".", 1)
            args = _json.loads(args_str)

            skill = self._agent_pool.get_skill(skill_name)
            if skill is None:
                raise SchedulerError(f"Skill {skill_name!r} not found")

            func = getattr(skill, func_name, None)
            if func is None:
                raise SchedulerError(
                    f"Function {func_name!r} not found on skill {skill_name!r}"
                )
            await func(**args)

        elif payload_type == "pipeline":
            from aria_skills.pipeline_executor import PipelineExecutor

            executor = PipelineExecutor()
            await executor.run(payload)

        else:
            raise SchedulerError(f"Unknown payload_type: {payload_type!r}")

    async def _update_job_state(
        self,
        job_id: str,
        status: str | None = None,
        last_run_at: datetime | None = None,
        last_duration_ms: int | None = None,
        last_error: str | None = None,
        increment_success: bool = False,
        increment_fail: bool = False,
    ) -> None:
        """Update job execution state in the database."""
        set_clauses = ["updated_at = NOW()"]
        params: dict[str, Any] = {"job_id": job_id}

        if status is not None:
            set_clauses.append("last_status = :status")
            params["status"] = status
        if last_run_at is not None:
            set_clauses.append("last_run_at = :last_run_at")
            params["last_run_at"] = last_run_at
        if last_duration_ms is not None:
            set_clauses.append("last_duration_ms = :last_duration_ms")
            params["last_duration_ms"] = last_duration_ms
        if last_error is not None:
            set_clauses.append("last_error = :last_error")
            params["last_error"] = last_error
        if increment_success:
            set_clauses.append("run_count = run_count + 1")
            set_clauses.append("success_count = success_count + 1")
        if increment_fail:
            set_clauses.append("run_count = run_count + 1")
            set_clauses.append("fail_count = fail_count + 1")

        query = f"""
            UPDATE aria_engine.cron_jobs
            SET {', '.join(set_clauses)}
            WHERE id = :job_id
        """

        async with self._db_engine.begin() as conn:
            await conn.execute(text(query), params)

    # ── Public management API ────────────────────────────────────────

    async def add_job(self, job_data: dict[str, Any]) -> str:
        """
        Add a new cron job to the database and register it with APScheduler.

        Args:
            job_data: Dict with keys: id (optional), name, schedule, agent_id,
                      payload_type, payload, session_mode, enabled, etc.

        Returns:
            The job ID.
        """
        job_id = job_data.get("id") or str(uuid4())

        async with self._db_engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO aria_engine.cron_jobs
                        (id, name, schedule, agent_id, enabled, payload_type,
                         payload, session_mode, max_duration_seconds, retry_count)
                    VALUES
                        (:id, :name, :schedule, :agent_id, :enabled, :payload_type,
                         :payload, :session_mode, :max_duration, :retry_count)
                """),
                {
                    "id": job_id,
                    "name": job_data["name"],
                    "schedule": job_data["schedule"],
                    "agent_id": job_data.get("agent_id", "main"),
                    "enabled": job_data.get("enabled", True),
                    "payload_type": job_data.get("payload_type", "prompt"),
                    "payload": job_data["payload"],
                    "session_mode": job_data.get("session_mode", "isolated"),
                    "max_duration": job_data.get("max_duration_seconds", 300),
                    "retry_count": job_data.get("retry_count", 0),
                },
            )

        # Register with APScheduler if enabled
        if job_data.get("enabled", True) and self._scheduler:
            trigger = parse_schedule(job_data["schedule"])
            await self._scheduler.add_schedule(
                self._execute_job,
                trigger=trigger,
                id=job_id,
                kwargs={
                    "job_id": job_id,
                    "agent_id": job_data.get("agent_id", "main"),
                    "payload_type": job_data.get("payload_type", "prompt"),
                    "payload": job_data["payload"],
                    "session_mode": job_data.get("session_mode", "isolated"),
                    "max_duration": job_data.get("max_duration_seconds", 300),
                    "retry_count": job_data.get("retry_count", 0),
                },
            )

        logger.info("Added job: %s (%s)", job_data["name"], job_id)
        return job_id

    async def update_job(self, job_id: str, updates: dict[str, Any]) -> bool:
        """
        Update an existing cron job in the DB and re-register with APScheduler.

        Args:
            job_id: Job identifier.
            updates: Dict of field→value pairs to update.

        Returns:
            True if the job was updated.
        """
        allowed_fields = {
            "name", "schedule", "agent_id", "enabled", "payload_type",
            "payload", "session_mode", "max_duration_seconds", "retry_count",
        }
        filtered = {k: v for k, v in updates.items() if k in allowed_fields}
        if not filtered:
            return False

        set_parts = [f"{k} = :{k}" for k in filtered]
        set_parts.append("updated_at = NOW()")
        filtered["job_id"] = job_id

        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    UPDATE aria_engine.cron_jobs
                    SET {', '.join(set_parts)}
                    WHERE id = :job_id
                """),
                filtered,
            )
            if result.rowcount == 0:
                return False

        # Re-register with APScheduler if schedule or enabled changed
        if self._scheduler and ("schedule" in updates or "enabled" in updates):
            # Remove old schedule
            try:
                await self._scheduler.remove_schedule(job_id)
            except Exception:
                pass

            # Re-add if enabled
            if updates.get("enabled", True):
                # Re-read full job from DB
                job = await self.get_job(job_id)
                if job:
                    trigger = parse_schedule(job["schedule"])
                    await self._scheduler.add_schedule(
                        self._execute_job,
                        trigger=trigger,
                        id=job_id,
                        kwargs={
                            "job_id": job_id,
                            "agent_id": job["agent_id"],
                            "payload_type": job["payload_type"],
                            "payload": job["payload"],
                            "session_mode": job["session_mode"],
                            "max_duration": job["max_duration_seconds"],
                            "retry_count": job["retry_count"],
                        },
                    )

        logger.info("Updated job: %s", job_id)
        return True

    async def remove_job(self, job_id: str) -> bool:
        """Remove a job from the database and APScheduler."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("DELETE FROM aria_engine.cron_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            )

        if self._scheduler:
            try:
                await self._scheduler.remove_schedule(job_id)
            except Exception:
                pass

        removed = result.rowcount > 0
        if removed:
            logger.info("Removed job: %s", job_id)
        return removed

    async def trigger_job(self, job_id: str) -> bool:
        """
        Manually trigger a job immediately (run now), regardless of schedule.

        Args:
            job_id: Job identifier.

        Returns:
            True if the job was triggered.
        """
        job = await self.get_job(job_id)
        if not job:
            return False

        # Run in background task
        task = asyncio.create_task(
            self._execute_job(
                job_id=job_id,
                agent_id=job["agent_id"],
                payload_type=job["payload_type"],
                payload=job["payload"],
                session_mode=job["session_mode"],
                max_duration=job["max_duration_seconds"],
                retry_count=0,  # No retry for manual triggers
            )
        )
        self._active_executions[job_id] = task
        task.add_done_callback(lambda _: self._active_executions.pop(job_id, None))

        logger.info("Manually triggered job: %s", job_id)
        return True

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a single job by ID."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT * FROM aria_engine.cron_jobs WHERE id = :job_id"),
                {"job_id": job_id},
            )
            row = result.mappings().first()
            return dict(row) if row else None

    async def list_jobs(self) -> list[dict[str, Any]]:
        """List all cron jobs with current state."""
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, name, schedule, agent_id, enabled,
                           payload_type, session_mode, last_run_at,
                           last_status, last_duration_ms, last_error,
                           next_run_at, run_count, success_count, fail_count,
                           created_at, updated_at
                    FROM aria_engine.cron_jobs
                    ORDER BY name
                """)
            )
            return [dict(row) for row in result.mappings().all()]

    async def get_job_history(
        self, job_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get execution history for a job from activity_log.

        Cron job executions are logged as activities with
        action='cron_execution' and details.job=<job_id>.
        """
        async with self._db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, action, skill, details, success,
                           created_at, duration_ms
                    FROM activity_log
                    WHERE action = 'cron_execution'
                      AND details->>'job' = :job_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"job_id": job_id, "limit": limit},
            )
            return [dict(row) for row in result.mappings().all()]

    @property
    def is_running(self) -> bool:
        """Whether the scheduler is currently running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status summary."""
        return {
            "running": self._running,
            "active_executions": len(self._active_executions),
            "active_job_ids": list(self._active_executions.keys()),
            "max_concurrent": MAX_CONCURRENT_JOBS,
        }
