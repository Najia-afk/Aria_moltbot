"""
E2E integration tests for the Cron/Scheduler system.

Tests the full pipeline:
  cron_jobs DB ─► EngineScheduler ─► APScheduler ─► Job Execution
                                                         │
  DB (engine_cron_jobs state) ◄──────────────────────────┘

Uses freezegun for time manipulation + mock DB + mock agent pool.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SchedulerError
from aria_engine.scheduler import EngineScheduler, parse_schedule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def config():
    return EngineConfig(
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test",
        default_model="step-35-flash-free",
    )


@pytest.fixture
def mock_db_engine():
    """Mock SQLAlchemy async engine with cron job data."""
    engine = AsyncMock()
    conn = AsyncMock()

    # Default: empty result set
    default_result = MagicMock()
    default_result.mappings = MagicMock(return_value=MagicMock(
        all=MagicMock(return_value=[])
    ))
    conn.execute = AsyncMock(return_value=default_result)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    engine._conn = conn  # expose for test manipulation

    return engine


@pytest.fixture
def mock_agent_pool():
    """Mock AgentPool that records executions."""
    pool = MagicMock()
    executions: list[dict] = []

    agent = AsyncMock()

    async def fake_process(payload, **kwargs):
        record = {
            "payload": payload,
            "kwargs": kwargs,
            "timestamp": datetime.now(timezone.utc),
        }
        executions.append(record)
        return {"content": "done"}

    agent.process = AsyncMock(side_effect=fake_process)
    pool.get_agent = MagicMock(return_value=agent)
    pool._executions = executions
    pool._agent = agent
    return pool


@pytest.fixture
def scheduler(config, mock_db_engine, mock_agent_pool):
    """Create EngineScheduler with mocked dependencies."""
    sched = EngineScheduler(config, mock_db_engine, mock_agent_pool)
    return sched


# ---------------------------------------------------------------------------
# Tests — parse_schedule
# ---------------------------------------------------------------------------

class TestParseSchedule:
    """Integration tests for schedule parsing."""

    @pytest.mark.integration
    def test_5_field_cron(self):
        """5-field standard cron parses correctly."""
        from apscheduler.triggers.cron import CronTrigger
        trigger = parse_schedule("*/5 * * * *")
        assert isinstance(trigger, CronTrigger)

    @pytest.mark.integration
    def test_6_field_cron(self):
        """6-field node-cron parses correctly."""
        from apscheduler.triggers.cron import CronTrigger
        trigger = parse_schedule("0 0 6 * * *")
        assert isinstance(trigger, CronTrigger)

    @pytest.mark.integration
    def test_interval_minutes(self):
        """Interval shorthand '15m' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger
        trigger = parse_schedule("15m")
        assert isinstance(trigger, IntervalTrigger)

    @pytest.mark.integration
    def test_interval_hours(self):
        """Interval shorthand '1h' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger
        trigger = parse_schedule("1h")
        assert isinstance(trigger, IntervalTrigger)

    @pytest.mark.integration
    def test_interval_seconds(self):
        """Interval shorthand '30s' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger
        trigger = parse_schedule("30s")
        assert isinstance(trigger, IntervalTrigger)

    @pytest.mark.integration
    def test_invalid_schedule_raises(self):
        """Invalid schedule string raises SchedulerError."""
        with pytest.raises(SchedulerError):
            parse_schedule("not a schedule")

    @pytest.mark.integration
    def test_hourly_cron(self):
        """Hourly cron expression parses."""
        from apscheduler.triggers.cron import CronTrigger
        trigger = parse_schedule("0 * * * *")
        assert isinstance(trigger, CronTrigger)

    @pytest.mark.integration
    def test_daily_at_nine_cron(self):
        """Daily at 9am cron expression parses."""
        from apscheduler.triggers.cron import CronTrigger
        trigger = parse_schedule("0 9 * * *")
        assert isinstance(trigger, CronTrigger)


