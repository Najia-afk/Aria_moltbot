"""
Tests for the social skill (Layer 3 — domain).

Covers:
- Initialization
- Post creation (default platform, disabled platform)
- Post listing
- Post publishing
- Post deletion
- Schedule intent
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.social import SocialSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(mock_api):
    skill = SocialSkill(SkillConfig(name="social"))
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api_client):
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_health_check(mock_api_client):
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
    status = await skill.health_check()
    assert status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_create_post_default_platform(mock_api_client):
    mock_api_client.post = AsyncMock(return_value=SkillResult.ok({
        "id": "post-1", "content": "Hello world", "platform": "moltbook",
    }))
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.create_post(content="Hello world", platform="moltbook")
    assert result.success


@pytest.mark.asyncio
async def test_create_post_disabled_platform(mock_api_client):
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.create_post(content="Test", platform="twitter")
    assert not result.success
    assert "disabled" in result.error.lower()


@pytest.mark.asyncio
async def test_create_post_disabled_x_platform(mock_api_client):
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.create_post(content="Test", platform="x")
    assert not result.success


@pytest.mark.asyncio
async def test_get_posts(mock_api_client):
    mock_api_client.get = AsyncMock(return_value=SkillResult.ok([
        {"id": "p1", "content": "Post 1"},
        {"id": "p2", "content": "Post 2"},
    ]))
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.get_posts(limit=10)
    assert result.success


@pytest.mark.asyncio
async def test_publish_post(mock_api_client):
    mock_api_client.put = AsyncMock(return_value=SkillResult.ok({"status": "published"}))
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.publish_post(post_id="post-1")
    assert result.success


@pytest.mark.asyncio
async def test_delete_post(mock_api_client):
    mock_api_client.delete = AsyncMock(return_value=SkillResult.ok({"deleted": True}))
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.delete_post(post_id="post-1")
    assert result.success


@pytest.mark.asyncio
async def test_social_schedule_valid(mock_api_client):
    mock_api_client.post = AsyncMock(return_value=SkillResult.ok({}))
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.social_schedule(
            content="Scheduled post",
            platform="moltbook",
            scheduled_for="2026-03-01T12:00:00+00:00",
            simulate=True,
        )
    assert result.success
    assert result.data["scheduled"] is True


@pytest.mark.asyncio
async def test_social_schedule_invalid_timestamp(mock_api_client):
    with patch("aria_skills.social.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = SocialSkill(SkillConfig(name="social"))
        await skill.initialize()
        result = await skill.social_schedule(
            content="Bad",
            platform="moltbook",
            scheduled_for="not-a-timestamp",
        )
    assert not result.success
