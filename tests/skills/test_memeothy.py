"""
Tests for the memeothy skill (Layer 3 — domain / Church of Molt).

Covers:
- Initialization (with and without API key)
- Proof-of-work computation
- Join / initiation (mocked httpx)
- Prophecy submission
- Canon retrieval
- Prophets listing
- Gallery browsing
- Status endpoint
- Error handling when httpx unavailable
"""
from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.memeothy import MemeothySkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(api_key: str = "", base_url: str = "https://molt.church") -> MemeothySkill:
    return MemeothySkill(SkillConfig(name="memeothy", config={
        "base_url": base_url,
        "api_key": api_key,
        "agent_name": "TestBot",
    }))


def _mock_response(data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = data
    return resp


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_no_key():
    skill = _make_skill()
    with patch.object(skill, "_load_credential_key", return_value=""):
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE
    assert skill._api_key == ""


@pytest.mark.asyncio
async def test_initialize_with_key():
    skill = _make_skill(api_key="test-key-123")
    with patch.object(skill, "_load_credential_key", return_value=""):
        ok = await skill.initialize()
    assert ok is True
    assert skill._api_key == "test-key-123"
    # Auth client should be created
    assert skill._auth_client is not None


# ---------------------------------------------------------------------------
# Tests — Proof-of-work
# ---------------------------------------------------------------------------

def test_compute_proof():
    proof = MemeothySkill._compute_proof("TestBot")
    assert isinstance(proof, str)
    assert len(proof) == 8
    # Same agent + same day → same proof (deterministic)
    assert proof == MemeothySkill._compute_proof("TestBot")


def test_compute_proof_different_agents():
    p1 = MemeothySkill._compute_proof("Agent1")
    p2 = MemeothySkill._compute_proof("Agent2")
    assert p1 != p2


# ---------------------------------------------------------------------------
# Tests — Join
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_join_success():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(
        {"api_key": "new-key-456", "message": "Welcome"}, 201
    ))
    with patch.object(skill, "_save_credentials"), \
         patch.object(skill, "_log_usage"):
        result = await skill.join(prophecy="The molt reveals all")
    assert result.success
    assert result.data["api_key"] == "new-key-456"
    assert skill._api_key == "new-key-456"


@pytest.mark.asyncio
async def test_join_failure():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(
        {"error": "proof invalid"}, 403
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.join()
    assert not result.success


@pytest.mark.asyncio
async def test_join_no_client():
    skill = _make_skill()
    await skill.initialize()
    skill._client = None
    result = await skill.join()
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Prophecy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_prophecy():
    skill = _make_skill(api_key="key")
    await skill.initialize()
    skill._auth_client = AsyncMock()
    skill._auth_client.post = AsyncMock(return_value=_mock_response(
        {"id": 1, "status": "accepted"}, 201
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.submit_prophecy(content="Sacred words", scripture_type="verse")
    assert result.success
    assert result.data["scripture_type"] == "verse"


@pytest.mark.asyncio
async def test_submit_prophecy_no_auth():
    skill = _make_skill()
    await skill.initialize()
    skill._api_key = ""
    result = await skill.submit_prophecy(content="test")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Canon
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_canon():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response(
        {"verses": [{"id": 1, "content": "First verse"}]}, 200
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.get_canon(limit=10)
    assert result.success
    assert result.data["count"] == 1


@pytest.mark.asyncio
async def test_get_canon_no_client():
    skill = _make_skill()
    await skill.initialize()
    skill._client = None
    result = await skill.get_canon()
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Prophets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_prophets():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response(
        {"prophets": [{"id": 1, "name": "Memeothy"}]}, 200
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.get_prophets()
    assert result.success
    assert result.data["count"] == 1


# ---------------------------------------------------------------------------
# Tests — Gallery
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_gallery():
    skill = _make_skill()
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response(
        {"gallery": [{"id": 1, "title": "Sacred Lobster"}]}, 200
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.get_gallery(limit=5)
    assert result.success
    assert result.data["count"] == 1


# ---------------------------------------------------------------------------
# Tests — Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status():
    skill = _make_skill(api_key="key")
    await skill.initialize()
    skill._client = AsyncMock()
    skill._client.get = AsyncMock(return_value=_mock_response(
        [{"id": 1, "name": "Memeothy"}], 200
    ))
    with patch.object(skill, "_log_usage"):
        result = await skill.status()
    assert result.success
    assert result.data["authenticated"] is True
    assert result.data["agent_name"] == "TestBot"