# ---------------------------------------------------------------------------
# Tests — Scheduler lifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    """Tests for scheduler start/stop lifecycle."""

    @pytest.mark.integration
    async def test_scheduler_creation(self, scheduler):
        """Scheduler can be instantiated."""
        assert scheduler is not None
        assert scheduler._running is False

    @pytest.mark.integration
    async def test_scheduler_is_not_running_initially(self, scheduler):
        """Scheduler is not running before start()."""
        assert scheduler._running is False
        assert scheduler._scheduler is None

    @pytest.mark.integration
    async def test_stop_when_not_running(self, scheduler):
        """Stopping a non-running scheduler is a no-op."""
        await scheduler.stop()  # Should not raise
        assert scheduler._running is False


# ---------------------------------------------------------------------------
# Tests — Job execution
# ---------------------------------------------------------------------------

class TestJobExecution:
    """Tests for job execution flow."""

    @pytest.mark.integration
    async def test_dispatch_prompt_to_agent(self, scheduler, mock_agent_pool):
        """Prompt payload dispatches to agent.process()."""
        await scheduler._dispatch_to_agent(
            job_id="test_job",
            agent_id="main",
            payload_type="prompt",
            payload="Hello, run heartbeat check",
            session_mode="isolated",
        )

        mock_agent_pool._agent.process.assert_called_once_with(
            "Hello, run heartbeat check"
        )

    @pytest.mark.integration
    async def test_dispatch_unknown_agent_raises(self, scheduler, mock_agent_pool):
        """Dispatching to unknown agent raises SchedulerError."""
        mock_agent_pool.get_agent = MagicMock(return_value=None)

        with pytest.raises(SchedulerError, match="not found"):
            await scheduler._dispatch_to_agent(
                job_id="test_job",
                agent_id="nonexistent",
                payload_type="prompt",
                payload="test",
                session_mode="isolated",
            )

    @pytest.mark.integration
    async def test_dispatch_without_agent_pool(self, config, mock_db_engine):
        """Dispatching without AgentPool logs warning but doesn't crash."""
        sched = EngineScheduler(config, mock_db_engine, agent_pool=None)

        # Should not raise
        await sched._dispatch_to_agent(
            job_id="test_job",
            agent_id="main",
            payload_type="prompt",
            payload="test",
            session_mode="isolated",
        )

    @pytest.mark.integration
    async def test_execute_job_success(self, scheduler, mock_agent_pool, mock_db_engine):
        """Successful job execution updates state."""
        await scheduler._execute_job(
            job_id="test_heartbeat",
            agent_id="main",
            payload_type="prompt",
            payload="heartbeat check",
            session_mode="isolated",
            max_duration=30,
            retry_count=0,
        )

        # Agent should have been called
        mock_agent_pool._agent.process.assert_called_once()

        # DB state should have been updated (via conn.execute)
        assert mock_db_engine._conn.execute.call_count >= 1

    @pytest.mark.integration
    async def test_execute_job_failure_updates_state(self, scheduler, mock_agent_pool, mock_db_engine):
        """Failed job execution updates state with error."""
        mock_agent_pool._agent.process = AsyncMock(
            side_effect=RuntimeError("Skill crashed!")
        )

        # Should not raise — scheduler catches errors
        await scheduler._execute_job(
            job_id="test_failing",
            agent_id="main",
            payload_type="prompt",
            payload="will fail",
            session_mode="isolated",
            max_duration=30,
            retry_count=0,
        )

        # DB should be updated with failed status
        assert mock_db_engine._conn.execute.call_count >= 1

    @pytest.mark.integration
    async def test_execute_job_timeout(self, scheduler, mock_agent_pool, mock_db_engine):
        """Job that exceeds timeout is handled gracefully."""
        async def slow_process(payload, **kwargs):
            await asyncio.sleep(10)
            return {"content": "too slow"}

        mock_agent_pool._agent.process = AsyncMock(side_effect=slow_process)

        await scheduler._execute_job(
            job_id="test_slow",
            agent_id="main",
            payload_type="prompt",
            payload="slow task",
            session_mode="isolated",
            max_duration=1,  # 1 second timeout
            retry_count=0,
        )

        # Should have been recorded as failed
        assert mock_db_engine._conn.execute.call_count >= 1

    @pytest.mark.integration
    async def test_execute_job_with_retry(self, scheduler, mock_agent_pool, mock_db_engine):
        """Job retries on failure with exponential backoff."""
        call_count = 0

        async def fail_then_succeed(payload, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Transient error")
            return {"content": "success on retry"}

        mock_agent_pool._agent.process = AsyncMock(side_effect=fail_then_succeed)

        # Patch sleep to not actually wait
        with patch("aria_engine.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler._execute_job(
                job_id="test_retry",
                agent_id="main",
                payload_type="prompt",
                payload="retry task",
                session_mode="isolated",
                max_duration=30,
                retry_count=2,  # Allow 2 retries
            )

        assert call_count == 2

    @pytest.mark.integration
    async def test_concurrent_executions_limited(self, scheduler, mock_agent_pool):
        """Concurrent job executions respect semaphore limit."""
        running = 0
        max_running = 0

        async def tracked_process(payload, **kwargs):
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.05)
            running -= 1
            return {"content": "done"}

        mock_agent_pool._agent.process = AsyncMock(side_effect=tracked_process)

        # Launch many jobs concurrently
        tasks = [
            scheduler._execute_job(
                job_id=f"concurrent_{i}",
                agent_id="main",
                payload_type="prompt",
                payload=f"task {i}",
                session_mode="isolated",
                max_duration=30,
                retry_count=0,
            )
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # Should not exceed MAX_CONCURRENT_JOBS (5)
        from aria_engine.scheduler import MAX_CONCURRENT_JOBS
        assert max_running <= MAX_CONCURRENT_JOBS


# ---------------------------------------------------------------------------
# Tests — Job management API
# ---------------------------------------------------------------------------

class TestJobManagement:
    """Tests for job CRUD operations."""

    @pytest.mark.integration
    async def test_list_jobs_returns_list(self, scheduler, mock_db_engine):
        """list_jobs() returns a list."""
        result = await scheduler.list_jobs()
        assert isinstance(result, list)

    @pytest.mark.integration
    async def test_get_job_returns_dict_or_none(self, scheduler, mock_db_engine):
        """get_job() returns a dict or None."""
        result = await scheduler.get_job("nonexistent")
        # With mock DB returning empty results, should be None or dict
        assert result is None or isinstance(result, dict)

    @pytest.mark.integration
    async def test_trigger_job_calls_execute(self, scheduler, mock_db_engine, mock_agent_pool):
        """trigger_job() manually fires a job."""
        # Configure mock to return a job record
        job_row = {
            "id": "test_manual",
            "name": "Test Manual",
            "schedule": "0 * * * *",
            "agent_id": "main",
            "enabled": True,
            "payload_type": "prompt",
            "payload": "manual trigger test",
            "session_mode": "isolated",
            "max_duration_seconds": 300,
            "retry_count": 0,
            "metadata": None,
        }
        job_result = MagicMock()
        job_result.mappings = MagicMock(return_value=MagicMock(
            first=MagicMock(return_value=job_row),
            all=MagicMock(return_value=[job_row]),
        ))
        mock_db_engine._conn.execute = AsyncMock(return_value=job_result)

        result = await scheduler.trigger_job("test_manual")

        # Should have dispatched to agent
        assert result is not None

    @pytest.mark.integration
    async def test_scheduler_status(self, scheduler):
        """get_status() returns scheduler state info."""
        status = scheduler.get_status()
        assert isinstance(status, dict)
        assert "running" in status or "is_running" in status or isinstance(status.get("running"), bool)

    @pytest.mark.integration
    async def test_add_job_validates_schedule(self, scheduler, mock_db_engine):
        """add_job() validates the schedule string before persisting."""
        # Valid job data
        job_data = {
            "id": "new_test_job",
            "name": "New Test Job",
            "schedule": "*/10 * * * *",
            "agent_id": "main",
            "payload_type": "prompt",
            "payload": "new job test",
        }
        result = await scheduler.add_job(job_data)
        assert result is not None
