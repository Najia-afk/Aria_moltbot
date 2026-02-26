"""
Tests for the sprint_manager skill (Layer 4 — orchestration).

Covers:
- Initialization and health check
- Sprint status retrieval
- Sprint planning (assign goals)
- Sprint move goal (board column)
- Sprint report generation
- Sprint prioritize (reorder goals)
- Error paths
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.sprint_manager import SprintManagerSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> SprintManagerSkill:
    return SprintManagerSkill(SkillConfig(name="sprint_manager"))


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.post = AsyncMock(return_value=SkillResult.ok({}))
    api.get = AsyncMock(return_value=SkillResult.ok({}))
    api.patch = AsyncMock(return_value=SkillResult.ok({}))
    api.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    return api


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api):
    skill = _make_skill()
    with patch("aria_skills.api_client.get_api_client", new_callable=AsyncMock, return_value=mock_api):
        ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Sprint Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_status_current(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({
        "sprint": "Sprint 7",
        "total": 10, "done": 5, "in_progress": 3,
    }))

    result = await skill.sprint_status()
    assert result.success
    mock_api.get.assert_called_once()


@pytest.mark.asyncio
async def test_sprint_status_named(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({"sprint": "Sprint 6"}))

    result = await skill.sprint_status(sprint="Sprint 6")
    assert result.success


@pytest.mark.asyncio
async def test_sprint_status_api_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("API down"))

    result = await skill.sprint_status()
    assert not result.success
    assert "Failed to get sprint status" in result.error


# ---------------------------------------------------------------------------
# Sprint Plan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_plan_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(return_value=SkillResult.ok({}))

    result = await skill.sprint_plan(sprint_name="Sprint 7", goal_ids=["g1", "g2", "g3"])
    assert result.success
    assert result.data["sprint"] == "Sprint 7"
    assert len(result.data["assigned"]) == 3
    for item in result.data["assigned"]:
        assert item["success"] is True


@pytest.mark.asyncio
async def test_sprint_plan_partial_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    # First call succeeds, second fails
    mock_api.patch = AsyncMock(side_effect=[
        SkillResult.ok({}),
        Exception("Goal not found"),
    ])

    result = await skill.sprint_plan(sprint_name="Sprint 7", goal_ids=["g1", "g2"])
    assert result.success
    assigned = result.data["assigned"]
    assert assigned[0]["success"] is True
    assert assigned[1]["success"] is False


# ---------------------------------------------------------------------------
# Sprint Move Goal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_move_goal_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(return_value=SkillResult.ok({"board_column": "doing"}))

    result = await skill.sprint_move_goal(goal_id="g1", column="doing", position=0)
    assert result.success


@pytest.mark.asyncio
async def test_sprint_move_goal_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(side_effect=Exception("Not found"))

    result = await skill.sprint_move_goal(goal_id="bad_id", column="done")
    assert not result.success
    assert "Failed to move goal" in result.error


# ---------------------------------------------------------------------------
# Sprint Report
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_report_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({
        "columns": {
            "todo": ["g1", "g2"],
            "doing": ["g3"],
            "done": ["g4", "g5"],
            "on_hold": [],
        }
    }))

    result = await skill.sprint_report()
    assert result.success
    assert result.data["total_goals"] == 5
    assert result.data["done"] == 2
    assert result.data["in_progress"] == 1
    assert result.data["todo"] == 2
    assert result.data["completion_pct"] == 40.0
    assert result.data["velocity"] == "2/5"


@pytest.mark.asyncio
async def test_sprint_report_empty_board(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({"columns": {}}))

    result = await skill.sprint_report()
    assert result.success
    assert result.data["total_goals"] == 0
    assert result.data["completion_pct"] == 0
    assert result.data["velocity"] == "0/0"


# ---------------------------------------------------------------------------
# Sprint Prioritize
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_prioritize_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.patch = AsyncMock(return_value=SkillResult.ok({}))

    result = await skill.sprint_prioritize(column="todo", goal_ids_ordered=["g3", "g1", "g2"])
    assert result.success
    assert result.data["column"] == "todo"
    assert len(result.data["reordered"]) == 3
    # Verify positions are sequential
    for i, item in enumerate(result.data["reordered"]):
        assert item["position"] == i
        assert item["success"] is True


# ---------------------------------------------------------------------------
# Sprint Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_create_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(return_value=SkillResult.ok({"id": "s1", "name": "Sprint 8"}))

    result = await skill.sprint_create(sprint_name="Sprint 8")
    assert result.success
    assert result.data["name"] == "Sprint 8"
    mock_api.post.assert_called_once()


@pytest.mark.asyncio
async def test_sprint_create_with_dates_and_capacity(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(return_value=SkillResult.ok({
        "id": "s2", "name": "Sprint 9", "start_date": "2026-03-01",
        "end_date": "2026-03-14", "capacity": 20,
    }))

    result = await skill.sprint_create(
        sprint_name="Sprint 9",
        start_date="2026-03-01",
        end_date="2026-03-14",
        capacity=20,
    )
    assert result.success
    call_kwargs = mock_api.post.call_args
    payload = call_kwargs.kwargs.get("data", call_kwargs.args[1] if len(call_kwargs.args) > 1 else {})
    assert payload.get("start_date") == "2026-03-01"
    assert payload.get("end_date") == "2026-03-14"
    assert payload.get("capacity") == 20


@pytest.mark.asyncio
async def test_sprint_create_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.post = AsyncMock(side_effect=Exception("Duplicate sprint name"))

    result = await skill.sprint_create(sprint_name="Sprint 8")
    assert not result.success
    assert "Failed to create sprint" in result.error


# ---------------------------------------------------------------------------
# Sprint Review
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sprint_review_success(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({
        "columns": {
            "todo": ["g1"],
            "doing": ["g2"],
            "done": ["g3", "g4", "g5"],
            "on_hold": ["g6"],
        }
    }))

    result = await skill.sprint_review()
    assert result.success
    data = result.data
    assert data["summary"]["total_goals"] == 6
    assert data["summary"]["completed"] == 3
    assert data["summary"]["incomplete"] == 2
    assert data["summary"]["completion_pct"] == 50.0
    assert len(data["completed_goals"]) == 3
    assert len(data["carried_over"]) == 2
    assert len(data["blocked"]) == 1
    assert "retrospective" in data
    assert "went_well" in data["retrospective"]
    assert "needs_improvement" in data["retrospective"]
    assert len(data["retrospective"]["action_items"]) > 0


@pytest.mark.asyncio
async def test_sprint_review_all_done(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({
        "columns": {"done": ["g1", "g2", "g3"], "todo": [], "doing": [], "on_hold": []}
    }))

    result = await skill.sprint_review(sprint="Sprint 5")
    assert result.success
    data = result.data
    assert data["sprint"] == "Sprint 5"
    assert data["summary"]["completed"] == 3
    assert data["summary"]["incomplete"] == 0
    assert data["summary"]["completion_pct"] == 100.0
    assert data["retrospective"]["needs_improvement"] == "All goals completed"
    assert data["retrospective"]["action_items"] == ["Plan next sprint goals"]


@pytest.mark.asyncio
async def test_sprint_review_empty_board(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(return_value=SkillResult.ok({"columns": {}}))

    result = await skill.sprint_review()
    assert result.success
    data = result.data
    assert data["summary"]["total_goals"] == 0
    assert data["summary"]["completion_pct"] == 0
    assert data["retrospective"]["went_well"] == "No goals tracked this sprint"


@pytest.mark.asyncio
async def test_sprint_review_api_failure(mock_api):
    skill = _make_skill()
    skill._api = mock_api
    skill._status = SkillStatus.AVAILABLE
    mock_api.get = AsyncMock(side_effect=Exception("Board unavailable"))

    result = await skill.sprint_review()
    assert not result.success
    assert "Failed to get board for review" in result.error
