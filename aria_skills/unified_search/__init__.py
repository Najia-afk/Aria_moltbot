# aria_skills/unified_search/__init__.py
"""
Unified search — merges skill graph + semantic memory results via RRF.

Architecture: Option 2 (separate tables) with unified search wrapper.
Per CLAUDE_SCHEMA_ADVICE.md — simple, works, scales to current needs.
"""
import asyncio
from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


def _rrf_merge(results_lists: List[List[Dict[str, Any]]], k: int = 60) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion: merge multiple ranked lists into one.

    Score = sum(1 / (k + rank + 1)) for each list the item appears in.
    Items appearing in multiple lists get higher combined scores.
    """
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}

    for result_list in results_lists:
        for rank, item in enumerate(result_list):
            item_id = str(item.get("id", item.get("name", id(item))))
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)
            if item_id not in items:
                items[item_id] = item

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
    return [items[iid] for iid in sorted_ids if iid in items]


@SkillRegistry.register
class UnifiedSearchSkill(BaseSkill):
    """Search across skill graph + semantic memories with RRF merge."""

    def __init__(self, config: Optional[SkillConfig] = None):
        super().__init__(config or SkillConfig(name="unified_search"))
        self._api = None

    @property
    def name(self) -> str:
        return "unified_search"

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
        self.logger.info("Unified search initialized (shared API client)")
        return True

    async def health_check(self) -> SkillStatus:
        if self._api is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    @logged_method()
    async def search(self, query: str = "", limit: int = 10, **kwargs) -> SkillResult:
        """
        Search across skill graph and semantic memories, merge with RRF.

        Args:
            query: Search text.
            limit: Max results (split between sources).
        """
        query = query or kwargs.get("query", "")
        if not query:
            return SkillResult.fail("query is required")
        limit = int(kwargs.get("limit", limit))

        if self._api is None:
            return SkillResult.fail("api_client not available")

        try:
            # Parallel search across both sources
            skills_task = self._search_skills(query, limit)
            memories_task = self._search_memories(query, limit)
            skills_results, memory_results = await asyncio.gather(
                skills_task, memories_task, return_exceptions=True
            )

            # Handle partial failures gracefully
            skills_list = skills_results if isinstance(skills_results, list) else []
            memory_list = memory_results if isinstance(memory_results, list) else []

            merged = _rrf_merge([skills_list, memory_list])[:limit]

            return SkillResult.ok({
                "query": query,
                "results": merged,
                "total": len(merged),
                "sources": {
                    "skills": len(skills_list),
                    "memories": len(memory_list),
                },
            })
        except Exception as e:
            return SkillResult.fail(f"Search failed: {e}")

    async def _search_skills(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search skill graph entities."""
        try:
            result = await self._api.graph_search(query=query, limit=limit)
            if not result.success:
                return []
            data = result.data
            if isinstance(data, dict):
                return data.get("entities", data.get("results", []))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def _search_memories(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Search semantic memories."""
        try:
            result = await self._api.search_memories_semantic(query=query, limit=limit)
            if not result.success:
                return []
            data = result.data
            if isinstance(data, dict):
                return data.get("memories", data.get("results", []))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def close(self) -> None:
        """Cleanup."""
        self._api = None
        self._status = SkillStatus.UNAVAILABLE
