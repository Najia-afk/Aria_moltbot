"""Database skill compatibility layer — routes supported operations via api_client."""


from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class DatabaseSkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api = None

    @property
    def name(self) -> str:
        return "database"

    async def initialize(self) -> bool:
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE if self._api else SkillStatus.UNAVAILABLE
        return self._status == SkillStatus.AVAILABLE

    async def health_check(self) -> SkillStatus:
        return self._status

    async def fetch_all(self, query: str, args: list | None = None) -> SkillResult:
        return SkillResult.fail("Raw SQL execution is disabled in this environment; use api_client resource methods.")

    async def fetch_one(self, query: str, args: list | None = None) -> SkillResult:
        return SkillResult.fail("Raw SQL execution is disabled in this environment; use api_client resource methods.")

    async def execute(self, query: str, args: list | None = None) -> SkillResult:
        return SkillResult.fail("Raw SQL write execution is disabled in this environment.")

    async def log_thought(self, content: str, category: str = "general") -> SkillResult:
        try:
            data = await self._api.create_thought(content=content, category=category)
            return SkillResult.ok(data)
        except Exception as exc:
            return SkillResult.fail(f"log_thought failed: {exc}")

    async def get_recent_thoughts(self, limit: int = 10) -> SkillResult:
        try:
            data = await self._api.get_thoughts(limit=limit)
            return SkillResult.ok(data)
        except Exception as exc:
            return SkillResult.fail(f"get_recent_thoughts failed: {exc}")

    async def store_memory(self, key: str, value: str, category: str = "general") -> SkillResult:
        try:
            data = await self._api.set_memory(key=key, value=value, category=category)
            return SkillResult.ok(data)
        except Exception as exc:
            return SkillResult.fail(f"store_memory failed: {exc}")

    async def recall_memory(self, key: str) -> SkillResult:
        try:
            data = await self._api.get_memory(key=key)
            return SkillResult.ok(data)
        except Exception as exc:
            return SkillResult.fail(f"recall_memory failed: {exc}")

    async def search_memories(self, pattern: str = "%", category: str | None = None, limit: int = 10) -> SkillResult:
        try:
            query = pattern.replace("%", " ").strip() or "memory"
            data = await self._api.search_memories_semantic(query=query, category=category, limit=limit)
            return SkillResult.ok(data)
        except Exception as exc:
            return SkillResult.fail(f"search_memories failed: {exc}")
