"""Telegram Bot API skill for Aria."""
import os
import asyncio
import logging
from datetime import datetime, timezone

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


@SkillRegistry.register
class TelegramSkill(BaseSkill):
    """
    Telegram Bot API integration.

    Uses httpx for direct HTTP calls to Telegram Bot API.
    Reads TELEGRAM_BOT_TOKEN from environment.
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._base_url: str = ""
        self._bot_info: dict = {}
        self._default_chat_id: str = ""

    @property
    def name(self) -> str:
        return "telegram"

    platform_name = "telegram"

    async def initialize(self) -> bool:
        token = self.config.config.get(
            "bot_token",
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        )
        if not token:
            self.logger.warning("TELEGRAM_BOT_TOKEN not set — skill unavailable")
            self._status = SkillStatus.UNAVAILABLE
            return True  # Skill loaded but not usable

        self._base_url = TELEGRAM_API_BASE.format(token=token)
        self._default_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        self._client = httpx.AsyncClient(timeout=30.0)

        try:
            resp = await self._client.get(f"{self._base_url}/getMe")
            if resp.status_code == 200:
                self._bot_info = resp.json().get("result", {})
                self._status = SkillStatus.AVAILABLE
                self.logger.info(
                    f"Telegram bot initialized: @{self._bot_info.get('username', 'unknown')}"
                )
            else:
                self.logger.error(f"Telegram getMe failed: {resp.status_code}")
                self._status = SkillStatus.ERROR
        except Exception as e:
            self.logger.warning(f"Telegram init failed (will work offline): {e}")
            self._status = SkillStatus.UNAVAILABLE

        return True

    async def health_check(self) -> SkillStatus:
        if not self._client:
            return SkillStatus.UNAVAILABLE
        try:
            resp = await self._client.get(f"{self._base_url}/getMe")
            self._status = (
                SkillStatus.AVAILABLE if resp.status_code == 200 else SkillStatus.ERROR
            )
        except Exception:
            self._status = SkillStatus.ERROR
        return self._status

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "Markdown",
    ) -> SkillResult:
        """Send a message to a Telegram chat."""
        if not self._client:
            return SkillResult.fail("Telegram client not initialized")

        target_chat = chat_id or self._default_chat_id
        if not target_chat:
            return SkillResult.fail(
                "No chat_id provided and TELEGRAM_CHAT_ID not set"
            )

        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            resp = await self._client.post(
                f"{self._base_url}/sendMessage", json=payload
            )

            if resp.status_code == 429:
                retry_after = resp.json().get("parameters", {}).get(
                    "retry_after", 5
                )
                self.logger.warning(f"Rate limited, retrying in {retry_after}s")
                await asyncio.sleep(retry_after)
                resp = await self._client.post(
                    f"{self._base_url}/sendMessage", json=payload
                )

            if resp.status_code == 400:
                error_desc = resp.json().get("description", "Unknown error")
                if "chat not found" in error_desc.lower():
                    return SkillResult.fail(
                        f"Chat not found: {target_chat}. "
                        "Ensure the user has sent /start to the bot first."
                    )
                return SkillResult.fail(f"Telegram error: {error_desc}")

            if resp.status_code == 401:
                return SkillResult.fail("Invalid bot token")

            if resp.status_code != 200:
                return SkillResult.fail(
                    f"Telegram API error {resp.status_code}: {resp.text}"
                )

            self._log_usage("send_message", True)
            return SkillResult.ok(resp.json().get("result", {}))

        except Exception as e:
            self._log_usage("send_message", False)
            return SkillResult.fail(f"Send failed: {e}")

    # SocialPlatform protocol
    async def post(
        self, content: str, tags: list[str] | None = None
    ) -> SkillResult:
        return await self.send_message(text=content)

    async def get_posts(self, limit: int = 10) -> SkillResult:
        return await self.get_updates(limit=limit)

    async def delete_post(self, post_id: str) -> SkillResult:
        return SkillResult.fail(
            "Telegram does not support post deletion via Bot API"
        )

    async def get_updates(
        self, offset: int | None = None, limit: int = 100
    ) -> SkillResult:
        """Get incoming updates (messages) from Telegram."""
        if not self._client:
            return SkillResult.fail("Telegram client not initialized")
        try:
            params: dict = {"limit": limit, "timeout": 0}
            if offset:
                params["offset"] = offset
            resp = await self._client.get(
                f"{self._base_url}/getUpdates", params=params
            )
            if resp.status_code != 200:
                return SkillResult.fail(f"getUpdates failed: {resp.status_code}")
            return SkillResult.ok(resp.json().get("result", []))
        except Exception as e:
            return SkillResult.fail(f"getUpdates error: {e}")

    async def reply_to_message(
        self, chat_id: str, message_id: int, text: str
    ) -> SkillResult:
        """Reply to a specific message."""
        if not self._client:
            return SkillResult.fail("Telegram client not initialized")
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "reply_to_message_id": message_id,
            }
            resp = await self._client.post(
                f"{self._base_url}/sendMessage", json=payload
            )
            if resp.status_code != 200:
                return SkillResult.fail(f"Reply failed: {resp.status_code}")
            return SkillResult.ok(resp.json().get("result", {}))
        except Exception as e:
            return SkillResult.fail(f"Reply error: {e}")

    async def get_me(self) -> SkillResult:
        """Get bot info."""
        return SkillResult.ok(self._bot_info)

    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None
