# S10-05: Unit Tests for NativeSessionManager
**Epic:** E8 — Quality & Testing | **Priority:** P0 | **Points:** 2 | **Phase:** 10

## Problem
`aria_engine/session_manager.py` replaces OpenClaw's filesystem-based sessions with PostgreSQL-native session management. It handles CRUD, auto-session creation, session protection, rate limiting, and history pagination. No unit tests exist for these critical data-integrity operations.

## Root Cause
NativeSessionManager was built in Sprint 5 as a rewrite of the old `session_manager` skill. Testing was deferred because it requires async DB mocking.

## Fix
### `tests/unit/test_session_manager.py`
```python
"""
Unit tests for aria_engine.session_manager.NativeSessionManager.

Tests:
- CRUD operations (create, read, update, delete)
- Auto-session (create on first message, close on inactivity)
- Session protection (prevent deletion of active sessions)
- Rate limiting
- History pagination
- Search
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.config import EngineConfig
from aria_engine.session_manager import NativeSessionManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        database_url="postgresql+asyncpg://test:test@localhost:5432/aria_test",
        litellm_base_url="http://localhost:4000",
        litellm_master_key="sk-test",
        default_model="step-35-flash-free",
    )


@pytest.fixture
def mock_db():
    """Mock async database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.__aenter__ = AsyncMock(return_value=db)
    db.__aexit__ = AsyncMock(return_value=False)
    return db


@pytest.fixture
def session_mgr(config: EngineConfig, mock_db) -> NativeSessionManager:
    """Create NativeSessionManager with mocked DB."""
    mgr = NativeSessionManager(config)
    mgr._get_db_session = AsyncMock(return_value=mock_db)
    return mgr


@pytest.fixture
def sample_session() -> dict[str, Any]:
    """A sample session dict as returned from DB."""
    return {
        "id": str(uuid.uuid4()),
        "agent_id": "main",
        "session_type": "interactive",
        "title": "Test Session",
        "model": "step-35-flash-free",
        "temperature": 0.7,
        "max_tokens": 4096,
        "context_window": 50,
        "status": "active",
        "message_count": 10,
        "total_tokens": 5000,
        "total_cost": 0.05,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": None,
    }


# ============================================================================
# CRUD Tests
# ============================================================================

class TestCRUD:
    """Tests for basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_session(self, session_mgr: NativeSessionManager, mock_db):
        """Create a new session with default values."""
        with patch.object(session_mgr, "_insert_session", new_callable=AsyncMock) as mock_insert:
            mock_insert.return_value = {
                "id": str(uuid.uuid4()),
                "agent_id": "main",
                "session_type": "interactive",
                "status": "active",
                "message_count": 0,
            }

            session = await session_mgr.create_session()

            assert session["agent_id"] == "main"
            assert session["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_session_with_agent(self, session_mgr: NativeSessionManager):
        """Create a session for a specific agent."""
        with patch.object(session_mgr, "_insert_session", new_callable=AsyncMock) as mock_insert:
            mock_insert.return_value = {
                "id": str(uuid.uuid4()),
                "agent_id": "researcher",
                "session_type": "cron",
                "model": "qwen3-mlx",
                "status": "active",
            }

            session = await session_mgr.create_session(
                agent_id="researcher",
                session_type="cron",
                model="qwen3-mlx",
            )

            assert session["agent_id"] == "researcher"
            assert session["model"] == "qwen3-mlx"

    @pytest.mark.asyncio
    async def test_get_session(self, session_mgr: NativeSessionManager, sample_session):
        """Retrieve a session by ID."""
        with patch.object(session_mgr, "_fetch_session", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_session

            session = await session_mgr.get_session(sample_session["id"])

            assert session["id"] == sample_session["id"]
            assert session["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, session_mgr: NativeSessionManager):
        """Getting a nonexistent session returns None."""
        with patch.object(session_mgr, "_fetch_session", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None

            session = await session_mgr.get_session(str(uuid.uuid4()))

            assert session is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, session_mgr: NativeSessionManager, sample_session):
        """List all sessions with pagination."""
        with patch.object(session_mgr, "_fetch_sessions", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {
                "sessions": [sample_session],
                "total": 1,
                "page": 1,
                "limit": 20,
            }

            result = await session_mgr.list_sessions(page=1, limit=20)

            assert result["total"] == 1
            assert len(result["sessions"]) == 1

    @pytest.mark.asyncio
    async def test_update_session(self, session_mgr: NativeSessionManager, sample_session):
        """Update session fields."""
        with patch.object(session_mgr, "_update_session_fields", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = {**sample_session, "title": "Updated Title"}

            session = await session_mgr.update_session(
                sample_session["id"],
                title="Updated Title",
            )

            assert session["title"] == "Updated Title"


# ============================================================================
# Session Protection Tests
# ============================================================================

class TestSessionProtection:
    """Tests for session protection rules."""

    @pytest.mark.asyncio
    async def test_cannot_delete_active_session(self, session_mgr: NativeSessionManager, sample_session):
        """Active sessions cannot be deleted."""
        with patch.object(session_mgr, "_fetch_session", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {**sample_session, "status": "active"}

            with pytest.raises(ValueError, match="Cannot delete active session"):
                await session_mgr.delete_session(sample_session["id"])

    @pytest.mark.asyncio
    async def test_can_delete_ended_session(self, session_mgr: NativeSessionManager, sample_session):
        """Ended sessions can be deleted."""
        with patch.object(session_mgr, "_fetch_session", new_callable=AsyncMock) as mock_fetch, \
             patch.object(session_mgr, "_delete_session_from_db", new_callable=AsyncMock) as mock_del:
            mock_fetch.return_value = {**sample_session, "status": "ended"}
            mock_del.return_value = True

            result = await session_mgr.delete_session(sample_session["id"])

            assert result is True
            mock_del.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_session_sets_ended_at(self, session_mgr: NativeSessionManager, sample_session):
        """Ending a session sets status='ended' and ended_at timestamp."""
        with patch.object(session_mgr, "_fetch_session", new_callable=AsyncMock) as mock_fetch, \
             patch.object(session_mgr, "_update_session_fields", new_callable=AsyncMock) as mock_update:
            mock_fetch.return_value = sample_session
            mock_update.return_value = {
                **sample_session,
                "status": "ended",
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }

            session = await session_mgr.end_session(sample_session["id"])

            assert session["status"] == "ended"
            assert session["ended_at"] is not None


# ============================================================================
# Auto-Session Tests
# ============================================================================

class TestAutoSession:
    """Tests for automatic session management."""

    @pytest.mark.asyncio
    async def test_auto_create_on_no_active(self, session_mgr: NativeSessionManager):
        """Auto-session creates a new session if no active one exists for the agent."""
        with patch.object(session_mgr, "_find_active_session", new_callable=AsyncMock) as mock_find, \
             patch.object(session_mgr, "_insert_session", new_callable=AsyncMock) as mock_insert:
            mock_find.return_value = None
            mock_insert.return_value = {
                "id": str(uuid.uuid4()),
                "agent_id": "main",
                "status": "active",
            }

            session = await session_mgr.get_or_create_session(agent_id="main")

            assert session["status"] == "active"
            mock_insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_reuse_existing_active(self, session_mgr: NativeSessionManager, sample_session):
        """Auto-session reuses an existing active session for the agent."""
        with patch.object(session_mgr, "_find_active_session", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = sample_session

            session = await session_mgr.get_or_create_session(agent_id="main")

            assert session["id"] == sample_session["id"]


# ============================================================================
# Rate Limiting Tests
# ============================================================================

class TestRateLimiting:
    """Tests for session creation rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, session_mgr: NativeSessionManager):
        """Cannot create more than N sessions per minute."""
        session_mgr._rate_limit_per_minute = 3

        with patch.object(session_mgr, "_count_recent_sessions", new_callable=AsyncMock) as mock_count, \
             patch.object(session_mgr, "_insert_session", new_callable=AsyncMock) as mock_insert:
            mock_count.return_value = 3  # Already at limit
            mock_insert.return_value = {"id": str(uuid.uuid4()), "status": "active"}

            with pytest.raises(ValueError, match="Rate limit exceeded"):
                await session_mgr.create_session()

    @pytest.mark.asyncio
    async def test_under_rate_limit_allowed(self, session_mgr: NativeSessionManager):
        """Session creation allowed when under rate limit."""
        session_mgr._rate_limit_per_minute = 10

        with patch.object(session_mgr, "_count_recent_sessions", new_callable=AsyncMock) as mock_count, \
             patch.object(session_mgr, "_insert_session", new_callable=AsyncMock) as mock_insert:
            mock_count.return_value = 2  # Under limit
            mock_insert.return_value = {
                "id": str(uuid.uuid4()),
                "agent_id": "main",
                "status": "active",
            }

            session = await session_mgr.create_session()
            assert session["status"] == "active"


# ============================================================================
# History & Search Tests
# ============================================================================

class TestHistoryAndSearch:
    """Tests for message history and search."""

    @pytest.mark.asyncio
    async def test_get_history_paginated(self, session_mgr: NativeSessionManager, sample_session):
        """Message history supports pagination."""
        messages = [
            {"role": "user", "content": f"Message {i}", "created_at": datetime.now(timezone.utc).isoformat()}
            for i in range(50)
        ]

        with patch.object(session_mgr, "_fetch_messages", new_callable=AsyncMock) as mock_msgs:
            mock_msgs.return_value = {
                "messages": messages[:20],
                "total": 50,
                "page": 1,
                "limit": 20,
            }

            result = await session_mgr.get_history(
                session_id=sample_session["id"],
                page=1,
                limit=20,
            )

            assert result["total"] == 50
            assert len(result["messages"]) == 20
            assert result["page"] == 1

    @pytest.mark.asyncio
    async def test_search_sessions(self, session_mgr: NativeSessionManager):
        """Search sessions by keyword."""
        with patch.object(session_mgr, "_search_sessions_db", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "sessions": [{"id": "s1", "title": "Python Discussion"}],
                "total": 1,
            }

            result = await session_mgr.search_sessions(query="Python")

            assert result["total"] == 1
            assert "Python" in result["sessions"][0]["title"]

    @pytest.mark.asyncio
    async def test_search_empty_results(self, session_mgr: NativeSessionManager):
        """Search with no matches returns empty list."""
        with patch.object(session_mgr, "_search_sessions_db", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "sessions": [],
                "total": 0,
            }

            result = await session_mgr.search_sessions(query="nonexistent_xyz_123")

            assert result["total"] == 0
            assert result["sessions"] == []
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Session manager at engine layer |
| 2 | .env for secrets (zero in code) | ✅ | Test config uses dummy credentials |
| 3 | models.yaml single source of truth | ❌ | Session manager doesn't resolve models |
| 4 | Docker-first testing | ✅ | Tests run in Docker CI |
| 5 | aria_memories only writable path | ❌ | Tests only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S5-01 must complete first (NativeSessionManager exists)
- S10-01 should complete first (shared conftest fixtures)

## Verification
```bash
# 1. Run tests:
pytest tests/unit/test_session_manager.py -v
# EXPECTED: All tests pass

# 2. Coverage:
pytest tests/unit/test_session_manager.py --cov=aria_engine.session_manager --cov-report=term-missing
# EXPECTED: >85% coverage

# 3. Import check:
python -c "import tests.unit.test_session_manager; print('OK')"
# EXPECTED: OK
```

## Prompt for Agent
```
Write unit tests for aria_engine.session_manager.NativeSessionManager.

FILES TO READ FIRST:
- aria_engine/session_manager.py (full file)
- aria_engine/config.py (EngineConfig)
- tests/conftest.py (shared fixtures)

STEPS:
1. Read all files above
2. Create tests/unit/test_session_manager.py
3. Mock all DB operations
4. Test CRUD, protection, auto-session, rate limiting, pagination, search
5. Run pytest and verify all tests pass

CONSTRAINTS:
- Mock DB — no real PostgreSQL
- Test session protection (cannot delete active)
- Test rate limiting
- Test pagination with total counts
```
