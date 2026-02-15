# tests/test_session_manager.py
"""Tests for the session_manager skill."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from aria_skills.base import SkillConfig, SkillResult
from aria_skills.session_manager import SessionManagerSkill, _parse_sessions_from_api


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def empty_config():
    """SkillConfig with an empty config dict."""
    return SkillConfig(name="session_manager", config={})


@pytest.fixture
def custom_config():
    """SkillConfig with custom values."""
    return SkillConfig(
        name="session_manager",
        config={
            "stale_threshold_minutes": 120,
            "openclaw_gateway_url": "http://testhost:9999",
        },
    )


@pytest.fixture
def skill(empty_config):
    return SessionManagerSkill(empty_config)


@pytest.fixture
def custom_skill(custom_config):
    return SessionManagerSkill(custom_config)


# ── Init / config defaults ────────────────────────────────────────────


class TestInit:
    def test_init_empty_config(self, empty_config):
        s = SessionManagerSkill(empty_config)
        assert s._stale_threshold_minutes == 60
        assert s._gateway_url.endswith("/api")
        assert s._client is not None

    def test_init_custom_config(self, custom_config):
        s = SessionManagerSkill(custom_config)
        assert s._stale_threshold_minutes == 120
        assert s._gateway_url == "http://testhost:9999"

    def test_name_property(self, skill):
        assert skill.name == "session_manager"


# ── _parse_sessions_from_api ──────────────────────────────────────────


class TestParseSessionsFromApi:
    def test_empty_string(self):
        assert _parse_sessions_from_api("") == []

    def test_json_list(self):
        data = [{"id": "a"}, {"id": "b"}]
        assert _parse_sessions_from_api(json.dumps(data)) == data

    def test_json_dict_with_sessions_key(self):
        data = {"sessions": [{"id": "x"}]}
        assert _parse_sessions_from_api(json.dumps(data)) == [{"id": "x"}]

    def test_fallback_line_parse(self):
        raw = "abc123  my-agent  running\ndef456  other-agent  idle"
        result = _parse_sessions_from_api(raw)
        assert len(result) == 2
        assert result[0]["id"] == "abc123"


# ── list_sessions ─────────────────────────────────────────────────────


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_ok(self, skill):
        mock_response = AsyncMock()
        mock_response.text = json.dumps([{"id": "s1"}, {"id": "s2"}])
        mock_response.raise_for_status = MagicMock()

        skill._client = AsyncMock()
        skill._client.get = AsyncMock(return_value=mock_response)

        result = await skill.list_sessions()
        assert result.success is True
        assert result.data["session_count"] == 2

    @pytest.mark.asyncio
    async def test_list_sessions_timeout(self, skill):
        import httpx

        skill._client = AsyncMock()
        skill._client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        result = await skill.list_sessions()
        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_list_sessions_generic_error(self, skill):
        skill._client = AsyncMock()
        skill._client.get = AsyncMock(side_effect=RuntimeError("boom"))

        result = await skill.list_sessions()
        assert result.success is False
        assert "boom" in result.error


# ── delete_session ────────────────────────────────────────────────────


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_ok(self, skill):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        skill._client = AsyncMock()
        skill._client.delete = AsyncMock(return_value=mock_response)

        result = await skill.delete_session(session_id="abc123")
        assert result.success is True
        assert result.data["deleted"] == "abc123"

    @pytest.mark.asyncio
    async def test_delete_empty_id(self, skill):
        result = await skill.delete_session(session_id="")
        assert result.success is False
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_delete_kwarg_id(self, skill):
        """session_id can also be passed via **kwargs when the positional arg is omitted."""
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()

        skill._client = AsyncMock()
        skill._client.delete = AsyncMock(return_value=mock_response)

        result = await skill.delete_session(**{"session_id": "xyz"})
        assert result.success is True
        assert result.data["deleted"] == "xyz"


# ── prune_sessions ────────────────────────────────────────────────────


class TestPruneSessions:
    @pytest.mark.asyncio
    async def test_prune_dry_run(self, skill):
        """Dry-run prune should not actually delete anything."""
        mock_list = AsyncMock(
            return_value=SkillResult.ok({
                "session_count": 2,
                "sessions": [
                    {"id": "old1", "updatedAt": "2020-01-01T00:00:00Z"},
                    {"id": "new1", "updatedAt": "2099-01-01T00:00:00Z"},
                ],
            })
        )
        skill.list_sessions = mock_list

        result = await skill.prune_sessions(dry_run=True)
        assert result.success is True
        assert result.data["dry_run"] is True
        assert result.data["pruned_count"] == 1
        assert "old1" in result.data["deleted_ids"]

    @pytest.mark.asyncio
    async def test_prune_list_failure_propagates(self, skill):
        skill.list_sessions = AsyncMock(
            return_value=SkillResult.fail("cannot list")
        )
        result = await skill.prune_sessions()
        assert result.success is False


# ── close ─────────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self, skill):
        skill._client = AsyncMock()
        await skill.close()
        skill._client.aclose.assert_awaited_once()
