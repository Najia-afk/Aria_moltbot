"""Tests for the Telegram Bot API skill."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.telegram import TelegramSkill


@pytest.fixture
def config():
    return SkillConfig(name="telegram", config={})


@pytest.fixture
def config_with_token():
    return SkillConfig(name="telegram", config={"bot_token": "test-token-123"})


@pytest.fixture
def skill(config):
    return TelegramSkill(config)


@pytest.fixture
def skill_with_token(config_with_token):
    return TelegramSkill(config_with_token)


# ── name property ────────────────────────────────────────────────────

def test_name_property(skill):
    assert skill.name == "telegram"


# ── initialize ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_initialize_no_token(skill):
    """No token → returns True but status UNAVAILABLE."""
    with patch.dict("os.environ", {}, clear=False):
        # Ensure no env token leaks in
        env = {k: v for k, v in __import__("os").environ.items() if k != "TELEGRAM_BOT_TOKEN"}
        with patch.dict("os.environ", env, clear=True):
            result = await skill.initialize()
    assert result is True
    assert skill.status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_initialize_with_token(skill_with_token):
    """Mock getMe 200 → status AVAILABLE."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "result": {"id": 123, "is_bot": True, "username": "test_bot"},
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=mock_resp)
        MockClient.return_value = instance

        result = await skill_with_token.initialize()

    assert result is True
    assert skill_with_token.status == SkillStatus.AVAILABLE
    assert skill_with_token._bot_info["username"] == "test_bot"


# ── send_message ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_message_success(skill_with_token):
    """Mock sendMessage 200 → SkillResult.ok."""
    # Initialize first
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    send_resp = MagicMock()
    send_resp.status_code = 200
    send_resp.json.return_value = {
        "ok": True,
        "result": {"message_id": 42, "chat": {"id": 999}},
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.post = AsyncMock(return_value=send_resp)
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.send_message("Hello!", chat_id="999")

    assert result.success is True
    assert result.data["message_id"] == 42


@pytest.mark.asyncio
async def test_send_message_no_chat_id(skill_with_token):
    """No chat_id and no env → SkillResult.fail."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        MockClient.return_value = instance

        with patch.dict("os.environ", {"TELEGRAM_CHAT_ID": ""}, clear=False):
            await skill_with_token.initialize()
            result = await skill_with_token.send_message("Hello!")

    assert result.success is False
    assert "chat_id" in result.error.lower() or "TELEGRAM_CHAT_ID" in result.error


@pytest.mark.asyncio
async def test_send_message_chat_not_found(skill_with_token):
    """Mock 400 with 'chat not found' → clear error message."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    err_resp = MagicMock()
    err_resp.status_code = 400
    err_resp.json.return_value = {
        "ok": False,
        "description": "Bad Request: chat not found",
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.post = AsyncMock(return_value=err_resp)
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.send_message("Hello!", chat_id="000")

    assert result.success is False
    assert "chat not found" in result.error.lower()
    assert "/start" in result.error


@pytest.mark.asyncio
async def test_send_message_rate_limited(skill_with_token):
    """Mock 429 then 200 → retry succeeds."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    rate_resp = MagicMock()
    rate_resp.status_code = 429
    rate_resp.json.return_value = {
        "ok": False,
        "parameters": {"retry_after": 0},  # 0 for fast tests
    }

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.json.return_value = {
        "ok": True,
        "result": {"message_id": 99},
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.post = AsyncMock(side_effect=[rate_resp, ok_resp])
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.send_message("Retry me", chat_id="123")

    assert result.success is True
    assert result.data["message_id"] == 99


@pytest.mark.asyncio
async def test_send_message_unauthorized(skill_with_token):
    """Mock 401 → 'Invalid bot token'."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    auth_resp = MagicMock()
    auth_resp.status_code = 401
    auth_resp.json.return_value = {"ok": False, "description": "Unauthorized"}

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.post = AsyncMock(return_value=auth_resp)
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.send_message("Test", chat_id="123")

    assert result.success is False
    assert "invalid bot token" in result.error.lower()


# ── get_updates ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_updates(skill_with_token):
    """Mock getUpdates 200 → list of updates."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    updates_resp = MagicMock()
    updates_resp.status_code = 200
    updates_resp.json.return_value = {
        "ok": True,
        "result": [
            {"update_id": 1, "message": {"text": "hi"}},
            {"update_id": 2, "message": {"text": "hello"}},
        ],
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(side_effect=[get_me_resp, updates_resp])
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.get_updates(limit=10)

    assert result.success is True
    assert len(result.data) == 2
    assert result.data[0]["update_id"] == 1


# ── reply_to_message ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reply_to_message(skill_with_token):
    """Mock sendMessage with reply_to → ok."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    reply_resp = MagicMock()
    reply_resp.status_code = 200
    reply_resp.json.return_value = {
        "ok": True,
        "result": {"message_id": 55, "reply_to_message": {"message_id": 10}},
    }

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.post = AsyncMock(return_value=reply_resp)
        MockClient.return_value = instance

        await skill_with_token.initialize()
        result = await skill_with_token.reply_to_message(
            chat_id="999", message_id=10, text="Reply!"
        )

    assert result.success is True
    assert result.data["message_id"] == 55


# ── close ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close(skill_with_token):
    """Verify client.aclose() called."""
    get_me_resp = MagicMock()
    get_me_resp.status_code = 200
    get_me_resp.json.return_value = {"ok": True, "result": {"username": "bot"}}

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.get = AsyncMock(return_value=get_me_resp)
        instance.aclose = AsyncMock()
        MockClient.return_value = instance

        await skill_with_token.initialize()
        await skill_with_token.close()

    instance.aclose.assert_called_once()
    assert skill_with_token._client is None
