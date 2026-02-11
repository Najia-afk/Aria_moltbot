# tests/test_memory_module.py
"""Tests for aria_mind/memory.py — MemoryManager short-term, long-term & artifacts."""
import json
import os
from collections import deque
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

pytestmark = pytest.mark.unit


# ── Helper ─────────────────────────────────────────────────────────────


def _make_manager(db=None):
    from aria_mind.memory import MemoryManager
    return MemoryManager(db_skill=db)


# ── Construction ───────────────────────────────────────────────────────


class TestMemoryManagerInit:
    """Test MemoryManager construction."""

    def test_defaults(self):
        mm = _make_manager()
        assert mm._db is None
        assert mm._connected is False
        assert isinstance(mm._short_term, deque)
        assert mm._max_short_term == 200

    def test_set_database(self):
        mm = _make_manager()
        db = MagicMock()
        mm.set_database(db)
        assert mm._db is db


# ── connect / disconnect ──────────────────────────────────────────────


class TestConnection:

    async def test_connect_without_db(self):
        mm = _make_manager()
        result = await mm.connect()
        assert result is True
        assert mm._connected is True

    async def test_connect_with_db_success(self):
        db = AsyncMock()
        db.is_available = True
        mm = _make_manager(db=db)
        result = await mm.connect()
        db.initialize.assert_awaited_once()
        assert result is True

    async def test_connect_with_db_failure(self):
        db = AsyncMock()
        db.initialize.side_effect = Exception("connection refused")
        mm = _make_manager(db=db)
        result = await mm.connect()
        assert result is False

    async def test_disconnect(self):
        db = AsyncMock()
        mm = _make_manager(db=db)
        mm._connected = True
        await mm.disconnect()
        db.close.assert_awaited_once()
        assert mm._connected is False


# ── Short-term memory ─────────────────────────────────────────────────


class TestShortTermMemory:

    def test_remember_short(self):
        mm = _make_manager()
        mm.remember_short("hello", "greeting")
        entries = mm.recall_short()
        assert len(entries) == 1
        assert entries[0]["content"] == "hello"
        assert entries[0]["category"] == "greeting"
        assert "timestamp" in entries[0]

    def test_recall_short_limit(self):
        mm = _make_manager()
        for i in range(20):
            mm.remember_short(f"item-{i}")
        recent = mm.recall_short(limit=5)
        assert len(recent) == 5
        assert recent[-1]["content"] == "item-19"

    def test_clear_short(self):
        mm = _make_manager()
        mm.remember_short("data")
        mm.clear_short()
        assert len(mm.recall_short()) == 0

    def test_clear_short_preserves_deque_maxlen(self):
        mm = _make_manager()
        mm.remember_short("data")
        mm.clear_short()
        assert isinstance(mm._short_term, deque)
        assert mm._short_term.maxlen == mm._max_short_term

    def test_deque_auto_trims(self):
        mm = _make_manager()
        mm._max_short_term = 5
        mm._short_term = deque(maxlen=5)
        for i in range(10):
            mm.remember_short(f"item-{i}")
        assert len(mm._short_term) == 5


# ── Long-term memory (database-backed) ────────────────────────────────


class TestLongTermMemory:

    async def test_remember_no_db(self):
        mm = _make_manager()
        result = await mm.remember("key", "value")
        assert result is False

    async def test_remember_with_db(self):
        db = AsyncMock()
        db.store_memory.return_value = MagicMock(success=True)
        mm = _make_manager(db=db)
        result = await mm.remember("key", "value", category="test")
        assert result is True
        db.store_memory.assert_awaited_once_with("key", "value", "test")

    async def test_recall_no_db(self):
        mm = _make_manager()
        result = await mm.recall("key")
        assert result is None

    async def test_recall_with_db(self):
        db = AsyncMock()
        db.recall_memory.return_value = MagicMock(success=True, data={"value": 42})
        mm = _make_manager(db=db)
        result = await mm.recall("key")
        assert result == 42

    async def test_recall_not_found(self):
        db = AsyncMock()
        db.recall_memory.return_value = MagicMock(success=False, data=None)
        mm = _make_manager(db=db)
        result = await mm.recall("missing")
        assert result is None

    async def test_search_no_db(self):
        mm = _make_manager()
        result = await mm.search("pattern")
        assert result == []

    async def test_search_with_db(self):
        db = AsyncMock()
        db.search_memories.return_value = MagicMock(success=True, data=[{"key": "a"}])
        mm = _make_manager(db=db)
        result = await mm.search("pattern", category="test", limit=5)
        assert len(result) == 1
        db.search_memories.assert_awaited_once_with("pattern", "test", 5)


