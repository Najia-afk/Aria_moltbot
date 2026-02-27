"""
Tests for the schedule skill (Layer 4 — orchestration).

Covers:
- Initialization and health check
- Job CRUD (create, get, list, delete)
- Due job detection
- Enable / disable jobs
- Mark job run
- API fallback paths
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.schedule import ScheduleSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> ScheduleSkill:
    return ScheduleSkill(SkillConfig(name="schedule"))


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.post = AsyncMock(return_value=SkillResult.ok({"id": "job_1", "name": "test_job"}))
    api.get = AsyncMock(return_value=SkillResult.ok([]))
    api.put = AsyncMock(return_value=SkillResult.ok({}))
    api.delete = AsyncMock(return_value=SkillResult.ok({}))
    api.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    return api


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api):
    skill = _make_skill()
    with patch("aria_skills.schedule.get_api_client", new_callable=AsyncMock, return_value=mock_api):
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Create Job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_job_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE

    result = await skill.create_job(
        name="hourly_check",
        schedule="every 1 hours",
        action="health_check",
    )
    assert result.success
    mock_api.post.assert_called_once()


@pytest.mark.asyncio
async def test_create_job_accepts_type_alias(mock_api):
    """S-41: create_job must accept 'type' kwarg as an alias for 'action'."""
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(return_value=SkillResult.ok({
        "id": "job_1", "name": "demo", "action": "heartbeat"
    }))

    result = await skill.create_job(
        name="demo",
        schedule="*/15 * * * *",
        type="heartbeat",
    )
    assert result.success
    assert result.data.get("action") == "heartbeat"


@pytest.mark.asyncio
async def test_create_job_missing_action_and_type(mock_api):
    """S-41: create_job without action or type must fail gracefully."""
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE

    result = await skill.create_job(
        name="demo",
        schedule="*/15 * * * *",
    )
    assert not result.success
    assert "required" in result.error.lower()


@pytest.mark.asyncio
async def test_create_job_api_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(side_effect=Exception("API down"))

    result = await skill.create_job(
        name="fallback_job",
        schedule="every 30 minutes",
        action="do_thing",
        params={"key": "value"},
    )
    assert result.success
    assert result.data["name"] == "fallback_job"
    assert result.data["enabled"] is True
    assert len(skill._jobs) == 1


# ---------------------------------------------------------------------------
# Get Job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({"id": "job_1", "name": "my_job"}))

    result = await skill.get_job(job_id="job_1")
    assert result.success
    assert result.data["id"] == "job_1"


@pytest.mark.asyncio
async def test_get_job_not_found_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))

    result = await skill.get_job(job_id="nonexistent")
    assert not result.success
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# List Jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_jobs(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([
        {"id": "j1", "enabled": True},
        {"id": "j2", "enabled": False},
    ]))

    result = await skill.list_jobs()
    assert result.success
    assert result.data["total"] == 2
    assert result.data["enabled"] == 1


@pytest.mark.asyncio
async def test_list_jobs_enabled_only_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))
    skill._jobs = {
        "j1": {"id": "j1", "enabled": True, "name": "a"},
        "j2": {"id": "j2", "enabled": False, "name": "b"},
    }

    result = await skill.list_jobs(enabled_only=True)
    assert result.success
    assert result.data["total"] == 1


# ---------------------------------------------------------------------------
# Enable / Disable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enable_job_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.put = AsyncMock(side_effect=Exception("API down"))
    skill._jobs["job_1"] = {"id": "job_1", "enabled": False, "schedule": "every 1 hours", "next_run": None}

    result = await skill.enable_job(job_id="job_1")
    assert result.success
    assert skill._jobs["job_1"]["enabled"] is True
    assert skill._jobs["job_1"]["next_run"] is not None


@pytest.mark.asyncio
async def test_disable_job_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.put = AsyncMock(side_effect=Exception("API down"))
    skill._jobs["job_1"] = {"id": "job_1", "enabled": True, "schedule": "every 1 hours", "next_run": "2026-01-01T00:00:00"}

    result = await skill.disable_job(job_id="job_1")
    assert result.success
    assert skill._jobs["job_1"]["enabled"] is False
    assert skill._jobs["job_1"]["next_run"] is None


# ---------------------------------------------------------------------------
# Due Jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_due_jobs_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([{"id": "j1", "name": "due_job"}]))

    result = await skill.get_due_jobs()
    assert result.success
    assert result.data["count"] == 1


@pytest.mark.asyncio
async def test_get_due_jobs_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))
    # Create a job whose next_run is in the past
    skill._jobs["j1"] = {
        "id": "j1", "enabled": True,
        "next_run": "2020-01-01T00:00:00+00:00",
    }

    result = await skill.get_due_jobs()
    assert result.success
    assert result.data["count"] == 1


# ---------------------------------------------------------------------------
# Delete Job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_job_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.delete = AsyncMock(side_effect=Exception("API down"))
    skill._jobs["job_1"] = {"id": "job_1", "name": "deleteme"}

    result = await skill.delete_job(job_id="job_1")
    assert result.success
    assert "job_1" not in skill._jobs


# ---------------------------------------------------------------------------
# Mark Job Run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_job_run_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.put = AsyncMock(side_effect=Exception("API down"))
    skill._jobs["job_1"] = {
        "id": "job_1", "schedule": "every 1 hours",
        "run_count": 0, "last_run": None, "next_run": None,
    }

    result = await skill.mark_job_run(job_id="job_1", success=True)
    assert result.success
    assert result.data["run_count"] == 1
    assert result.data["last_success"] is True
