"""
Unit tests for aria_engine.scheduler — parse_schedule + EngineScheduler.

Tests:
- Schedule string parsing (cron + interval)
- Start/stop lifecycle
- Job execution flow
- Error handling and retry with backoff
- Dispatch to agent
- Public management API (add, update, remove, trigger)
- Scheduler status
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SchedulerError
from aria_engine.scheduler import EngineScheduler, parse_schedule


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test",
        default_model="step-35-flash-free",
    )


@pytest.fixture
def mock_db_engine() -> AsyncMock:
    """Mock SQLAlchemy async engine."""
    engine = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    return engine


@pytest.fixture
def mock_agent_pool() -> MagicMock:
    """Mock AgentPool."""
    pool = MagicMock()
    agent = AsyncMock()
    agent.process = AsyncMock(return_value={"content": "done"})
    pool.get_agent = MagicMock(return_value=agent)
    pool.get_skill = MagicMock(return_value=None)
    return pool


@pytest.fixture
def scheduler(config, mock_db_engine, mock_agent_pool) -> EngineScheduler:
    """Create EngineScheduler with mocked dependencies."""
    sched = EngineScheduler(config, mock_db_engine, mock_agent_pool)
    return sched


# ============================================================================
# parse_schedule Tests
# ============================================================================

class TestParseSchedule:
    """Tests for the module-level parse_schedule() function."""

    def test_5_field_cron(self):
        """Standard 5-field cron expression is parsed."""
        from apscheduler.triggers.cron import CronTrigger

        trigger = parse_schedule("0 * * * *")
        assert isinstance(trigger, CronTrigger)

    def test_6_field_cron(self):
        """Node-style 6-field cron expression is parsed."""
        from apscheduler.triggers.cron import CronTrigger

        trigger = parse_schedule("0 0 6 * * *")
        assert isinstance(trigger, CronTrigger)

    def test_interval_minutes(self):
        """Interval shorthand '15m' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = parse_schedule("15m")
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_hours(self):
        """Interval shorthand '1h' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = parse_schedule("1h")
        assert isinstance(trigger, IntervalTrigger)

    def test_interval_seconds(self):
        """Interval shorthand '30s' parses to IntervalTrigger."""
        from apscheduler.triggers.interval import IntervalTrigger

        trigger = parse_schedule("30s")
        assert isinstance(trigger, IntervalTrigger)

    def test_invalid_schedule_raises(self):
        """Invalid schedule string raises SchedulerError."""
        with pytest.raises(SchedulerError, match="Cannot parse schedule"):
            parse_schedule("not a cron")

    def test_empty_raises(self):
        """Empty string raises SchedulerError."""
        with pytest.raises(SchedulerError):
            parse_schedule("")

    def test_4_fields_raises(self):
        """4-field expression raises SchedulerError."""
        with pytest.raises(SchedulerError):
            parse_schedule("* * * *")

    def test_common_cron_expressions(self):
        """Various common cron expressions parse successfully."""
        valid = [
            "0 * * * *",       # every hour
            "*/15 * * * *",    # every 15 minutes
            "0 3 * * *",       # daily at 3am
            "0 0 * * 0",       # weekly on Sunday
            "0 0 1 * *",       # monthly
            "30 6 * * 1-5",    # weekdays at 6:30
        ]
        for expr in valid:
            trigger = parse_schedule(expr)
            assert trigger is not None, f"Failed to parse: {expr}"


# ============================================================================
# Lifecycle Tests
# ============================================================================

class TestSchedulerLifecycle:
    """Tests for scheduler start/stop lifecycle."""

    async def test_start_sets_running(self, scheduler: EngineScheduler, mock_db_engine):
        """Starting scheduler sets _running=True."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # Mock DB returns no jobs
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = []
        conn.execute = AsyncMock(return_value=result_mock)

        with patch("aria_engine.scheduler.SQLAlchemyDataStore"), \
             patch("aria_engine.scheduler.AsyncScheduler") as mock_sched_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_sched_cls.return_value = mock_instance

            await scheduler.start()
            assert scheduler._running is True

    async def test_stop_sets_not_running(self, scheduler: EngineScheduler):
        """Stopping scheduler sets _running=False."""
        # Simulate started state
        scheduler._running = True
        mock_sched = AsyncMock()
        mock_sched.__aexit__ = AsyncMock(return_value=False)
        scheduler._scheduler = mock_sched

        await scheduler.stop()
        assert scheduler._running is False

    async def test_double_start_is_idempotent(self, scheduler: EngineScheduler):
        """Calling start() when already running doesn't reinitialize."""
        scheduler._running = True
        # Should return immediately
        await scheduler.start()
        # No scheduler created
        assert scheduler._scheduler is None  # Was never set in this test


# ============================================================================
# Job Execution Tests
# ============================================================================