# ── Thoughts ───────────────────────────────────────────────────────────


class TestThoughts:

    async def test_log_thought_without_db(self):
        mm = _make_manager()
        result = await mm.log_thought("I wonder…")
        assert result is True
        # Should also land in short-term
        assert len(mm.recall_short()) == 1

    async def test_log_thought_with_db(self):
        db = AsyncMock()
        db.log_thought.return_value = MagicMock(success=True)
        mm = _make_manager(db=db)
        result = await mm.log_thought("thinking…", category="reflection")
        assert result is True
        db.log_thought.assert_awaited_once_with("thinking…", "reflection")

    async def test_get_recent_thoughts_no_db(self):
        mm = _make_manager()
        mm.remember_short("thought 1", "reflection")
        mm.remember_short("noise", "context")
        mm.remember_short("thought 2", "thought")
        thoughts = await mm.get_recent_thoughts(limit=10)
        assert len(thoughts) == 2  # only reflection / thought categories

    async def test_get_recent_thoughts_with_db(self):
        db = AsyncMock()
        db.get_recent_thoughts.return_value = MagicMock(success=True, data=[{"content": "ok"}])
        mm = _make_manager(db=db)
        thoughts = await mm.get_recent_thoughts(limit=5)
        assert len(thoughts) == 1


# ── File artifacts ─────────────────────────────────────────────────────


class TestArtifacts:

    def test_save_artifact(self, tmp_path):
        mm = _make_manager()
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.save_artifact("hello world", "note.md", category="plans")
            assert result["success"] is True
            assert (tmp_path / "plans" / "note.md").read_text() == "hello world"

    def test_save_artifact_with_subfolder(self, tmp_path):
        mm = _make_manager()
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.save_artifact("data", "file.txt", category="logs", subfolder="sub")
            assert result["success"] is True
            assert (tmp_path / "logs" / "sub" / "file.txt").exists()

    def test_load_artifact(self, tmp_path):
        mm = _make_manager()
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "note.md").write_text("content here")
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.load_artifact("note.md", category="plans")
            assert result["success"] is True
            assert result["content"] == "content here"

    def test_load_artifact_missing(self, tmp_path):
        mm = _make_manager()
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.load_artifact("missing.md", category="plans")
            assert result["success"] is False

    def test_list_artifacts(self, tmp_path):
        mm = _make_manager()
        category_dir = tmp_path / "exports"
        category_dir.mkdir()
        (category_dir / "a.json").write_text("{}")
        (category_dir / "b.json").write_text("{}")
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            files = mm.list_artifacts(category="exports")
            assert len(files) == 2
            names = {f["name"] for f in files}
            assert names == {"a.json", "b.json"}

    def test_list_artifacts_empty_dir(self, tmp_path):
        mm = _make_manager()
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            files = mm.list_artifacts(category="nonexistent")
            assert files == []


# ── JSON artifacts ─────────────────────────────────────────────────────


class TestJsonArtifacts:

    def test_save_json_artifact(self, tmp_path):
        mm = _make_manager()
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.save_json_artifact({"key": "value"}, "data", category="exports")
            assert result["success"] is True
            content = json.loads((tmp_path / "exports" / "data.json").read_text())
            assert content == {"key": "value"}

    def test_load_json_artifact(self, tmp_path):
        mm = _make_manager()
        (tmp_path / "exports").mkdir()
        (tmp_path / "exports" / "data.json").write_text('{"a": 1}')
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.load_json_artifact("data.json", category="exports")
            assert result["success"] is True
            assert result["data"] == {"a": 1}

    def test_load_json_artifact_invalid_json(self, tmp_path):
        mm = _make_manager()
        (tmp_path / "exports").mkdir()
        (tmp_path / "exports" / "bad.json").write_text("not json")
        with patch.object(mm, "_get_memories_path", return_value=tmp_path):
            result = mm.load_json_artifact("bad.json", category="exports")
            assert result["success"] is False
            assert "Invalid JSON" in result["error"]


# ── get_status / repr ──────────────────────────────────────────────────


class TestStatus:

    def test_get_status_keys(self):
        mm = _make_manager()
        status = mm.get_status()
        assert "connected" in status
        assert "has_database" in status
        assert "short_term_count" in status
        assert "max_short_term" in status
        assert "file_storage" in status

    def test_repr_no_db(self):
        mm = _make_manager()
        r = repr(mm)
        assert "memory-only" in r
        assert "0 short-term" in r
