# aria_skills/database/__init__.py
"""
Database skill — proxies through api_client to Aria's REST API.

Provides thought/memory CRUD and search via the existing API endpoints.
Raw SQL is NOT supported for safety; all operations go through the API.
"""
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class DatabaseSkill(BaseSkill):
    """
    Self-healing database skill.

    Proxies all data access through api_client → FastAPI → PostgreSQL.
    Tools: fetch_all, fetch_one, execute (read-only),
           log_thought, get_recent_thoughts,
           store_memory, recall_memory, search_memories.
    """

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="database"))
        self._api = None

    @property
    def name(self) -> str:
        return "database"

    async def initialize(self) -> bool:
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception as e:
            self.logger.error(f"API client required for database skill: {e}")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._status = SkillStatus.AVAILABLE
        self.logger.info("Database skill initialized via api_client")
        return True

    async def health_check(self) -> SkillStatus:
        if self._api is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    # ── Thoughts ──────────────────────────────────────────────────

    @logged_method()
    async def log_thought(
        self, content: str = "", category: str = "general",
        metadata: dict | None = None, **kwargs
    ) -> SkillResult:
        """Log a new thought to the database."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        content = content or kwargs.get("content", "")
        if not content:
            return SkillResult.fail("No content provided")
        return await self._api.create_thought(
            content=content,
            category=category or kwargs.get("category", "general"),
            metadata=metadata or kwargs.get("metadata"),
        )

    @logged_method()
    async def get_recent_thoughts(
        self, limit: int = 25, page: int = 1, **kwargs
    ) -> SkillResult:
        """Get recent thoughts."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        return await self._api.get_thoughts(
            limit=limit or kwargs.get("limit", 25),
            page=page or kwargs.get("page", 1),
        )

    # ── Memories ──────────────────────────────────────────────────

    @logged_method()
    async def store_memory(
        self, key: str = "", value: Any = None,
        category: str = "general", **kwargs
    ) -> SkillResult:
        """Store a key-value memory."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        key = key or kwargs.get("key", "")
        if not key:
            return SkillResult.fail("No key provided")
        value = value if value is not None else kwargs.get("value")
        return await self._api.set_memory(
            key=key, value=value,
            category=category or kwargs.get("category", "general"),
        )

    @logged_method()
    async def recall_memory(self, key: str = "", **kwargs) -> SkillResult:
        """Recall a memory by key."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        key = key or kwargs.get("key", "")
        if not key:
            return SkillResult.fail("No key provided")
        return await self._api.get_memory(key=key)

    @logged_method()
    async def search_memories(
        self, query: str = "", category: str | None = None,
        limit: int = 20, **kwargs
    ) -> SkillResult:
        """Search memories (semantic if available, else keyword via category)."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        query = query or kwargs.get("query", "")
        if not query:
            return await self._api.get_memories(
                limit=limit, category=category or kwargs.get("category"),
            )
        # Try semantic search first
        try:
            result = await self._api.search_memories_semantic(
                query=query, limit=limit, category=category,
            )
            if result.success:
                return result
        except Exception:
            pass
        # Fallback to category listing
        return await self._api.get_memories(
            limit=limit, category=category or kwargs.get("category"),
        )

    # ── Generic query proxies (read-only, via API) ────────────────

    @logged_method()
    async def fetch_all(
        self, table: str = "", limit: int = 25, **kwargs
    ) -> SkillResult:
        """Fetch rows from a table via the appropriate API endpoint."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        table = table or kwargs.get("table", "")
        TABLE_MAP = {
            "thoughts": lambda: self._api.get_thoughts(limit=limit),
            "memories": lambda: self._api.get_memories(limit=limit),
            "activities": lambda: self._api.get_activities(limit=limit),
            "goals": lambda: self._api.get_goals(limit=limit),
            "entities": lambda: self._api.get_entities(limit=limit),
        }
        fetcher = TABLE_MAP.get(table)
        if not fetcher:
            return SkillResult.fail(
                f"Table '{table}' not supported. Available: {', '.join(TABLE_MAP)}"
            )
        return await fetcher()

    @logged_method()
    async def fetch_one(self, table: str = "", key: str = "", **kwargs) -> SkillResult:
        """Fetch a single record by key."""
        if self._api is None:
            return SkillResult.fail("database not initialized")
        table = table or kwargs.get("table", "")
        key = key or kwargs.get("key", kwargs.get("id", ""))
        if table == "memories":
            return await self._api.get_memory(key=key)
        return SkillResult.fail(f"fetch_one not yet supported for table '{table}'")

    @logged_method()
    async def execute(self, query: str = "", **kwargs) -> SkillResult:
        """Execute is disabled for safety. Use specific methods instead."""
        return SkillResult.fail(
            "Raw SQL execution is disabled for safety. "
            "Use log_thought, store_memory, fetch_all, etc."
        )
