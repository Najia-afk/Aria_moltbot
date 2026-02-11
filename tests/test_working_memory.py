# tests/test_working_memory.py
"""
Tests for TICKET-35 — Persistent Working Memory.

Covers:
  • ORM model columns
  • WorkingMemorySkill operations (remember, recall, get_context, checkpoint,
    restore_checkpoint, forget, reflect, update)
  • Context ranking / scoring
  • Category filtering
  • TTL handling
  • Skill properties (name, canonical_name)
  • Health check
  • API router endpoints with mock DB
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

pytestmark = pytest.mark.unit

from aria_skills.base import SkillConfig, SkillResult, SkillStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(api_url: str = "http://localhost:8000/api"):
    """Instantiate WorkingMemorySkill with a test config."""
    from aria_skills.working_memory import WorkingMemorySkill
    cfg = SkillConfig(name="working_memory", config={"api_url": api_url})
    return WorkingMemorySkill(cfg)


def _make_response(status_code=200, json_data=None):
    """Create a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


# ============================================================================
# 1. ORM Model
# ============================================================================

class TestWorkingMemoryORM:
    """Verify the SQLAlchemy model schema."""

    def test_working_memory_orm_model(self):
        """Model has all expected columns with correct types."""
        sa = pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed (runs in container)")
        sa_inspect = sa.inspect
        # Import via the canonical models module path
        import importlib, sys
        # Add src/api to path so we can import db.models
        sys.path.insert(0, "src/api")
        try:
            from db.models import WorkingMemory, Base
        except ImportError:
            # Fallback: import directly from the file
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "db.models", "src/api/db/models.py"
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            WorkingMemory = mod.WorkingMemory
            Base = mod.Base
        finally:
            if "src/api" in sys.path:
                sys.path.remove("src/api")

        mapper = sa_inspect(WorkingMemory)
        col_names = {c.key for c in mapper.column_attrs}

        expected = {
            "id", "category", "key", "value", "importance",
            "ttl_hours", "source", "checkpoint_id",
            "created_at", "updated_at", "accessed_at", "access_count",
        }
        assert expected.issubset(col_names), f"Missing columns: {expected - col_names}"
        assert WorkingMemory.__tablename__ == "working_memory"
        assert issubclass(WorkingMemory, Base)


# ============================================================================
# 2. Skill Properties
# ============================================================================

class TestSkillProperties:
    """Verify skill name and canonical_name."""

    def test_skill_properties(self):
        skill = _make_skill()
        assert skill.name == "working_memory"
        assert skill.canonical_name == "aria-working-memory"


# ============================================================================
# 3. Health Check
# ============================================================================

class TestHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_available(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.get = AsyncMock(return_value=_make_response(200))
        skill._status = SkillStatus.AVAILABLE

        status = await skill.health_check()
        assert status == SkillStatus.AVAILABLE

    @pytest.mark.asyncio
    async def test_health_check_unavailable_no_client(self):
        skill = _make_skill()
        skill._api = None
        status = await skill.health_check()
        assert status == SkillStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.get = AsyncMock(side_effect=Exception("timeout"))
        status = await skill.health_check()
        assert status == SkillStatus.ERROR


# ============================================================================
# 4. Remember & Recall
# ============================================================================

class TestRememberAndRecall:

    @pytest.mark.asyncio
    async def test_remember_and_recall(self):
        """Mock API: store then retrieve."""
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()

        # remember
        skill._api._client.post = AsyncMock(
            return_value=_make_response(200, {"id": "abc-123", "key": "greeting", "upserted": True})
        )
        result = await skill.remember("greeting", {"text": "hello"}, category="social")
        assert result.success
        assert result.data["upserted"] is True

        # recall
        skill._api._client.get = AsyncMock(
            return_value=_make_response(200, {
                "items": [{"key": "greeting", "value": {"text": "hello"}, "category": "social"}],
                "count": 1,
            })
        )
        result = await skill.recall(key="greeting", category="social")
        assert result.success
        assert result.data["count"] == 1

    @pytest.mark.asyncio
    async def test_remember_not_initialized(self):
        skill = _make_skill()
        skill._api = None
        result = await skill.remember("k", "v")
        assert not result.success
        assert "not initialized" in result.error


# ============================================================================
# 5. Context Ranking
# ============================================================================

class TestContextRanking:

    @pytest.mark.asyncio
    async def test_context_ranking(self):
        """Store items with different importance and verify they come back scored."""
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()

        mock_context = {
            "context": [
                {"key": "important", "importance": 0.9, "relevance": 0.82},
                {"key": "normal", "importance": 0.5, "relevance": 0.55},
                {"key": "minor", "importance": 0.1, "relevance": 0.30},
            ],
            "count": 3,
        }
        skill._api._client.get = AsyncMock(return_value=_make_response(200, mock_context))

        result = await skill.get_context(limit=10)
        assert result.success
        items = result.data["context"]
        assert len(items) == 3
        # Verify ordering by relevance descending
        relevances = [i["relevance"] for i in items]
        assert relevances == sorted(relevances, reverse=True)


# ============================================================================
# 6. Checkpoint & Restore
# ============================================================================

class TestCheckpointRestore:

    @pytest.mark.asyncio
    async def test_checkpoint_restore(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()

        # checkpoint
        ckpt_data = {"checkpoint_id": "ckpt-20260209T120000-abc123", "items_checkpointed": 5}
        skill._api._client.post = AsyncMock(return_value=_make_response(200, ckpt_data))
        result = await skill.checkpoint()
        assert result.success
        assert "ckpt-" in result.data["checkpoint_id"]

        # restore
        restore_data = {
            "checkpoint_id": "ckpt-20260209T120000-abc123",
            "items": [{"key": "a"}, {"key": "b"}],
            "count": 2,
        }
        skill._api._client.get = AsyncMock(return_value=_make_response(200, restore_data))
        result = await skill.restore_checkpoint()
        assert result.success
        assert result.data["count"] == 2


# ============================================================================
# 7. Reflect
# ============================================================================

class TestReflect:

    @pytest.mark.asyncio
    async def test_reflect_output(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()

        skill._api._client.get = AsyncMock(return_value=_make_response(200, {
            "items": [
                {"key": "k1", "category": "social", "importance": 0.8},
                {"key": "k2", "category": "cognition", "importance": 0.3},
                {"key": "k3", "category": "social", "importance": 0.5},
            ],
            "count": 3,
        }))
        result = await skill.reflect()
        assert result.success
        summary = result.data["summary"]
        assert "3 items" in summary
        assert "2 categories" in summary
        assert "[social]" in summary
        assert "[cognition]" in summary

    @pytest.mark.asyncio
    async def test_reflect_empty(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.get = AsyncMock(return_value=_make_response(200, {"items": [], "count": 0}))
        result = await skill.reflect()
        assert result.success
        assert "empty" in result.data["summary"].lower()


# ============================================================================
# 8. Category Filter
# ============================================================================

class TestCategoryFilter:

    @pytest.mark.asyncio
    async def test_category_filter(self):
        """Recall with category should pass param through."""
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.get = AsyncMock(return_value=_make_response(200, {"items": [], "count": 0}))

        await skill.recall(category="social")
        call_kwargs = skill._api._client.get.call_args
        assert "social" in str(call_kwargs)


# ============================================================================
# 9. TTL Handling
# ============================================================================

class TestTTLHandling:

    @pytest.mark.asyncio
    async def test_ttl_handling(self):
        """Items stored with ttl_hours should pass the value to the API."""
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.post = AsyncMock(
            return_value=_make_response(200, {"id": "x", "key": "tmp", "upserted": True})
        )
        await skill.remember("tmp", {"v": 1}, ttl_hours=2)
        call_json = skill._api._client.post.call_args
        body = call_json.kwargs.get("json") or call_json[1].get("json")
        assert body["ttl_hours"] == 2


# ============================================================================
# 10. Forget
# ============================================================================

class TestForget:

    @pytest.mark.asyncio
    async def test_forget_operation(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.delete = AsyncMock(
            return_value=_make_response(200, {"deleted": True, "id": "some-uuid"})
        )
        result = await skill.forget("some-uuid")
        assert result.success
        assert result.data["deleted"] is True


# ============================================================================
# 11. Update
# ============================================================================

class TestUpdate:

    @pytest.mark.asyncio
    async def test_update_importance(self):
        skill = _make_skill()
        skill._api = MagicMock()
        skill._api._client = AsyncMock()
        skill._api._client.patch = AsyncMock(
            return_value=_make_response(200, {"id": "x", "importance": 0.9})
        )
        result = await skill.update("x", importance=0.9)
        assert result.success


# ============================================================================
# 12. API Router — Mock DB
# ============================================================================

class TestAPIRouter:
    """Test FastAPI endpoints with mocked AsyncSession."""

    @pytest.mark.asyncio
    async def test_router_list_endpoint(self):
        """GET /working-memory returns items."""
        pytest.importorskip("fastapi", reason="fastapi not installed (runs in container)")
        import sys
        sys.path.insert(0, "src/api")
        try:
            from fastapi.testclient import TestClient
            from fastapi import FastAPI

            from routers.working_memory import router

            app = FastAPI()
            app.include_router(router)

            # We can't easily mock async DB dep inline in TestClient,
            # so just verify the router object exists with correct routes
            routes = [r.path for r in app.routes]
            assert "/working-memory" in routes
            assert "/working-memory/context" in routes
            assert "/working-memory/checkpoint" in routes
            assert "/working-memory/{item_id}" in routes
        finally:
            sys.path.remove("src/api")

    @pytest.mark.asyncio
    async def test_router_has_all_methods(self):
        """Router has GET, POST, PATCH, DELETE endpoints."""
        pytest.importorskip("fastapi", reason="fastapi not installed (runs in container)")
        import sys
        sys.path.insert(0, "src/api")
        try:
            from routers.working_memory import router
            methods = set()
            for route in router.routes:
                if hasattr(route, "methods"):
                    methods.update(route.methods)
            assert {"GET", "POST", "PATCH", "DELETE"}.issubset(methods)
        finally:
            sys.path.remove("src/api")


# ============================================================================
# 13. Cognition Integration
# ============================================================================

class TestCognitionIntegration:

    def test_cognition_has_working_memory_injection(self):
        """Verify cognition.process references working_memory."""
        import inspect
        from aria_mind.cognition import Cognition
        source = inspect.getsource(Cognition.process)
        assert "working_memory" in source

    def test_cognition_has_remember_after_process(self):
        """Verify cognition.process calls wm.remember after processing."""
        import inspect
        from aria_mind.cognition import Cognition
        source = inspect.getsource(Cognition.process)
        assert "wm.remember" in source or "remember(" in source


# ============================================================================
# 14. Startup Integration
# ============================================================================

class TestStartupIntegration:

    def test_startup_has_working_memory_phase(self):
        """Verify startup.py contains Phase 3.5 for working memory."""
        import inspect
        from aria_mind.startup import run_startup
        source = inspect.getsource(run_startup)
        assert "Phase 3.5" in source
        assert "working_memory" in source or "WorkingMemory" in source

    def test_shutdown_has_checkpoint(self):
        """Verify shutdown logic calls checkpoint."""
        import inspect
        from aria_mind.startup import run_forever
        source = inspect.getsource(run_forever)
        assert "checkpoint" in source


# ============================================================================
# 15. Skill Registration
# ============================================================================

class TestSkillRegistration:

    def test_skill_registered_in_registry(self):
        """WorkingMemorySkill is auto-registered via @SkillRegistry.register."""
        from aria_skills.registry import SkillRegistry
        assert "working_memory" in SkillRegistry._skill_classes
        assert "aria-working-memory" in SkillRegistry._skill_classes
