# aria_skills/memory_compression/__init__.py
"""
Memory compression — wraps api_client.summarize_session() for episodic memory.

Thin wrapper around existing API endpoints. Does NOT rebuild compression.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class MemoryCompressionSkill(BaseSkill):
    """Compress session history into episodic semantic memories."""

    def __init__(self, config: Optional[SkillConfig] = None):
        super().__init__(config or SkillConfig(name="memory_compression"))
        self._api = None

    @property
    def name(self) -> str:
        return "memory_compression"

    async def initialize(self) -> bool:
        """Initialize via centralized API client."""
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception as e:
            self.logger.error(f"API client init failed: {e}")
            self._status = SkillStatus.UNAVAILABLE
            return False
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Memory compression initialized (shared API client)")
        return True

    async def health_check(self) -> SkillStatus:
        if self._api is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    @logged_method()
    async def compress_session(self, hours_back: int = 6, **kwargs) -> SkillResult:
        """
        Compress recent session activity into a semantic memory summary.

        Uses api_client.summarize_session() which LLM-summarizes activities
        from the last N hours and stores as episodic semantic memory.

        Args:
            hours_back: How many hours of activity to compress (default: 6).
        """
        hours_back = int(kwargs.get("hours_back", hours_back))
        hours_back = max(1, min(48, hours_back))

        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            result = await self._api.summarize_session(hours_back=hours_back)
            if not result.success:
                return SkillResult.fail(f"Compression failed: {result.error}")

            data = result.data or {}
            return SkillResult.ok({
                "compressed": True,
                "hours_back": hours_back,
                "summary": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            return SkillResult.fail(f"Compression failed: {e}")

    @logged_method()
    async def get_context_budget(self, max_tokens: int = 2000, **kwargs) -> SkillResult:
        """
        Retrieve working memory context within a token budget.

        Uses api_client.get_working_memory_context() with weighted relevance.

        Args:
            max_tokens: Maximum tokens for context (default: 2000).
        """
        max_tokens = int(kwargs.get("max_tokens", max_tokens))
        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            result = await self._api.get_working_memory_context(limit=20)
            if not result.success:
                return SkillResult.fail(f"Context retrieval failed: {result.error}")

            items: List[Dict[str, Any]] = []
            raw = result.data
            if isinstance(raw, dict):
                items = raw.get("items", raw.get("context", []))
            elif isinstance(raw, list):
                items = raw

            # Estimate tokens (rough: 1 token ≈ 4 chars) and truncate to budget
            total_chars = 0
            selected: List[Dict[str, Any]] = []
            for item in items:
                val = str(item.get("value", "")) if isinstance(item, dict) else str(item)
                chars = len(val)
                if total_chars + chars > max_tokens * 4:
                    break
                total_chars += chars
                selected.append(item)

            return SkillResult.ok({
                "items_count": len(selected),
                "total_available": len(items),
                "estimated_tokens": total_chars // 4,
                "budget": max_tokens,
                "items": selected,
            })
        except Exception as e:
            return SkillResult.fail(f"Context retrieval failed: {e}")

    async def close(self) -> None:
        """Cleanup."""
        self._api = None
        self._status = SkillStatus.UNAVAILABLE
