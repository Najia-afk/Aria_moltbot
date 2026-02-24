"""
Tests for the telegram skill (Layer 3 — domain).

Covers:
- Initialization (with and without token)
- send_message (success, rate limiting, errors)
- get_updates
- reply_to_message
- Health check
All httpx calls are mocked.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.telegram import TelegramSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def _make_skill(token="test-bot-token"):
    return TelegramSkill(SkillConfig(name="telegram", config={
        "bot_token": token,
    }))


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize_success():
    skill = _make_skill()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(200, {
        "result": {"username": "test_bot", "id": 123}
    }))

    with patch("aria_skills.telegram.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE
    assert skill._bot_info.get("username") == "test_bot"


@pytest.mark.asyncio
async def test_initialize_no_token():
    skill = TelegramSkill(SkillConfig(name="telegram", config={"bot_token": ""}))
    with patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": ""}, clear=False):
        ok = await skill.initialize()
    assert ok is True  # Loaded but unavailable
    assert skill._status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_initialize_api_error():
    skill = _make_skill()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_mock_response(401))

    with patch("aria_skills.telegram.httpx") as mock_httpx:
        mock_httpx.AsyncClient.return_value = mock_client
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.ERROR


# ---------------------------------------------------------------------------
# send_message tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_message_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._default_chat_id = "12345"
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "result": {"message_id": 42, "chat": {"id": 12345}}
    }))

    result = await skill.send_message(text="Hello!")
    assert result.success
    assert result.data["message_id"] == 42


@pytest.mark.asyncio
async def test_send_message_no_client():
    skill = _make_skill()
    skill._client = None
    result = await skill.send_message(text="Hello!")
    assert not result.success


@pytest.mark.asyncio
async def test_send_message_no_chat_id():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._default_chat_id = ""
    result = await skill.send_message(text="Hello!")
    assert not result.success
    assert "chat_id" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_rate_limited():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._default_chat_id = "12345"

    rate_resp = _mock_response(429, {"parameters": {"retry_after": 0}})
    success_resp = _mock_response(200, {"result": {"message_id": 99}})
    skill._client.post = AsyncMock(side_effect=[rate_resp, success_resp])

    result = await skill.send_message(text="Retry me")
    assert result.success


@pytest.mark.asyncio
async def test_send_message_chat_not_found():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._default_chat_id = "99999"
    skill._client.post = AsyncMock(return_value=_mock_response(400, {
        "description": "Bad Request: chat not found"
    }))

    result = await skill.send_message(text="Nobody home")
    assert not result.success
    assert "chat not found" in result.error.lower()


@pytest.mark.asyncio
async def test_send_message_invalid_token():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._default_chat_id = "12345"
    skill._client.post = AsyncMock(return_value=_mock_response(401))

    result = await skill.send_message(text="Bad token")
    assert not result.success
    assert "invalid" in result.error.lower()


# ---------------------------------------------------------------------------
# get_updates tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_updates_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._client.get = AsyncMock(return_value=_mock_response(200, {
        "result": [{"update_id": 1, "message": {"text": "hi"}}]
    }))

    result = await skill.get_updates()
    assert result.success


@pytest.mark.asyncio
async def test_get_updates_no_client():
    skill = _make_skill()
    skill._client = None
    result = await skill.get_updates()
    assert not result.success


# ---------------------------------------------------------------------------
# reply_to_message tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reply_to_message():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "result": {"message_id": 100}
    }))

    result = await skill.reply_to_message(chat_id="12345", message_id=42, text="Reply!")
    assert result.success


# ---------------------------------------------------------------------------
# health_check tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check_no_client():
    skill = _make_skill()
    skill._client = None
    status = await skill.health_check()
    assert status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_health_check_api_ok():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._base_url = "https://api.telegram.org/botTOKEN"
    skill._client.get = AsyncMock(return_value=_mock_response(200))
    status = await skill.health_check()
    assert status == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# close / get_me tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me():
    skill = _make_skill()
    skill._bot_info = {"username": "aria_bot", "id": 999}
    result = await skill.get_me()
    assert result.success
    assert result.data["username"] == "aria_bot"


@pytest.mark.asyncio
async def test_close():
    skill = _make_skill()
    skill._client = AsyncMock()
    await skill.close()
    assert skill._client is None
