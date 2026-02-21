# S11-02: E2E Cron/Scheduler Execution
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 3 | **Phase:** 11

## Problem
The `EngineScheduler` replaces OpenClaw's cron system. We need end-to-end tests that verify cron jobs are loaded from YAML, registered with APScheduler, fire at correct times, invoke skill pipelines, and persist execution history — all through the real stack, not mocked.

## Root Cause
Scheduler bugs are the most insidious: they appear only at specific times, under specific conditions. Unit tests with mocked clocks catch logic errors but miss real timing issues, APScheduler threading bugs, and database commit race conditions. E2E tests with freezegun + real APScheduler catch these.

## Fix
### `tests/integration/test_e2e_cron.py`
```python
"""
E2E integration tests for the Cron/Scheduler system.

Tests the full pipeline:
  cron_jobs.yaml ─► EngineScheduler ─► APScheduler ─► Skill Execution
                                                            │
  DB (scheduler_jobs, scheduler_history) ◄──────────────────┘

Uses freezegun for time manipulation + real APScheduler + real DB.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time

# ---------------------------------------------------------------------------
# Test cron YAML (minimal)
# ---------------------------------------------------------------------------

MINI_CRON_YAML = """
jobs:
  - id: test_heartbeat
    name: "Test Heartbeat"
    schedule: "*/5 * * * *"
    skill: health
    method: heartbeat
    enabled: true
    priority: high

  - id: test_memory_sweep
    name: "Test Memory Sweep"
    schedule: "0 * * * *"
    skill: memory_compression
    method: compress
    enabled: true
    priority: medium

  - id: test_disabled_job
    name: "Disabled Job"
    schedule: "* * * * *"
    skill: health
    method: check
    enabled: false
    priority: low

  - id: test_daily_report
    name: "Daily Report"
    schedule: "0 9 * * *"
    skill: goals
    method: daily_summary
    enabled: true
    priority: high
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cron_yaml(tmp_path):
    """Write a test cron YAML file."""
    yaml_path = tmp_path / "test_cron_jobs.yaml"
    yaml_path.write_text(MINI_CRON_YAML)
    return yaml_path


@pytest.fixture
async def scheduler(cron_yaml):
    """Create and start a test scheduler."""
    from aria_engine.scheduler import EngineScheduler

    sched = EngineScheduler(cron_path=str(cron_yaml))
    await sched.start()
    yield sched
    await sched.shutdown()


@pytest.fixture
def mock_skill_registry():
    """Mock the skill registry to capture executions."""
    executions: list[dict] = []

    async def fake_execute(skill_name: str, method: str, **kwargs):
        record = {
            "skill": skill_name,
            "method": method,
            "kwargs": kwargs,
            "timestamp": datetime.now(timezone.utc),
        }
        executions.append(record)
        return {"status": "ok", "skill": skill_name}

    mock = AsyncMock(side_effect=fake_execute)
    mock._executions = executions
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestE2ECronExecution:
    """End-to-end cron/scheduler tests."""

    @pytest.mark.integration
    async def test_jobs_loaded_from_yaml(self, scheduler):
        """All enabled jobs from YAML are registered."""
        jobs = await scheduler.list_jobs()
        job_ids = {j["id"] for j in jobs}

        assert "test_heartbeat" in job_ids
        assert "test_memory_sweep" in job_ids
        assert "test_daily_report" in job_ids
        assert "test_disabled_job" not in job_ids  # disabled

    @pytest.mark.integration
    async def test_disabled_jobs_not_registered(self, scheduler):
        """Disabled jobs are not scheduled."""
        jobs = await scheduler.list_jobs()
        job_ids = {j["id"] for j in jobs}
        assert "test_disabled_job" not in job_ids

    @pytest.mark.integration
    async def test_heartbeat_fires_every_5_minutes(self, scheduler, mock_skill_registry):
        """Heartbeat job fires every 5 minutes."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            # Simulate 15 minutes passing
            for minute in range(0, 16, 5):
                with freeze_time(
                    datetime(2026, 3, 1, 12, minute, 0, tzinfo=timezone.utc)
                ):
                    await scheduler._check_and_fire("test_heartbeat")

            heartbeat_calls = [
                e for e in mock_skill_registry._executions
                if e["skill"] == "health" and e["method"] == "heartbeat"
            ]
            # Should fire at :00, :05, :10, :15 = up to 4 times
            assert len(heartbeat_calls) >= 3

    @pytest.mark.integration
    async def test_hourly_job_fires_correctly(self, scheduler, mock_skill_registry):
        """Hourly job fires at the top of each hour."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            # At minute 0 — should fire
            with freeze_time(datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_memory_sweep")

            # At minute 30 — should NOT fire
            with freeze_time(datetime(2026, 3, 1, 14, 30, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_memory_sweep")

            sweep_calls = [
                e for e in mock_skill_registry._executions
                if e["skill"] == "memory_compression"
            ]
            assert len(sweep_calls) == 1

    @pytest.mark.integration
    async def test_daily_job_fires_at_nine(self, scheduler, mock_skill_registry):
        """Daily report fires at 09:00 only."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            # 09:00 — should fire
            with freeze_time(datetime(2026, 3, 1, 9, 0, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_daily_report")

            # 15:00 — should NOT fire
            with freeze_time(datetime(2026, 3, 1, 15, 0, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_daily_report")

            report_calls = [
                e for e in mock_skill_registry._executions
                if e["skill"] == "goals"
            ]
            assert len(report_calls) == 1

    @pytest.mark.integration
    async def test_execution_history_persisted(self, scheduler, mock_skill_registry):
        """Execution results are stored in the database."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            with freeze_time(datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_heartbeat")

        # Check history in database
        history = await scheduler.get_history("test_heartbeat", limit=10)
        assert len(history) >= 1

        last_run = history[0]
        assert last_run["job_id"] == "test_heartbeat"
        assert last_run["status"] == "success"
        assert "duration_ms" in last_run

    @pytest.mark.integration
    async def test_failed_job_recorded(self, scheduler):
        """Failed job execution is recorded in history."""
        async def failing_skill(*args, **kwargs):
            raise RuntimeError("Skill crashed!")

        with patch.object(scheduler, "_execute_skill", AsyncMock(side_effect=failing_skill)):
            with freeze_time(datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)):
                # Should not raise — scheduler catches errors
                await scheduler._check_and_fire("test_heartbeat")

        history = await scheduler.get_history("test_heartbeat", limit=10)
        failed = [h for h in history if h["status"] == "error"]
        assert len(failed) >= 1
        assert "crashed" in failed[0].get("error", "").lower()

    @pytest.mark.integration
    async def test_manual_trigger(self, scheduler, mock_skill_registry):
        """Jobs can be triggered manually outside their schedule."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            result = await scheduler.trigger("test_heartbeat")

        assert result["status"] == "ok"
        assert len(mock_skill_registry._executions) == 1

    @pytest.mark.integration
    async def test_pause_and_resume_job(self, scheduler, mock_skill_registry):
        """Paused jobs don't fire; resumed jobs do."""
        await scheduler.pause("test_heartbeat")

        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            with freeze_time(datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_heartbeat")

        assert len(mock_skill_registry._executions) == 0

        # Resume
        await scheduler.resume("test_heartbeat")

        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            with freeze_time(datetime(2026, 3, 1, 12, 5, 0, tzinfo=timezone.utc)):
                await scheduler._check_and_fire("test_heartbeat")

        assert len(mock_skill_registry._executions) == 1

    @pytest.mark.integration
    async def test_concurrent_job_execution(self, scheduler, mock_skill_registry):
        """Multiple jobs firing simultaneously don't interfere."""
        with patch.object(scheduler, "_execute_skill", mock_skill_registry):
            # Both heartbeat and memory_sweep fire at :00
            with freeze_time(datetime(2026, 3, 1, 13, 0, 0, tzinfo=timezone.utc)):
                await asyncio.gather(
                    scheduler._check_and_fire("test_heartbeat"),
                    scheduler._check_and_fire("test_memory_sweep"),
                )

        skills_called = {e["skill"] for e in mock_skill_registry._executions}
        assert "health" in skills_called
        assert "memory_compression" in skills_called

    @pytest.mark.integration
    async def test_scheduler_restart_recovers_jobs(self, cron_yaml):
        """Scheduler restart reloads all jobs from YAML."""
        from aria_engine.scheduler import EngineScheduler

        sched1 = EngineScheduler(cron_path=str(cron_yaml))
        await sched1.start()
        jobs_before = await sched1.list_jobs()
        await sched1.shutdown()

        # New instance
        sched2 = EngineScheduler(cron_path=str(cron_yaml))
        await sched2.start()
        jobs_after = await sched2.list_jobs()
        await sched2.shutdown()

        assert {j["id"] for j in jobs_before} == {j["id"] for j in jobs_after}

    @pytest.mark.integration
    async def test_next_run_time_calculation(self, scheduler):
        """Next run time is correctly calculated for each job."""
        with freeze_time(datetime(2026, 3, 1, 12, 3, 0, tzinfo=timezone.utc)):
            jobs = await scheduler.list_jobs()

            heartbeat = next(j for j in jobs if j["id"] == "test_heartbeat")
            # Next run should be at 12:05
            next_run = datetime.fromisoformat(heartbeat["next_run"])
            assert next_run.minute == 5
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Tests scheduler → skill pipeline |
| 2 | .env for secrets | ✅ | TEST_DATABASE_URL |
| 3 | models.yaml single source | ❌ | No LLM calls |
| 4 | Docker-first testing | ✅ | Requires PostgreSQL |
| 5 | aria_memories only writable path | ❌ | DB writes only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S10-03 (unit tests for scheduler) must pass
- `pip install freezegun apscheduler`
- Test PostgreSQL instance

## Verification
```bash
# 1. Run cron E2E tests:
TEST_DATABASE_URL=postgresql://aria:aria_test@localhost:5432/aria_test pytest tests/integration/test_e2e_cron.py -v --timeout=60

# 2. Check freezegun integrates properly:
pytest tests/integration/test_e2e_cron.py::TestE2ECronExecution::test_heartbeat_fires_every_5_minutes -v -s

# 3. Verify history persistence:
pytest tests/integration/test_e2e_cron.py::TestE2ECronExecution::test_execution_history_persisted -v
```

## Prompt for Agent
```
Create end-to-end integration tests for the cron/scheduler system.

FILES TO READ FIRST:
- aria_engine/scheduler.py (EngineScheduler class)
- aria_mind/cron_jobs.yaml (production cron config)
- tests/unit/test_scheduler.py (unit tests to complement)
- tests/integration/conftest.py (DB fixtures)

STEPS:
1. Create tests/integration/test_e2e_cron.py
2. Write a mini YAML config for test jobs
3. Test: loading, timing, history, failures, pause/resume, concurrent
4. Use freezegun for deterministic time testing
5. Use real APScheduler + real database

CONSTRAINTS:
- Mock the skill execution, but NOT the scheduler or database
- Test at least 10 scenarios (load, disable, fire, fail, manual, pause, resume, concurrent, restart, next_run)
- Each test must clean up (scheduler.shutdown())
```
