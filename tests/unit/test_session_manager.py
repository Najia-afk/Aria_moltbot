"""
Unit tests for aria_engine.session_manager.NativeSessionManager.

Tests:
- CRUD operations (create, read, update, delete)
- Message operations (add, get, delete)
- Session listing with search & pagination
- Session ending
- Pruning old sessions
- Stats
"""
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_engine.exceptions import EngineError
from aria_engine.session_manager import NativeSessionManager


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_engine() -> AsyncMock:
    """Mock SQLAlchemy async engine."""
    engine = AsyncMock()
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    engine.begin = MagicMock(return_value=conn)
    return engine


@pytest.fixture
def session_mgr(mock_db_engine) -> NativeSessionManager:
    """Create NativeSessionManager with mocked DB."""
    return NativeSessionManager(mock_db_engine)


def _make_session_row(
    session_id: str = "abc123",
    title: str = "Test Session",
    agent_id: str = "main",
    session_type: str = "chat",
    message_count: int = 5,
) -> dict[str, Any]:
    """Create a fake DB row dict for a session."""
    now = datetime.now(timezone.utc)
    return {
        "session_id": session_id,
        "title": title,
        "agent_id": agent_id,
        "session_type": session_type,
        "metadata": None,
        "message_count": message_count,
        "created_at": now,
        "updated_at": now,
        "last_message_at": now,
    }


def _make_message_row(
    msg_id: int = 1,
    session_id: str = "abc123",
    role: str = "user",
    content: str = "Hello",
) -> dict[str, Any]:
    """Create a fake DB row dict for a message."""
    return {
        "id": msg_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "agent_id": None,
        "metadata": None,
        "created_at": datetime.now(timezone.utc),
    }


# ============================================================================
# Session CRUD Tests
# ============================================================================

