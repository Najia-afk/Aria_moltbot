"""
Telegram Webhook Router
=======================
Receives incoming Telegram updates via webhook (push model).
Maps each Telegram chat_id to a persistent Aria chat session so the
conversation has full memory across messages — exactly like the web chat UI.

Flow:
  Telegram → POST /telegram/webhook → Aria chat engine → sendMessage reply

No polling. No wasted LLM tokens. Instant response on every message.

Setup:
  Call POST /api/telegram/register-webhook?url=https://your-domain.com
  to tell Telegram where to push updates.
"""
import json
import logging
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

logger = logging.getLogger("aria.telegram.webhook")

router = APIRouter(prefix="/telegram", tags=["telegram"])

# ── Session persistence ───────────────────────────────────────────────────
# Maps Telegram chat_id (str) → Aria session_id (str)
_SESSIONS_FILE = Path(
    os.environ.get("ARIA_MEMORIES_PATH", "/app/aria_memories")
) / "memory" / "telegram_sessions.json"


def _load_sessions() -> dict:
    try:
        if _SESSIONS_FILE.exists():
            return json.loads(_SESSIONS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_sessions(mapping: dict) -> None:
    try:
        _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SESSIONS_FILE.write_text(json.dumps(mapping, indent=2))
    except Exception as e:
        logger.warning("Could not persist telegram sessions: %s", e)


# ── Telegram API helpers ──────────────────────────────────────────────────

def _bot_url(path: str) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}/{path}"


async def _send_reply(chat_id: str | int, text: str) -> None:
    """Send a message back to the Telegram chat."""
    if not text:
        return
    # Telegram message limit is 4096 chars — split if needed
    chunks = [text[i:i + 4096] for i in range(0, len(text), 4096)]
    async with httpx.AsyncClient(timeout=15) as client:
        for chunk in chunks:
            try:
                await client.post(_bot_url("sendMessage"), json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                })
            except Exception as e:
                logger.error("Failed to send Telegram reply: %s", e)


# ── Internal API helper (reuse the running chat engine) ──────────────────

async def _get_or_create_session(chat_id: str, username: str | None) -> str:
    """Return an existing Aria session for this chat_id, or create one."""
    mapping = _load_sessions()
    if chat_id in mapping:
        return mapping[chat_id]

    # Create a new session via the internal API
    api_base = os.environ.get("ENGINE_API_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("ARIA_API_KEY", "")
    title = f"Telegram — {username or chat_id}"

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{api_base}/api/engine/chat/sessions",
            json={"title": title, "agent_id": "aria"},
            headers={"X-API-Key": api_key} if api_key else {},
        )
        resp.raise_for_status()
        session_id = resp.json()["id"]

    mapping[chat_id] = session_id
    _save_sessions(mapping)
    logger.info("Created Telegram session %s for chat_id=%s", session_id, chat_id)
    return session_id


async def _chat(session_id: str, text: str) -> str:
    """Send a message to the Aria chat engine and return the reply."""
    api_base = os.environ.get("ENGINE_API_BASE_URL", "http://localhost:8000")
    api_key = os.environ.get("ARIA_API_KEY", "")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{api_base}/api/engine/chat/sessions/{session_id}/messages",
            json={"content": text, "enable_tools": True, "enable_thinking": False},
            headers={"X-API-Key": api_key} if api_key else {},
        )
        resp.raise_for_status()
        return resp.json().get("content", "")


# ── Webhook endpoint ──────────────────────────────────────────────────────

async def _process_update(update: dict) -> None:
    """Background task: process one Telegram update and reply."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return  # inline queries, etc. — ignore for now

    chat_id = str(message["chat"]["id"])
    text = message.get("text", "").strip()
    username = message.get("from", {}).get("username")

    if not text:
        return  # photo, sticker, etc. — ignore

    # Security: only respond to the allowed user
    allowed_user = os.environ.get("TELEGRAM_ALLOWED_USER_ID", "")
    from_id = str(message.get("from", {}).get("id", ""))
    if allowed_user and from_id != allowed_user:
        logger.warning("Blocked Telegram message from unknown user %s", from_id)
        return

    logger.info("Telegram incoming from chat_id=%s: %r", chat_id, text[:80])

    try:
        # Send typing indicator
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(_bot_url("sendChatAction"), json={
                "chat_id": chat_id,
                "action": "typing",
            })
    except Exception:
        pass

    try:
        session_id = await _get_or_create_session(chat_id, username)
        reply = await _chat(session_id, text)
        await _send_reply(chat_id, reply)
    except Exception as e:
        logger.error("Failed to process Telegram message: %s", e)
        await _send_reply(chat_id, f"⚠️ Something went wrong: {e}")


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """
    Receive a Telegram update (webhook push).
    Telegram calls this immediately when you send a message — no polling.
    """
    # Validate secret token if configured
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = await request.json()
    background_tasks.add_task(_process_update, update)
    # Must return 200 quickly — Telegram will retry if we're slow
    return {"ok": True}


# ── Admin: register / inspect webhook ──────────────────────────────────────

@router.post("/register-webhook")
async def register_webhook(url: str):
    """
    Tell Telegram to start pushing updates to the given HTTPS URL.
    Call once after deployment: POST /api/telegram/register-webhook?url=https://...
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not set")

    webhook_url = url.rstrip("/") + "/api/telegram/webhook"
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

    payload: dict = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_bot_url("setWebhook"), json=payload)

    data = resp.json()
    if not data.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram setWebhook failed: {data}")

    logger.info("Telegram webhook registered: %s", webhook_url)
    return {"registered": True, "url": webhook_url, "telegram": data}


@router.get("/webhook-info")
async def webhook_info():
    """Check current Telegram webhook status."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not set")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_bot_url("getWebhookInfo"))

    return resp.json()


@router.delete("/webhook")
async def delete_webhook():
    """Remove Telegram webhook (switches back to no updates — NOT polling)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(status_code=503, detail="TELEGRAM_BOT_TOKEN not set")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(_bot_url("deleteWebhook"))

    return resp.json()
