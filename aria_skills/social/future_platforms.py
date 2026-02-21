"""Future-ready social platform connectors with safe simulation defaults."""


import os

from aria_skills.base import SkillResult


def _compact_tags(tags: list[str] | None) -> list[str]:
    return [str(tag).strip().lstrip("#") for tag in (tags or []) if str(tag).strip()]


class TelegramSimulationPlatform:
    """Telegram connector in simulation-first mode for aria-social."""

    platform_name = "telegram"

    _required_env = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]

    def _present(self) -> dict[str, bool]:
        present: dict[str, bool] = {}
        for key in self._required_env:
            val = os.getenv(key, "")
            present[key] = bool(val and val.strip())
        return present

    async def post(
        self,
        content: str,
        tags: list[str] | None = None,
        simulate: bool = True,
        chat_id: str | None = None,
        **_: object,
    ) -> SkillResult:
        if not content or not content.strip():
            return SkillResult.fail("content is required")

        present = self._present()
        ready = all(present.values())
        tags_compact = _compact_tags(tags)

        return SkillResult.ok(
            {
                "platform": "telegram",
                "simulated": True,
                "mode": "simulation",
                "requested_live": not simulate,
                "live_supported": False,
                "ready_for_live": ready,
                "credentials_present": present,
                "missing_env": [k for k, ok in present.items() if not ok],
                "would_post": {
                    "text": content,
                    "chat_id": chat_id or os.getenv("TELEGRAM_CHAT_ID"),
                    "tags": tags_compact,
                },
                "note": "Simulation only: aria-social telegram routing is dry-run by default.",
            }
        )

    async def get_posts(self, limit: int = 10) -> SkillResult:
        return SkillResult.ok(
            {
                "platform": "telegram",
                "simulated": True,
                "items": [],
                "limit": limit,
                "note": "No remote fetch in simulation mode.",
            }
        )

    async def delete_post(self, post_id: str) -> SkillResult:
        return SkillResult.ok(
            {
                "platform": "telegram",
                "simulated": True,
                "deleted": False,
                "post_id": post_id,
                "note": "No remote deletion in simulation mode.",
            }
        )

    async def health_check(self) -> bool:
        return all(self._present().values())
