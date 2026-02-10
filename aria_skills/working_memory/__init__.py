# aria_skills/working_memory/__init__.py
"""
Working Memory Skill — persistent short-term memory that survives restarts.

Wraps the /working-memory REST endpoints via httpx (api_client pattern).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class WorkingMemorySkill(BaseSkill):
    """
    Persistent working memory — remembers context across restarts.

    Operations:
        remember   — store a key/value with category + importance
        recall     — retrieve by key (optionally filtered by category)
        get_context— weighted-ranked retrieval for LLM context injection
        checkpoint — snapshot current state
        restore_checkpoint — fetch latest checkpoint
        forget     — delete an item by id
        reflect    — produce human-readable summary of current memory
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api = None

    @property
    def name(self) -> str:
        return "working_memory"

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Initialize via centralized API client."""
        try:
            self._api = await get_api_client()
        except Exception as e:
            self.logger.error(f"API client init failed: {e}")
            self._status = SkillStatus.UNAVAILABLE
            return False
        if not self._api._client:
            self.logger.error("API client not available")
            self._status = SkillStatus.UNAVAILABLE
            return False
        self._status = SkillStatus.AVAILABLE
        self.logger.info("WorkingMemory skill initialized (shared API client)")
        return True

    async def health_check(self) -> SkillStatus:
        """Ping the API health endpoint."""
        if not self._api or not self._api._client:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        try:
            resp = await self._api._client.get("/health")
            self._status = (
                SkillStatus.AVAILABLE if resp.status_code == 200 else SkillStatus.ERROR
            )
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        return self._status

    async def close(self) -> None:
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
        self._status = SkillStatus.UNAVAILABLE

    # ── Operations ───────────────────────────────────────────────────────

    @logged_method()
    async def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: float = 0.5,
        ttl_hours: Optional[int] = None,
        source: Optional[str] = None,
    ) -> SkillResult:
        """Store (or upsert) a working memory item."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.post("/working-memory", json={
                "key": key,
                "value": value,
                "category": category,
                "importance": importance,
                "ttl_hours": ttl_hours,
                "source": source,
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"remember failed: {e}")

    @logged_method()
    async def recall(
        self,
        key: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> SkillResult:
        """Retrieve working memory items by key and/or category."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            params: Dict[str, Any] = {"limit": limit}
            if key:
                params["key"] = key
            if category:
                params["category"] = category
            resp = await self._api._client.get("/working-memory", params=params)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"recall failed: {e}")

    @logged_method()
    async def get_context(
        self,
        limit: int = 20,
        weight_recency: float = 0.4,
        weight_importance: float = 0.4,
        weight_access: float = 0.2,
        category: Optional[str] = None,
    ) -> SkillResult:
        """Weighted-ranked context retrieval for LLM injection."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            params: Dict[str, Any] = {
                "limit": limit,
                "weight_recency": weight_recency,
                "weight_importance": weight_importance,
                "weight_access": weight_access,
            }
            if category:
                params["category"] = category
            resp = await self._api._client.get("/working-memory/context", params=params)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"get_context failed: {e}")

    @logged_method()
    async def checkpoint(self) -> SkillResult:
        """Snapshot all current working memory items."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.post("/working-memory/checkpoint", json={})
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"checkpoint failed: {e}")

    @logged_method()
    async def restore_checkpoint(self) -> SkillResult:
        """Fetch items from the latest checkpoint."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.get("/working-memory/checkpoint")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"restore_checkpoint failed: {e}")

    @logged_method()
    async def forget(self, item_id: str) -> SkillResult:
        """Delete a working memory item by UUID."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.delete(f"/working-memory/{item_id}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"forget failed: {e}")

    @logged_method()
    async def update(self, item_id: str, **kwargs) -> SkillResult:
        """Partial update (value, importance) for an item."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.patch(
                f"/working-memory/{item_id}",
                json=kwargs,
            )
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"update failed: {e}")

    @logged_method()
    async def reflect(self) -> SkillResult:
        """Produce a human-readable summary of current working memory."""
        if not self._api or not self._api._client:
            return SkillResult.fail("Working memory not initialized")
        try:
            resp = await self._api._client.get("/working-memory", params={"limit": 100})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

            if not items:
                return SkillResult.ok({
                    "summary": "Working memory is empty.",
                    "count": 0,
                })

            # Group by category
            categories: Dict[str, list] = {}
            for item in items:
                cat = item.get("category", "general")
                categories.setdefault(cat, []).append(item)

            parts = [f"Working memory: {len(items)} items across {len(categories)} categories.\n"]
            for cat, cat_items in sorted(categories.items()):
                parts.append(f"  [{cat}] ({len(cat_items)} items)")
                for ci in cat_items[:5]:
                    key = ci.get("key", "?")
                    importance = ci.get("importance", 0.5)
                    parts.append(f"    - {key} (importance={importance})")
                if len(cat_items) > 5:
                    parts.append(f"    ... and {len(cat_items) - 5} more")

            summary = "\n".join(parts)
            return SkillResult.ok({"summary": summary, "count": len(items)})
        except Exception as e:
            return SkillResult.fail(f"reflect failed: {e}")

    @logged_method()
    async def sync_to_files(self) -> SkillResult:
        """Cron-callable: sync DB state to aria_memories/memory/ JSON files."""
        import json as _json
        from pathlib import Path
        from datetime import timezone

        memories_path = Path(__file__).parent.parent.parent / "aria_memories" / "memory"
        memories_path.mkdir(parents=True, exist_ok=True)

        context_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "active_goals": [],
            "recent_activities": [],
            "system_health": {"status": "unknown"},
        }

        # Fetch goals via existing API client
        try:
            if self._api and self._api._client:
                resp = await self._api._client.get(
                    "/goals", params={"status": "active", "limit": 20}
                )
                if resp.status_code == 200:
                    context_data["active_goals"] = resp.json().get("goals", [])

                resp = await self._api._client.get(
                    "/activities", params={"limit": 10}
                )
                if resp.status_code == 200:
                    context_data["recent_activities"] = resp.json().get("activities", [])
        except Exception as e:
            self.logger.warning(f"sync_to_files: API fetch failed: {e}")

        # Write context.json
        context_path = memories_path / "context.json"
        context_path.write_text(
            _json.dumps(context_data, indent=2, default=str), encoding="utf-8"
        )

        files_written = ["context.json"]
        return SkillResult.ok({"files_updated": files_written, "path": str(memories_path)})