class TestSessionCRUD:
    """Tests for basic session CRUD operations."""

    async def test_create_session_defaults(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Create a new session with default values."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        now = datetime.now(timezone.utc)
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = {
            "session_id": "test_id",
            "title": "Session test_id",
            "agent_id": "main",
            "session_type": "chat",
            "created_at": now,
        }
        conn.execute = AsyncMock(return_value=result_mock)

        session = await session_mgr.create_session()

        assert session["session_id"] == "test_id"
        assert session["agent_id"] == "main"
        assert session["message_count"] == 0

    async def test_create_session_with_agent(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Create a session for a specific agent."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        now = datetime.now(timezone.utc)
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = {
            "session_id": "r_id",
            "title": "Research",
            "agent_id": "researcher",
            "session_type": "cron",
            "created_at": now,
        }
        conn.execute = AsyncMock(return_value=result_mock)

        session = await session_mgr.create_session(
            agent_id="researcher",
            session_type="cron",
            title="Research",
        )

        assert session["agent_id"] == "researcher"

    async def test_get_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Retrieve a session by ID."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        row = _make_session_row()
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = row
        conn.execute = AsyncMock(return_value=result_mock)

        session = await session_mgr.get_session("abc123")

        assert session is not None
        assert session["session_id"] == "abc123"
        assert session["title"] == "Test Session"

    async def test_get_nonexistent_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Getting a nonexistent session returns None."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = None
        conn.execute = AsyncMock(return_value=result_mock)

        session = await session_mgr.get_session("nonexistent")
        assert session is None

    async def test_update_session_title(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Update session title."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # First call: UPDATE returning session_id
        update_result = MagicMock()
        update_result.first.return_value = MagicMock()  # truthy = found

        # Second call: get_session re-fetches
        row = _make_session_row(title="Updated Title")
        get_result = MagicMock()
        get_result.mappings.return_value.first.return_value = row

        conn.execute = AsyncMock(side_effect=[update_result, get_result])

        session = await session_mgr.update_session("abc123", title="Updated Title")

        assert session is not None
        assert session["title"] == "Updated Title"

    async def test_delete_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Delete a session and its messages."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # Messages delete, then session delete returning row
        msg_result = MagicMock()
        session_result = MagicMock()
        session_result.first.return_value = MagicMock()  # truthy = found
        conn.execute = AsyncMock(side_effect=[msg_result, session_result])

        deleted = await session_mgr.delete_session("abc123")
        assert deleted is True

    async def test_delete_nonexistent_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Deleting a nonexistent session returns False."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        msg_result = MagicMock()
        session_result = MagicMock()
        session_result.first.return_value = None  # Not found
        conn.execute = AsyncMock(side_effect=[msg_result, session_result])

        deleted = await session_mgr.delete_session("nonexistent")
        assert deleted is False


# ============================================================================
# Session End Tests
# ============================================================================

class TestSessionEnd:
    """Tests for ending sessions."""

    async def test_end_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Ending a session marks it with ended metadata."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.first.return_value = MagicMock()  # truthy
        conn.execute = AsyncMock(return_value=result_mock)

        result = await session_mgr.end_session("abc123")
        assert result is True

    async def test_end_nonexistent_session(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Ending a non-existent session returns False."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.first.return_value = None
        conn.execute = AsyncMock(return_value=result_mock)

        result = await session_mgr.end_session("nonexistent")
        assert result is False


# ============================================================================
# List Sessions Tests
# ============================================================================

class TestListSessions:
    """Tests for listing sessions with filters and pagination."""

    async def test_list_sessions(self, session_mgr: NativeSessionManager, mock_db_engine):
        """List all sessions with pagination."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # Count query, then data query
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        row = _make_session_row()
        data_result = MagicMock()
        data_result.mappings.return_value.all.return_value = [row]

        conn.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await session_mgr.list_sessions(limit=20)

        assert result["total"] == 1
        assert len(result["sessions"]) == 1
        assert result["limit"] == 20

    async def test_list_sessions_with_agent_filter(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Filter sessions by agent_id."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.mappings.return_value.all.return_value = []

        conn.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await session_mgr.list_sessions(agent_id="researcher")

        assert result["total"] == 0

    async def test_list_sessions_clamps_limit(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Limit is clamped to MAX_PAGE_SIZE (100)."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        count_result = MagicMock()
        count_result.scalar.return_value = 0

        data_result = MagicMock()
        data_result.mappings.return_value.all.return_value = []

        conn.execute = AsyncMock(side_effect=[count_result, data_result])

        result = await session_mgr.list_sessions(limit=999)

        assert result["limit"] == 100


# ============================================================================
# Message Operations Tests
# ============================================================================

class TestMessageOperations:
    """Tests for adding and getting messages."""

    async def test_add_message(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Add a message to a session."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        # Check session exists, then insert message, then update session
        check_result = MagicMock()
        check_result.first.return_value = MagicMock()  # session exists

        now = datetime.now(timezone.utc)
        insert_result = MagicMock()
        insert_result.mappings.return_value.first.return_value = {
            "id": 42,
            "session_id": "abc123",
            "role": "user",
            "content": "Hello!",
            "agent_id": None,
            "created_at": now,
        }

        update_result = MagicMock()  # session updated_at touch

        conn.execute = AsyncMock(side_effect=[check_result, insert_result, update_result])

        msg = await session_mgr.add_message(
            session_id="abc123",
            role="user",
            content="Hello!",
        )

        assert msg["role"] == "user"
        assert msg["content"] == "Hello!"
        assert msg["session_id"] == "abc123"

    async def test_add_message_to_nonexistent_session(
        self, session_mgr: NativeSessionManager, mock_db_engine
    ):
        """Adding a message to a nonexistent session raises EngineError."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        check_result = MagicMock()
        check_result.first.return_value = None  # session not found

        conn.execute = AsyncMock(return_value=check_result)

        with pytest.raises(EngineError, match="not found"):
            await session_mgr.add_message(
                session_id="nonexistent",
                role="user",
                content="test",
            )

    async def test_get_messages(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Get messages for a session."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        rows = [
            _make_message_row(msg_id=1, content="Hello"),
            _make_message_row(msg_id=2, role="assistant", content="Hi!"),
        ]
        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = rows
        conn.execute = AsyncMock(return_value=result_mock)

        messages = await session_mgr.get_messages("abc123")

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    async def test_delete_message(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Delete a single message."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.first.return_value = MagicMock()  # found
        conn.execute = AsyncMock(return_value=result_mock)

        deleted = await session_mgr.delete_message(42, "abc123")
        assert deleted is True


# ============================================================================
# Stats Tests
# ============================================================================

class TestStats:
    """Tests for session statistics."""

    async def test_get_stats(self, session_mgr: NativeSessionManager, mock_db_engine):
        """get_stats returns aggregate session statistics."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        now = datetime.now(timezone.utc)
        result_mock = MagicMock()
        result_mock.mappings.return_value.first.return_value = {
            "total_sessions": 10,
            "total_messages": 500,
            "active_agents": 3,
            "oldest_session": now - timedelta(days=30),
            "newest_activity": now,
        }
        conn.execute = AsyncMock(return_value=result_mock)

        stats = await session_mgr.get_stats()

        assert stats["total_sessions"] == 10
        assert stats["total_messages"] == 500
        assert stats["active_agents"] == 3


# ============================================================================
# Pruning Tests
# ============================================================================

class TestPruning:
    """Tests for pruning old sessions."""

    async def test_prune_dry_run(self, session_mgr: NativeSessionManager, mock_db_engine):
        """Dry run counts but doesn't delete."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = [
            {"session_id": "old1", "msg_count": 10},
            {"session_id": "old2", "msg_count": 20},
        ]
        conn.execute = AsyncMock(return_value=result_mock)

        result = await session_mgr.prune_old_sessions(days=30, dry_run=True)

        assert result["pruned_count"] == 2
        assert result["message_count"] == 30
        assert result["dry_run"] is True

    async def test_prune_no_stale_sessions(self, session_mgr: NativeSessionManager, mock_db_engine):
        """When no stale sessions exist, nothing is deleted."""
        conn = mock_db_engine.begin.return_value
        conn.__aenter__ = AsyncMock(return_value=conn)

        result_mock = MagicMock()
        result_mock.mappings.return_value.all.return_value = []
        conn.execute = AsyncMock(return_value=result_mock)

        result = await session_mgr.prune_old_sessions(days=30)

        assert result["pruned_count"] == 0
