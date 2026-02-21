# S10-03: Unit Tests for EngineScheduler
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 10

## Problem
`aria_engine/scheduler.py` manages all 15+ cron jobs — heartbeat, social posting, memory consolidation, reflection. If the scheduler fails, Aria becomes inert. No unit tests exist for job registration, execution, error handling, retry logic, or cron expression parsing.

## Root Cause
Scheduler was built in Sprint 3 and tested only via manual `docker compose up` verification. Automated tests were deferred because scheduler testing requires time manipulation and complex mocking.

## Fix
### `tests/unit/test_scheduler.py`
```python
"""
Unit tests for aria_engine.scheduler.EngineScheduler.

Tests:
- Start/stop lifecycle
- Job registration (add, remove, update)
- Job execution flow
- Error handling and retry
- Cron expression parsing
- Agent routing for cron jobs
- Job enable/disable toggle
- Manual trigger
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

from aria_engine.config import EngineConfig
from aria_engine.scheduler import EngineScheduler


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
def mock_db():
    """Mock database session for scheduler."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.fixture
def scheduler(config: EngineConfig, mock_db) -> EngineScheduler:
    """Create EngineScheduler with mocked dependencies."""
    sched = EngineScheduler(config)
    sched._get_db_session = AsyncMock(return_value=mock_db)
    sched._apscheduler = MagicMock()
    return sched


@pytest.fixture
def sample_job() -> dict[str, Any]:
    """Sample cron job definition."""
    return {
        "id": "heartbeat",
        "name": "Heartbeat",
        "schedule": "0 * * * *",  # every hour
        "agent_id": "main",
        "enabled": True,
        "payload_type": "prompt",
        "payload": "Run heartbeat cycle: reflect on recent activity and update status.",
        "session_mode": "isolated",
        "max_duration_seconds": 300,
        "retry_count": 0,
    }


@pytest.fixture
def sample_jobs() -> list[dict[str, Any]]:
    """Multiple sample cron jobs."""
    return [
        {
            "id": "heartbeat",
            "name": "Heartbeat",
            "schedule": "0 * * * *",
            "agent_id": "main",
            "enabled": True,
            "payload_type": "prompt",
            "payload": "Run heartbeat cycle.",
            "session_mode": "isolated",
            "max_duration_seconds": 300,
            "retry_count": 0,
        },
        {
            "id": "social_check",
            "name": "Social Media Check",
            "schedule": "*/30 * * * *",
            "agent_id": "social",
            "enabled": True,
            "payload_type": "skill",
            "payload": "social.check_mentions",
            "session_mode": "shared",
            "max_duration_seconds": 120,
            "retry_count": 2,
        },
        {
            "id": "memory_consolidation",
            "name": "Memory Consolidation",
            "schedule": "0 3 * * *",
            "agent_id": "main",
            "enabled": False,
            "payload_type": "pipeline",
            "payload": "memory_consolidation_pipeline",
            "session_mode": "isolated",
            "max_duration_seconds": 600,
            "retry_count": 1,
        },
    ]


# ============================================================================
# Lifecycle Tests
# ============================================================================

class TestSchedulerLifecycle:
    """Tests for scheduler start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_initializes_apscheduler(self, scheduler: EngineScheduler):
        """Starting scheduler initializes APScheduler and loads jobs from DB."""
        with patch.object(scheduler, "_load_jobs_from_db", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = []

            await scheduler.start()

            assert scheduler._running is True
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_shuts_down_gracefully(self, scheduler: EngineScheduler):
        """Stopping scheduler waits for running jobs to finish."""
        scheduler._running = True
        scheduler._active_jobs = {}

        await scheduler.stop()

        assert scheduler._running is False
        scheduler._apscheduler.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self, scheduler: EngineScheduler):
        """Calling start() twice doesn't create duplicate schedulers."""
        with patch.object(scheduler, "_load_jobs_from_db", new_callable=AsyncMock) as mock_load:
            mock_load.return_value = []
            scheduler._running = True

            await scheduler.start()  # Should be no-op

            mock_load.assert_not_called()


# ============================================================================
# Job Registration Tests
# ============================================================================

class TestJobRegistration:
    """Tests for adding, removing, and updating cron jobs."""

    @pytest.mark.asyncio
    async def test_add_job(self, scheduler: EngineScheduler, sample_job):
        """Adding a job registers it in APScheduler and DB."""
        with patch.object(scheduler, "_save_job_to_db", new_callable=AsyncMock):
            result = await scheduler.add_job(sample_job)

            assert result["id"] == "heartbeat"
            assert result["status"] == "registered"
            scheduler._apscheduler.add_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_job(self, scheduler: EngineScheduler, sample_job):
        """Removing a job unregisters it from APScheduler and DB."""
        scheduler._jobs = {"heartbeat": sample_job}

        with patch.object(scheduler, "_delete_job_from_db", new_callable=AsyncMock):
            result = await scheduler.remove_job("heartbeat")

            assert result["status"] == "removed"
            scheduler._apscheduler.remove_job.assert_called_once_with("heartbeat")

    @pytest.mark.asyncio
    async def test_update_job_schedule(self, scheduler: EngineScheduler, sample_job):
        """Updating a job's schedule reschedules it."""
        scheduler._jobs = {"heartbeat": sample_job}

        with patch.object(scheduler, "_save_job_to_db", new_callable=AsyncMock):
            result = await scheduler.update_job("heartbeat", {"schedule": "*/15 * * * *"})

            assert result["schedule"] == "*/15 * * * *"

    @pytest.mark.asyncio
    async def test_toggle_job_enabled(self, scheduler: EngineScheduler, sample_job):
        """Toggling a job's enabled state pauses/resumes it."""
        scheduler._jobs = {"heartbeat": sample_job}

        with patch.object(scheduler, "_save_job_to_db", new_callable=AsyncMock):
            # Disable
            result = await scheduler.toggle_job("heartbeat", enabled=False)
            assert result["enabled"] is False

            # Re-enable
            result = await scheduler.toggle_job("heartbeat", enabled=True)
            assert result["enabled"] is True


# ============================================================================
# Job Execution Tests
# ============================================================================

class TestJobExecution:
    """Tests for cron job execution flow."""

    @pytest.mark.asyncio
    async def test_prompt_job_creates_session(self, scheduler: EngineScheduler, sample_job):
        """Prompt-type jobs create a chat session and send the prompt."""
        with patch.object(scheduler, "_execute_prompt_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "status": "success",
                "duration_ms": 1500,
                "output": "Heartbeat complete.",
            }

            result = await scheduler._execute_job(sample_job)

            assert result["status"] == "success"
            mock_exec.assert_called_once_with(sample_job)

    @pytest.mark.asyncio
    async def test_skill_job_invokes_skill(self, scheduler: EngineScheduler):
        """Skill-type jobs invoke the skill directly."""
        skill_job = {
            "id": "social_check",
            "payload_type": "skill",
            "payload": "social.check_mentions",
            "agent_id": "social",
            "max_duration_seconds": 120,
        }

        with patch.object(scheduler, "_execute_skill_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"status": "success", "duration_ms": 500}

            result = await scheduler._execute_job(skill_job)

            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_job_timeout_enforcement(self, scheduler: EngineScheduler, sample_job):
        """Jobs that exceed max_duration_seconds are cancelled."""
        sample_job["max_duration_seconds"] = 1  # 1 second timeout

        async def slow_execution(job):
            await asyncio.sleep(10)
            return {"status": "success"}

        with patch.object(scheduler, "_execute_prompt_job", side_effect=slow_execution):
            result = await scheduler._execute_job_with_timeout(sample_job)

            assert result["status"] == "timeout"

    @pytest.mark.asyncio
    async def test_job_updates_last_run(self, scheduler: EngineScheduler, sample_job):
        """After execution, last_run_at and counters are updated in DB."""
        with patch.object(scheduler, "_execute_prompt_job", new_callable=AsyncMock) as mock_exec, \
             patch.object(scheduler, "_update_job_stats", new_callable=AsyncMock) as mock_stats:
            mock_exec.return_value = {"status": "success", "duration_ms": 200}

            await scheduler._execute_job(sample_job)

            mock_stats.assert_called_once()
            call_kwargs = mock_stats.call_args[1] if mock_stats.call_args[1] else mock_stats.call_args[0]


# ============================================================================
# Error Handling & Retry Tests
# ============================================================================

class TestErrorHandling:
    """Tests for job failure handling and retry logic."""

    @pytest.mark.asyncio
    async def test_failed_job_increments_fail_count(self, scheduler: EngineScheduler, sample_job):
        """Failed jobs increment fail_count in DB."""
        with patch.object(scheduler, "_execute_prompt_job", new_callable=AsyncMock) as mock_exec, \
             patch.object(scheduler, "_update_job_stats", new_callable=AsyncMock) as mock_stats:
            mock_exec.side_effect = Exception("LLM timeout")

            result = await scheduler._execute_job(sample_job)

            assert result["status"] == "error"
            assert "LLM timeout" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, scheduler: EngineScheduler):
        """Jobs with retry_count > 0 are retried on failure."""
        retry_job = {
            "id": "social_check",
            "payload_type": "skill",
            "payload": "social.check_mentions",
            "agent_id": "social",
            "max_duration_seconds": 120,
            "retry_count": 2,
        }

        with patch.object(scheduler, "_execute_skill_job", new_callable=AsyncMock) as mock_exec:
            # Fail twice, succeed on third
            mock_exec.side_effect = [
                Exception("Network error"),
                Exception("Timeout"),
                {"status": "success", "duration_ms": 300},
            ]

            result = await scheduler._execute_with_retry(retry_job)

            assert result["status"] == "success"
            assert mock_exec.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, scheduler: EngineScheduler):
        """Job fails permanently after retry_count exhausted."""
        retry_job = {
            "id": "failing_job",
            "payload_type": "prompt",
            "payload": "test",
            "agent_id": "main",
            "max_duration_seconds": 60,
            "retry_count": 1,
        }

        with patch.object(scheduler, "_execute_prompt_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = Exception("Persistent failure")

            result = await scheduler._execute_with_retry(retry_job)

            assert result["status"] == "error"
            assert mock_exec.call_count == 2  # 1 original + 1 retry


# ============================================================================
# Cron Expression Tests
# ============================================================================

class TestCronExpressions:
    """Tests for cron expression parsing and validation."""

    def test_valid_cron_expressions(self, scheduler: EngineScheduler):
        """Valid cron expressions are accepted."""
        valid = [
            "0 * * * *",       # every hour
            "*/15 * * * *",    # every 15 minutes
            "0 3 * * *",       # daily at 3am
            "0 0 * * 0",       # weekly on Sunday
            "0 0 1 * *",       # monthly
            "30 6 * * 1-5",    # weekdays at 6:30
        ]
        for expr in valid:
            assert scheduler._validate_cron(expr) is True, f"Should be valid: {expr}"

    def test_invalid_cron_expressions(self, scheduler: EngineScheduler):
        """Invalid cron expressions are rejected."""
        invalid = [
            "",                # empty
            "not a cron",      # text
            "60 * * * *",      # minute > 59
            "* * * *",         # only 4 fields
            "* * * * * *",     # 6 fields
        ]
        for expr in invalid:
            assert scheduler._validate_cron(expr) is False, f"Should be invalid: {expr}"


# ============================================================================
# Manual Trigger Tests
# ============================================================================

class TestManualTrigger:
    """Tests for manually triggering a cron job."""

    @pytest.mark.asyncio
    async def test_manual_trigger_executes_immediately(self, scheduler: EngineScheduler, sample_job):
        """Manual trigger executes the job immediately, regardless of schedule."""
        scheduler._jobs = {"heartbeat": sample_job}

        with patch.object(scheduler, "_execute_job", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"status": "success", "duration_ms": 100}

            result = await scheduler.trigger_job("heartbeat")

            assert result["status"] == "success"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_nonexistent_job_fails(self, scheduler: EngineScheduler):
        """Triggering a job that doesn't exist raises an error."""
        scheduler._jobs = {}

        with pytest.raises(KeyError):
            await scheduler.trigger_job("nonexistent")


# ============================================================================
# Time-Based Tests
# ============================================================================

class TestTimeBased:
    """Tests using freezegun for deterministic time."""

    @freeze_time("2026-02-18 14:00:00")
    def test_next_run_calculation(self, scheduler: EngineScheduler):
        """Verify next_run_at is calculated correctly from cron expression."""
        next_run = scheduler._calculate_next_run("0 * * * *")
        assert next_run is not None
        # Next hour from 14:00 should be 15:00
        assert next_run.hour == 15
        assert next_run.minute == 0

    @freeze_time("2026-02-18 02:55:00")
    def test_next_run_daily(self, scheduler: EngineScheduler):
        """Daily job at 3am should run in 5 minutes."""
        next_run = scheduler._calculate_next_run("0 3 * * *")
        assert next_run is not None
        assert next_run.hour == 3
        assert next_run.minute == 0

    def test_get_scheduler_status(self, scheduler: EngineScheduler, sample_jobs):
        """Scheduler status reports all registered jobs."""
        scheduler._jobs = {j["id"]: j for j in sample_jobs}
        scheduler._running = True

        status = scheduler.get_status()

        assert status["running"] is True
        assert status["total_jobs"] == 3
        assert status["enabled_jobs"] == 2  # memory_consolidation is disabled
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Scheduler tests verify engine layer |
| 2 | .env for secrets (zero in code) | ✅ | Test config uses dummy credentials |
| 3 | models.yaml single source of truth | ❌ | Scheduler doesn't touch models |
| 4 | Docker-first testing | ✅ | Tests run in Docker CI |
| 5 | aria_memories only writable path | ❌ | Tests only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S3-01 must complete first (EngineScheduler implementation exists)
- S10-01 should complete first (shared conftest fixtures)

## Verification
```bash
# 1. Run tests:
pytest tests/unit/test_scheduler.py -v
# EXPECTED: All tests pass

# 2. Coverage:
pytest tests/unit/test_scheduler.py --cov=aria_engine.scheduler --cov-report=term-missing
# EXPECTED: >85% coverage

# 3. Verify freezegun works:
python -c "from freezegun import freeze_time; print('OK')"
# EXPECTED: OK
```

## Prompt for Agent
```
Write comprehensive unit tests for aria_engine.scheduler.EngineScheduler.

FILES TO READ FIRST:
- aria_engine/scheduler.py (full file — implementation under test)
- aria_engine/config.py (EngineConfig)
- aria_mind/cron_jobs.yaml (original job definitions)
- tests/conftest.py (shared fixtures)

STEPS:
1. Read all files above
2. Create tests/unit/test_scheduler.py
3. Mock APScheduler, DB, and ChatEngine
4. Use freezegun for time-based tests
5. Run pytest and verify all tests pass

CONSTRAINTS:
- Mock APScheduler internals — never start a real scheduler
- Use freezegun for time-dependent tests
- Test all three payload types: prompt, skill, pipeline
- Test retry logic with exponential backoff
- Verify cron expression validation
```