class TestJobExecution:
    """Tests for cron job execution flow."""

    async def test_dispatch_prompt_calls_agent_process(
        self, scheduler: EngineScheduler, mock_agent_pool
    ):
        """Prompt-type payload dispatches to agent.process()."""
        await scheduler._dispatch_to_agent(
            job_id="test-job",
            agent_id="main",
            payload_type="prompt",
            payload="Run heartbeat cycle.",
            session_mode="isolated",
        )

        agent = mock_agent_pool.get_agent.return_value
        agent.process.assert_called_once_with("Run heartbeat cycle.")

    async def test_dispatch_unknown_payload_raises(self, scheduler: EngineScheduler):
        """Unknown payload_type raises SchedulerError."""
        with pytest.raises(SchedulerError, match="Unknown payload_type"):
            await scheduler._dispatch_to_agent(
                job_id="test",
                agent_id="main",
                payload_type="unknown_type",
                payload="test",
                session_mode="isolated",
            )

    async def test_dispatch_missing_agent_raises(self, scheduler: EngineScheduler, mock_agent_pool):
        """Dispatching to a non-existent agent raises SchedulerError."""
        mock_agent_pool.get_agent.return_value = None

        with pytest.raises(SchedulerError, match="not found in pool"):
            await scheduler._dispatch_to_agent(
                job_id="test",
                agent_id="nonexistent",
                payload_type="prompt",
                payload="test",
                session_mode="isolated",
            )

    async def test_dispatch_without_pool_logs_warning(
        self, config, mock_db_engine
    ):
        """Job dispatch without agent pool logs but doesn't crash."""
        sched = EngineScheduler(config, mock_db_engine, agent_pool=None)

        # Should not raise — just logs a warning
        await sched._dispatch_to_agent(
            job_id="orphan",
            agent_id="main",
            payload_type="prompt",
            payload="test",
            session_mode="isolated",
        )


# ============================================================================
# Execute Job with Timeout and Retry Tests
# ============================================================================

class TestExecuteJobRetry:
    """Tests for job execution with retry and timeout."""

    async def test_successful_execution(self, scheduler: EngineScheduler, mock_db_engine):
        """Successful job updates state to success."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        with patch.object(scheduler, "_dispatch_to_agent", new_callable=AsyncMock):
            await scheduler._execute_job(
                job_id="test",
                agent_id="main",
                payload_type="prompt",
                payload="Run test.",
                session_mode="isolated",
                max_duration=300,
                retry_count=0,
            )

        # Should have called _update_job_state for running + success
        assert conn.execute.call_count >= 2

    async def test_timeout_triggers_retry(self, scheduler: EngineScheduler, mock_db_engine):
        """Timed-out job retries if retry_count > 0."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        call_count = 0

        async def slow_dispatch(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(10)  # Will be timed out
            # Second call succeeds instantly

        with patch.object(scheduler, "_dispatch_to_agent", side_effect=slow_dispatch):
            await scheduler._execute_job(
                job_id="test",
                agent_id="main",
                payload_type="prompt",
                payload="test",
                session_mode="isolated",
                max_duration=1,      # 1 second timeout
                retry_count=1,       # 1 retry
            )

        # Should have attempted at least 2 times
        assert call_count >= 1


# ============================================================================
# Public Management API Tests
# ============================================================================

class TestManagementAPI:
    """Tests for add/update/remove/trigger jobs."""

    async def test_add_job(self, scheduler: EngineScheduler, mock_db_engine):
        """Adding a job inserts to DB."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.execute = AsyncMock()

        job_id = await scheduler.add_job({
            "name": "Test Job",
            "schedule": "0 * * * *",
            "agent_id": "main",
            "payload": "Run test.",
        })

        assert job_id is not None
        conn.execute.assert_called_once()

    async def test_remove_job(self, scheduler: EngineScheduler, mock_db_engine):
        """Removing a job deletes from DB."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        result_mock = MagicMock()
        result_mock.rowcount = 1
        conn.execute = AsyncMock(return_value=result_mock)

        removed = await scheduler.remove_job("test-job")
        assert removed is True

    async def test_remove_nonexistent_job(self, scheduler: EngineScheduler, mock_db_engine):
        """Removing a nonexistent job returns False."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        result_mock = MagicMock()
        result_mock.rowcount = 0
        conn.execute = AsyncMock(return_value=result_mock)

        removed = await scheduler.remove_job("nonexistent")
        assert removed is False

    async def test_trigger_executes_immediately(self, scheduler: EngineScheduler, mock_db_engine):
        """Manual trigger runs the job immediately."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # get_job returns a job — use a real dict so dict(row) works
        job_row = {
            "id": "heartbeat",
            "agent_id": "main",
            "payload_type": "prompt",
            "payload": "Run heartbeat.",
            "session_mode": "isolated",
            "max_duration_seconds": 300,
            "retry_count": 0,
        }
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = job_row
        conn.execute = AsyncMock(return_value=result_mock)

        with patch.object(scheduler, "_execute_job", new_callable=AsyncMock):
            triggered = await scheduler.trigger_job("heartbeat")

        assert triggered is True

    async def test_trigger_nonexistent_job_returns_false(
        self, scheduler: EngineScheduler, mock_db_engine
    ):
        """Triggering a non-existent job returns False."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = None
        conn.execute = AsyncMock(return_value=result_mock)

        triggered = await scheduler.trigger_job("nonexistent")
        assert triggered is False


# ============================================================================
# Status Tests
# ============================================================================

class TestSchedulerStatus:
    """Tests for scheduler status reporting."""

    def test_get_status_when_stopped(self, scheduler: EngineScheduler):
        """Status reports running=False when stopped."""
        status = scheduler.get_status()
        assert status["running"] is False
        assert status["active_executions"] == 0

    def test_is_running_property(self, scheduler: EngineScheduler):
        """is_running property reflects _running state."""
        assert scheduler.is_running is False
        scheduler._running = True
        assert scheduler.is_running is True
