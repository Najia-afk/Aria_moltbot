"""
Tests for the working_memory skill (Layer 2).

Covers:
- remember / recall / checkpoint / forget operations
- get_context (weighted retrieval)
- reflect (summary generation)
- Skill unavailable guard
- update and restore_checkpoint
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from aria_skills.working_memory import WorkingMemorySkill
from aria_skills.base import SkillConfig, SkillResult, SkillStatus


@pytest.fixture
def wm_skill(mock_api_client):
    """Return a WorkingMemorySkill wired to the mock_api_client."""
    cfg = SkillConfig(name="working_memory", config={})
    skill = WorkingMemorySkill(cfg)
    skill._api = mock_api_client
    skill._status = SkillStatus.AVAILABLE
    return skill


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_success(mock_api_client):
    """Skill initializes when API client is reachable."""
    mock_api_client.health_check = AsyncMock(return_value=SkillStatus.AVAILABLE)
    cfg = SkillConfig(name="working_memory", config={})
    skill = WorkingMemorySkill(cfg)
    with patch("aria_skills.working_memory.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_initialize_failure():
    """Skill reports UNAVAILABLE when API client fails."""
    cfg = SkillConfig(name="working_memory", config={})
    skill = WorkingMemorySkill(cfg)
    with patch("aria_skills.working_memory.get_api_client", new_callable=AsyncMock, side_effect=Exception("no api")):
        ok = await skill.initialize()
    assert ok is False
    assert skill._status == SkillStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# remember
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remember(wm_skill, mock_api_client):
    """remember stores a key-value item via POST."""
    mock_api_client.post = AsyncMock(return_value=SkillResult.ok({"id": "mem-1", "key": "foo"}))
    result = await wm_skill.remember(key="foo", value="bar", category="test")
    assert result.success is True
    mock_api_client.post.assert_called_once()
    call_args = mock_api_client.post.call_args
    assert call_args[0][0] == "/working-memory"
    assert call_args[1]["data"]["key"] == "foo"


@pytest.mark.asyncio
async def test_remember_not_initialized():
    """remember fails when skill is not initialized."""
    cfg = SkillConfig(name="working_memory", config={})
    skill = WorkingMemorySkill(cfg)
    result = await skill.remember(key="x", value="y")
    assert result.success is False
    assert "not initialized" in result.error.lower()


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recall_by_key(wm_skill, mock_api_client):
    """recall retrieves items filtered by key."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": [{"key": "foo", "value": "bar"}]}))
    result = await wm_skill.recall(key="foo")
    assert result.success is True
    mock_api_client.get.assert_called_once()
    call_args = mock_api_client.get.call_args
    assert call_args[1]["params"]["key"] == "foo"


@pytest.mark.asyncio
async def test_recall_by_category(wm_skill, mock_api_client):
    """recall filters by category when provided."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": []}))
    result = await wm_skill.recall(category="goals")
    assert result.success is True
    call_args = mock_api_client.get.call_args
    assert call_args[1]["params"]["category"] == "goals"


# ---------------------------------------------------------------------------
# get_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_context(wm_skill, mock_api_client):
    """get_context performs weighted retrieval via /working-memory/context."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": [], "total": 0}))
    result = await wm_skill.get_context(limit=10)
    assert result.success is True
    call_args = mock_api_client.get.call_args
    assert "/working-memory/context" in call_args[0][0]


# ---------------------------------------------------------------------------
# checkpoint / restore_checkpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkpoint(wm_skill, mock_api_client):
    """checkpoint creates a snapshot via POST."""
    mock_api_client.post = AsyncMock(return_value=SkillResult.ok({"checkpoint_id": "cp-1"}))
    result = await wm_skill.checkpoint()
    assert result.success is True
    call_args = mock_api_client.post.call_args
    assert "/working-memory/checkpoint" in call_args[0][0]


@pytest.mark.asyncio
async def test_restore_checkpoint(wm_skill, mock_api_client):
    """restore_checkpoint fetches the latest snapshot via GET."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": [{"key": "a"}]}))
    result = await wm_skill.restore_checkpoint()
    assert result.success is True
    call_args = mock_api_client.get.call_args
    assert "/working-memory/checkpoint" in call_args[0][0]


# ---------------------------------------------------------------------------
# forget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_forget(wm_skill, mock_api_client):
    """forget deletes an item by UUID via DELETE."""
    mock_api_client.delete = AsyncMock(return_value=SkillResult.ok({"deleted": True}))
    result = await wm_skill.forget(item_id="uuid-123")
    assert result.success is True
    call_args = mock_api_client.delete.call_args
    assert "uuid-123" in call_args[0][0]


@pytest.mark.asyncio
async def test_forget_not_initialized():
    """forget fails when skill is not initialized."""
    cfg = SkillConfig(name="working_memory", config={})
    skill = WorkingMemorySkill(cfg)
    result = await skill.forget(item_id="x")
    assert result.success is False


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update(wm_skill, mock_api_client):
    """update patches an item by UUID."""
    mock_api_client.patch = AsyncMock(return_value=SkillResult.ok({"updated": True}))
    result = await wm_skill.update(item_id="uuid-456", importance=0.9)
    assert result.success is True


# ---------------------------------------------------------------------------
# reflect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reflect_empty(wm_skill, mock_api_client):
    """reflect reports empty memory when no items exist."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": []}))
    result = await wm_skill.reflect()
    assert result.success is True
    assert result.data["count"] == 0
    assert "empty" in result.data["summary"].lower()


@pytest.mark.asyncio
async def test_reflect_with_items(wm_skill, mock_api_client):
    """reflect builds a summary grouped by category."""
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok({
        "items": [
            {"key": "goal_1", "category": "goals", "importance": 0.8},
            {"key": "fact_1", "category": "facts", "importance": 0.5},
        ],
    }))
    result = await wm_skill.reflect()
    assert result.success is True
    assert result.data["count"] == 2
    assert "goals" in result.data["summary"].lower()
    assert "facts" in result.data["summary"].lower()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close(wm_skill):
    """close clears the API ref and sets UNAVAILABLE."""
    await wm_skill.close()
    assert wm_skill._api is None
    assert wm_skill._status == SkillStatus.UNAVAILABLE
