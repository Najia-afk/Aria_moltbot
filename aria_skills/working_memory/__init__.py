# aria_skills/working_memory/__init__.py
"""
Working Memory Skill — persistent short-term memory that survives restarts.

Wraps the /working-memory REST endpoints via httpx (api_client pattern).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

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
        import os
        workspace_root = self._resolve_workspace_root()
        memories_path = workspace_root / "aria_memories" / "memory"
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

        # Write canonical context.json
        context_path = memories_path / "context.json"
        payload = _json.dumps(context_data, indent=2, default=str)
        context_path.write_text(
            payload, encoding="utf-8"
        )

        mirror_paths = self._legacy_snapshot_paths(workspace_root)
        mirrored = []
        pruned = []
        write_legacy_mirror = os.getenv("ARIA_WM_WRITE_LEGACY_MIRROR", "false").lower() == "true"
        prune_legacy = os.getenv("ARIA_WM_PRUNE_LEGACY_SNAPSHOTS", "true").lower() == "true"

        for mirror in mirror_paths:
            try:
                if write_legacy_mirror:
                    mirror.parent.mkdir(parents=True, exist_ok=True)
                    mirror.write_text(payload, encoding="utf-8")
                    mirrored.append(str(mirror))
                elif prune_legacy and mirror.exists():
                    mirror.unlink()
                    pruned.append(str(mirror))
            except Exception as e:
                self.logger.debug(f"sync_to_files: legacy maintenance skipped for {mirror}: {e}")

        files_written = ["context.json"]
        return SkillResult.ok({
            "files_updated": files_written,
            "path": str(memories_path),
            "workspace_root": str(workspace_root),
            "mirrored_paths": mirrored,
            "pruned_legacy_paths": pruned,
            "legacy_mirror_enabled": write_legacy_mirror,
        })

    def _resolve_workspace_root(self) -> Path:
        """Find the best workspace root across local and container execution layouts."""
        candidates: list[Path] = []

        env_root = self.config.config.get("workspace_root") if self.config and self.config.config else None
        if env_root:
            candidates.append(Path(str(env_root)).expanduser())

        env_root = None
        try:
            import os
            env_root = os.environ.get("ARIA_WORKSPACE_ROOT")
        except Exception:
            env_root = None
        if env_root:
            candidates.append(Path(env_root).expanduser())

        here = Path(__file__).resolve()
        candidates.extend([here.parent, *here.parents])
        candidates.append(Path.cwd())

        best: Path | None = None
        best_score = -1

        for cand in candidates:
            score = 0
            if (cand / "pyproject.toml").exists():
                score += 3
            if (cand / "README.md").exists():
                score += 2
            if (cand / "aria_memories").is_dir():
                score += 2
            if (cand / "aria_skills").is_dir():
                score += 2
            if (cand / "src").is_dir():
                score += 1

            if score > best_score:
                best = cand
                best_score = score

        return (best or Path.cwd()).resolve()

    def _legacy_snapshot_paths(self, workspace_root: Path) -> list[Path]:
        """Known compatibility locations that may still be read by older runtime paths."""
        paths = [
            workspace_root / "aria_mind" / "skills" / "aria_memories" / "memory" / "context.json",
        ]
        canonical = (workspace_root / "aria_memories" / "memory" / "context.json").resolve()
        unique: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            resolved = path.resolve()
            if resolved == canonical:
                continue
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique
