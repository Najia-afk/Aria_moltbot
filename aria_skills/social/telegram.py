"""Telegram bot integration via long-poll — S-46 implementation.

Strategy: long-poll (getUpdates) to avoid the need for a public HTTPS URL.
The `telegram_poll` cron job (aria_mind/cron_jobs.yaml) calls poll_once() every 2 min.

Commands:
    /status  — system health summary
    /goals   — active goals with progress bars
    /memory  — recent activities

Environment variables (stacks/brain/.env):
    TELEGRAM_BOT_TOKEN      — BotFather token for @aria_blue_bot
    TELEGRAM_ADMIN_CHAT_ID  — Najia's chat ID for push notifications
"""
import logging
import os
from typing import Any

import httpx

from aria_skills.base import SkillResult

logger = logging.getLogger("aria.skill.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramPlatform:
    platform_name = "telegram"

    def __init__(self) -> None:
        self._token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._base: str = TELEGRAM_API.format(token=self._token) if self._token else ""
        self._offset: int = 0
        self._sessions: dict[int, list[dict[str, Any]]] = {}  # chat_id → message history

    # ── Core API ──────────────────────────────────────────────────────────────

    async def send_message(self, chat_id: int, text: str) -> SkillResult:
        """Send a Markdown message to a Telegram chat."""
        if not self._token:
            return SkillResult.fail("TELEGRAM_BOT_TOKEN not set")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{self._base}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                )
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Telegram API error: {resp.status_code} {resp.text}")
        except Exception as exc:
            logger.exception("send_message failed: %s", exc)
            return SkillResult.fail(str(exc))

    async def get_updates(self, timeout: int = 2) -> list[dict[str, Any]]:
        """Long-poll for new updates from Telegram's getUpdates endpoint."""
        if not self._token:
            return []
        try:
            async with httpx.AsyncClient(timeout=timeout + 5) as client:
                resp = await client.get(
                    f"{self._base}/getUpdates",
                    params={"offset": self._offset, "timeout": timeout},
                )
            if resp.status_code != 200:
                logger.warning("getUpdates returned %s", resp.status_code)
                return []
            updates: list[dict[str, Any]] = resp.json().get("result", [])
            if updates:
                self._offset = updates[-1]["update_id"] + 1
            return updates
        except Exception as exc:
            logger.error("get_updates failed: %s", exc)
            return []

    # ── Command Handlers ──────────────────────────────────────────────────────

    async def handle_status(self, chat_id: int) -> SkillResult:
        """/status — system health summary via api_client."""
        try:
            from aria_skills.api_client import get_api_client  # type: ignore[import]

            api = await get_api_client()
            hb = await api.get_latest_heartbeat()
            beat = hb.get("beat_number", "?")
            status = hb.get("status", "unknown")
            details = hb.get("details", {})
            msg = (
                f"*System Status*\n"
                f"Beat #{beat} — {status}\n"
                f"Soul: {'✅' if details.get('soul') else '❌'}\n"
                f"Memory: {'✅' if details.get('memory') else '❌'}\n"
                f"Cognition: {'✅' if details.get('cognition') else '❌'}"
            )
            return await self.send_message(chat_id, msg)
        except Exception as exc:
            logger.exception("handle_status failed")
            return SkillResult.fail(str(exc))

    async def handle_goals(self, chat_id: int) -> SkillResult:
        """/goals — active goals list with progress bars."""
        try:
            from aria_skills.api_client import get_api_client  # type: ignore[import]

            api = await get_api_client()
            goals = await api.get_goals(status="active", limit=5)
            if not goals:
                return await self.send_message(chat_id, "*No active goals.*")
            lines = ["*Active Goals:*"]
            for g in goals:
                pct = int(g.get("progress", 0))
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"• {g['title'][:40]} `{bar}` {pct}%")
            return await self.send_message(chat_id, "\n".join(lines))
        except Exception as exc:
            logger.exception("handle_goals failed")
            return SkillResult.fail(str(exc))

    async def handle_memory(self, chat_id: int) -> SkillResult:
        """/memory — recent activities."""
        try:
            from aria_skills.api_client import get_api_client  # type: ignore[import]

            api = await get_api_client()
            activities = await api.get_activities(limit=5)
            lines = ["*Recent Activity:*"]
            for a in activities:
                ts = str(a.get("created_at", ""))[:16]
                lines.append(f"• `{ts}` {a.get('action', '?')}")
            return await self.send_message(chat_id, "\n".join(lines))
        except Exception as exc:
            logger.exception("handle_memory failed")
            return SkillResult.fail(str(exc))

    async def handle_command(self, update: dict[str, Any]) -> None:
        """Route an incoming Telegram update to the correct command handler."""
        msg = update.get("message", {})
        chat_id: int | None = msg.get("chat", {}).get("id")
        text: str = msg.get("text", "")
        if not chat_id or not text.startswith("/"):
            return
        # Thread context — store user message history per chat_id
        self._sessions.setdefault(chat_id, []).append({"role": "user", "content": text})
        command = text.split()[0].split("@")[0]  # strip @bot_name suffix
        route: dict[str, Any] = {
            "/status": self.handle_status,
            "/goals": self.handle_goals,
            "/memory": self.handle_memory,
        }
        handler = route.get(command)
        if handler:
            await handler(chat_id)
        else:
            await self.send_message(chat_id, "Commands: /status · /goals · /memory")

    # ── Polling Loop ──────────────────────────────────────────────────────────

    async def poll_once(self) -> None:
        """Process one batch of updates. Called by the telegram_poll cron job."""
        updates = await self.get_updates()
        for update in updates:
            try:
                await self.handle_command(update)
            except Exception as exc:
                logger.error("Failed to handle update %s: %s", update.get("update_id"), exc)

    # ── Notification API ──────────────────────────────────────────────────────

    async def notify(self, chat_id: int, message: str) -> SkillResult:
        """Push a critical alert to a specific chat. Used by health/heartbeat events."""
        return await self.send_message(chat_id, f"🔔 *Aria Alert*\n{message}")

    # ── SkillResult compatibility ──────────────────────────────────────────────

    async def post(self, content: str, tags: list[str] | None = None) -> SkillResult:
        """Social interface — send to admin chat (TELEGRAM_ADMIN_CHAT_ID)."""
        raw_id = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "0")
        try:
            chat_id = int(raw_id)
        except ValueError:
            return SkillResult.fail(f"TELEGRAM_ADMIN_CHAT_ID is not a valid integer: {raw_id!r}")
        if not chat_id:
            return SkillResult.fail("TELEGRAM_ADMIN_CHAT_ID not set")
        return await self.send_message(chat_id, content)

    async def get_posts(self, limit: int = 10) -> SkillResult:
        return SkillResult.fail("Telegram does not support read-back of sent messages")

    async def delete_post(self, post_id: str) -> SkillResult:
        return SkillResult.fail("Telegram message deletion not implemented in S-46 scope")

    async def health_check(self) -> bool:
        """Return True if the bot token is valid and reachable."""
        if not self._token:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._base}/getMe")
            return resp.status_code == 200
        except Exception:
            return False
