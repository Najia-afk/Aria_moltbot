"""
Tests for the performance skill (Layer 4 — orchestration).

Covers:
- Initialization and health check
- Log review creation (success + API fallback)
- Get reviews (with limit)
- Improvement summary aggregation
- Error paths
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.performance import PerformanceSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> PerformanceSkill:
    return PerformanceSkill(SkillConfig(name="performance"))


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.post = AsyncMock(return_value=SkillResult.ok({"id": "perf_1"}))
    api.get = AsyncMock(return_value=SkillResult.ok([]))
    api.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    return api


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api):
    skill = _make_skill()
    with patch("aria_skills.performance.get_api_client", new_callable=AsyncMock, return_value=mock_api):
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Log Review
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_log_review_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE

    result = await skill.log_review(
        period="2026-02-24",
        successes=["Deployed v3"],
        failures=["Slow query"],
        improvements=["Add caching"],
    )
    assert result.success
    mock_api.post.assert_called_once()


@pytest.mark.asyncio
async def test_log_review_api_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(side_effect=Exception("API down"))

    result = await skill.log_review(
        period="2026-02-24",
        successes=["OK"],
        failures=[],
        improvements=["Retry logic"],
    )
    assert result.success
    assert result.data["id"] == "perf_1"
    assert len(skill._logs) == 1


# ---------------------------------------------------------------------------
# Get Reviews
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_reviews_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([
        {"period": "2026-02-23", "successes": [], "failures": [], "improvements": []},
        {"period": "2026-02-24", "successes": ["v3"], "failures": [], "improvements": []},
    ]))

    result = await skill.get_reviews(limit=5)
    assert result.success
    assert result.data["total"] == 2


@pytest.mark.asyncio
async def test_get_reviews_api_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))
    skill._logs = [
        {"period": "2026-01-01", "successes": [], "failures": [], "improvements": []},
    ]

    result = await skill.get_reviews(limit=10)
    assert result.success
    assert result.data["total"] == 1
    assert len(result.data["reviews"]) == 1


# ---------------------------------------------------------------------------
# Improvement Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_improvement_summary(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([
        {"improvements": ["Add caching", "Better docs"]},
        {"improvements": ["Add caching", "Fix CI"]},
        {"improvements": ["Better docs"]},
    ]))

    result = await skill.get_improvement_summary()
    assert result.success
    assert result.data["total_reviews"] == 3
    top = result.data["top_improvements"]
    # "Add caching" appears 2x, "Better docs" 2x, "Fix CI" 1x
    assert len(top) >= 2
    top_items = [item[0] for item in top]
    assert "Add caching" in top_items
    assert "Better docs" in top_items


@pytest.mark.asyncio
async def test_get_improvement_summary_empty(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok([]))

    result = await skill.get_improvement_summary()
    assert result.success
    assert result.data["total_reviews"] == 0
    assert result.data["top_improvements"] == []


@pytest.mark.asyncio
async def test_get_improvement_summary_fallback(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))
    skill._logs = [
        {"improvements": ["Monitor latency"]},
    ]

    result = await skill.get_improvement_summary()
    assert result.success
    assert result.data["total_reviews"] == 1
