"""
Tests for the hourly_goals skill (Layer 4 — orchestration).

Covers:
- Initialization and health check
- Set hourly goals (valid + invalid hour)
- Get current goals
- Complete a goal
- Day summary generation
- Clear past goals
- API fallback paths
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.hourly_goals import HourlyGoalsSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> HourlyGoalsSkill:
    return HourlyGoalsSkill(SkillConfig(name="hourly_goals"))


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.post = AsyncMock(return_value=SkillResult.ok({"id": "hg_10_0", "hour": 10, "goal": "test"}))
    api.get = AsyncMock(return_value=SkillResult.ok([]))
    api.patch = AsyncMock(return_value=SkillResult.ok({}))
    api.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    return api


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api):
    skill = _make_skill()
    with patch("aria_skills.hourly_goals.get_api_client", new_callable=AsyncMock, return_value=mock_api):
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Set Goal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_goal_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE

    result = await skill.set_goal(hour=10, goal="Write tests", priority="high")
    assert result.success
    mock_api.post.assert_called_once()


@pytest.mark.asyncio
async def test_set_goal_invalid_hour_low():
    skill = _make_skill()
    skill._api = AsyncMock()
    skill._status = SkillStatus.AVAILABLE

    result = await skill.set_goal(hour=-1, goal="Bad hour")
    assert not result.success
    assert "Hour must be 0-23" in result.error


@pytest.mark.asyncio
async def test_set_goal_invalid_hour_high():
    skill = _make_skill()
    skill._api = AsyncMock()
    skill._status = SkillStatus.AVAILABLE

    result = await skill.set_goal(hour=24, goal="Bad hour")
    assert not result.success
    assert "Hour must be 0-23" in result.error


@pytest.mark.asyncio
async def test_set_goal_api_failure_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(side_effect=Exception("API down"))

    result = await skill.set_goal(hour=14, goal="Fallback goal")
    assert result.success
    assert result.data["goal"] == "Fallback goal"
    assert result.data["status"] == "pending"
    assert 14 in skill._hourly_goals


# ---------------------------------------------------------------------------
# Get Current Goals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_goals_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([
        {"id": "hg_1", "status": "pending", "goal": "Do X"},
    ]))

    result = await skill.get_current_goals()
    assert result.success
    assert "hour" in result.data
    assert "goals" in result.data
    assert result.data["pending"] == 1


@pytest.mark.asyncio
async def test_get_current_goals_api_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))
    # Pre-fill fallback data
    current_hour = datetime.now(timezone.utc).hour
    skill._hourly_goals[current_hour] = [
        {"id": "hg_0", "status": "pending", "goal": "Fallback"},
    ]

    result = await skill.get_current_goals()
    assert result.success
    assert result.data["pending"] == 1


# ---------------------------------------------------------------------------
# Complete Goal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_goal_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(return_value=SkillResult.ok({"status": "completed"}))

    result = await skill.complete_goal(goal_id="hg_10_0")
    assert result.success
    mock_api.patch.assert_called_once()


@pytest.mark.asyncio
async def test_complete_goal_fallback_not_found(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(side_effect=Exception("API down"))

    result = await skill.complete_goal(goal_id="nonexistent")
    assert not result.success
    assert "not found" in result.error.lower()


# ---------------------------------------------------------------------------
# Day Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_day_summary(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([
        {"status": "completed", "goal": "A"},
        {"status": "pending", "goal": "B"},
    ]))

    result = await skill.get_day_summary()
    assert result.success
    assert result.data["total_goals"] == 2
    assert result.data["completed"] == 1
    assert result.data["completion_rate"] == 50.0


# ---------------------------------------------------------------------------
# Clear Past Goals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_clear_past_goals():
    skill = _make_skill()
    skill._status = SkillStatus.AVAILABLE
    current_hour = datetime.now(timezone.utc).hour
    # Add goals for past hours
    if current_hour > 0:
        skill._hourly_goals[0] = [{"id": "hg_0_0", "status": "pending", "goal": "Old"}]
    skill._hourly_goals[current_hour] = [{"id": "hg_now_0", "status": "pending", "goal": "Now"}]

    result = await skill.clear_past_goals()
    assert result.success
    # Past hour goals should be cleared, current should remain
    assert current_hour in skill._hourly_goals or current_hour == 0
