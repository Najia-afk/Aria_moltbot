"""
Tests for the moltbook skill (Layer 3 — domain).

Covers:
- Initialization and health check
- Post creation (success, empty content, rate limiting)
- Feed retrieval
- Comment creation
- Post deletion
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill():
    from aria_skills.moltbook import MoltbookSkill
    return MoltbookSkill(SkillConfig(name="moltbook", config={
        "api_key": "test-token-123",
        "api_url": "https://www.moltbook.com/api/v1",
    }))


def _mock_httpx_client():
    """Return a mocked httpx.AsyncClient."""
    client = AsyncMock()
    return client


def _response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    with patch("aria_skills.moltbook.HAS_HTTPX", True):
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_health_check_no_client():
    skill = _make_skill()
    skill._client = None
    status = await skill.health_check()
    assert status == SkillStatus.ERROR


@pytest.mark.asyncio
async def test_health_check_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_response(200))
    status = await skill.health_check()
    assert status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_create_post_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_response(200, {"id": "post-1"}))
    skill._local_client = AsyncMock()
    skill._local_client.post = AsyncMock(return_value=_response(200))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.create_post(content="Hello Moltbook!", submolt="general")
    assert result.success
    assert result.data["id"] == "post-1"


@pytest.mark.asyncio
async def test_create_post_empty_content():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._status = SkillStatus.AVAILABLE

    result = await skill.create_post(content="")
    assert not result.success


@pytest.mark.asyncio
async def test_create_post_no_client():
    skill = _make_skill()
    skill._client = None
    result = await skill.create_post(content="Test")
    assert not result.success
    assert "not initialized" in result.error.lower()


@pytest.mark.asyncio
async def test_create_post_rate_limited():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_response(
        429, {"retry_after_minutes": 5}
    ))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.create_post(content="Test post")
    assert not result.success
    assert "rate limited" in result.error.lower()


@pytest.mark.asyncio
async def test_get_feed_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_response(200, [{"id": "p1"}]))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.get_feed(sort="hot", limit=10)
    assert result.success


@pytest.mark.asyncio
async def test_get_feed_no_client():
    skill = _make_skill()
    skill._client = None
    result = await skill.get_feed()
    assert not result.success


@pytest.mark.asyncio
async def test_add_comment_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_response(200, {"id": "c1"}))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.add_comment(post_id="p1", content="Great post!")
    assert result.success


@pytest.mark.asyncio
async def test_delete_post_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.delete = AsyncMock(return_value=_response(200, {"deleted": True}))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.delete_post(post_id="p1")
    assert result.success


@pytest.mark.asyncio
async def test_posting_guard_blocks_sub_agents():
    skill = _make_skill()
    # Test the internal guard directly (agent_role != main)
    guard = skill._check_posting_allowed(agent_role="sub-agent-x")
    assert guard is not None
    assert not guard.success
