# tests/test_session_manager.py
"""Tests for the session_manager skill — filesystem + PG hybrid."""
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

from aria_skills.base import SkillConfig, SkillResult
from aria_skills.session_manager import (
    SessionManagerSkill,
    _epoch_ms_to_iso,
    _flatten_sessions,
    _load_sessions_index,
    _save_sessions_index,
)

# ── Sample sessions.json data ─────────────────────────────────────────

_NOW_MS = 1749600000000  # ~2025-06-11

SAMPLE_INDEX = {
    "agent:main:cron:abc123": {
        "sessionId": "abc123",
        "updatedAt": _NOW_MS,
        "label": "cron job 1",
        "model": "gpt-4o",
        "contextTokens": 500,
    },
    "agent:main:direct:def456": {
        "sessionId": "def456",
        "updatedAt": _NOW_MS - 7200000,  # 2h old
        "label": "direct chat",
        "model": "gpt-4o",
        "contextTokens": 200,
    },
}


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def agents_dir(tmp_path):
    """Create a temp agents directory with sessions.json + .jsonl files."""
    sess_dir = tmp_path / "main" / "sessions"
    sess_dir.mkdir(parents=True)
    index_path = sess_dir / "sessions.json"
    index_path.write_text(json.dumps(SAMPLE_INDEX))
    # Create transcript files
    (sess_dir / "abc123.jsonl").write_text('{"role":"user","content":"hi"}\n')
    (sess_dir / "def456.jsonl").write_text('{"role":"user","content":"hello"}\n')
    return tmp_path


@pytest.fixture
def empty_config():
    """SkillConfig with an empty config dict."""
    return SkillConfig(name="session_manager", config={})


@pytest.fixture
def custom_config():
    """SkillConfig with custom values."""
    return SkillConfig(
        name="session_manager",
        config={
            "stale_threshold_minutes": 120,
            "api_url": "http://testhost:9999",
        },
    )


@pytest.fixture
def skill(empty_config):
    return SessionManagerSkill(empty_config)


@pytest.fixture
def custom_skill(custom_config):
    return SessionManagerSkill(custom_config)


# ── Init / config defaults ────────────────────────────────────────────


class TestInit:
    def test_init_empty_config(self, empty_config):
        s = SessionManagerSkill(empty_config)
        assert s._stale_threshold_minutes == 60
        assert "aria-api" in s._api_url or "8000" in s._api_url
        assert s._client is not None

    def test_init_custom_config(self, custom_config):
        s = SessionManagerSkill(custom_config)
        assert s._stale_threshold_minutes == 120
        assert s._api_url == "http://testhost:9999"

    def test_name_property(self, skill):
        assert skill.name == "session_manager"


# ── Helper functions ──────────────────────────────────────────────────


class TestHelpers:
    def test_epoch_ms_to_iso(self):
        result = _epoch_ms_to_iso(1749600000000)
        assert result is not None
        assert "2025" in result

    def test_epoch_ms_to_iso_none(self):
        assert _epoch_ms_to_iso(None) is None

    def test_epoch_ms_to_iso_zero(self):
        assert _epoch_ms_to_iso(0) is None

    def test_flatten_sessions_dedup(self):
        sessions = _flatten_sessions(SAMPLE_INDEX, "main")
        ids = [s["sessionId"] for s in sessions]
        assert "abc123" in ids
        assert "def456" in ids
        assert len(sessions) == 2

    def test_flatten_sessions_type_detection(self):
        sessions = _flatten_sessions(SAMPLE_INDEX, "main")
        by_id = {s["sessionId"]: s for s in sessions}
        assert by_id["abc123"]["session_type"] == "cron"
        assert by_id["def456"]["session_type"] == "direct"

    def test_load_sessions_index_missing(self, tmp_path):
        """Missing file returns empty dict."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(tmp_path)
        try:
            result = _load_sessions_index("nonexistent")
            assert result == {}
        finally:
            mod._AGENTS_DIR = orig

    def test_load_save_roundtrip(self, agents_dir):
        """Save and reload sessions.json."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        try:
            index = _load_sessions_index("main")
            assert "agent:main:cron:abc123" in index
            # Modify and save
            index["agent:main:cron:new1"] = {"sessionId": "new1", "updatedAt": 0}
            _save_sessions_index(index, "main")
            reloaded = _load_sessions_index("main")
            assert "agent:main:cron:new1" in reloaded
        finally:
            mod._AGENTS_DIR = orig


# ── list_sessions ─────────────────────────────────────────────────────


class TestListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_ok(self, skill, agents_dir):
        """Lists sessions from filesystem."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        try:
            result = await skill.list_sessions()
            assert result.success is True
            assert result.data["session_count"] == 2
        finally:
            mod._AGENTS_DIR = orig

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, skill, tmp_path):
        """Empty agents dir returns 0 sessions."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(tmp_path)
        try:
            result = await skill.list_sessions()
            assert result.success is True
            assert result.data["session_count"] == 0
        finally:
            mod._AGENTS_DIR = orig

    @pytest.mark.asyncio
    async def test_list_sessions_by_agent(self, skill, agents_dir):
        """Filter by specific agent."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        try:
            result = await skill.list_sessions(agent="main")
            assert result.success is True
            assert result.data["session_count"] == 2
        finally:
            mod._AGENTS_DIR = orig


# ── delete_session ────────────────────────────────────────────────────


class TestDeleteSession:
    @pytest.mark.asyncio
    async def test_delete_ok(self, skill, agents_dir):
        """Delete removes key from sessions.json and archives transcript."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        # Mock PG call
        skill._mark_ended_in_pg = AsyncMock(return_value=False)
        try:
            result = await skill.delete_session(session_id="abc123")
            assert result.success is True
            assert result.data["deleted"] == "abc123"
            assert result.data["transcript_archived"] is True
            # Verify key removed from index
            index = _load_sessions_index("main")
            assert "agent:main:cron:abc123" not in index
            # Verify transcript archived
            sess_dir = agents_dir / "main" / "sessions"
            assert not (sess_dir / "abc123.jsonl").exists()
            deleted_files = list(sess_dir.glob("abc123.jsonl.deleted.*"))
            assert len(deleted_files) == 1
        finally:
            mod._AGENTS_DIR = orig

    @pytest.mark.asyncio
    async def test_delete_empty_id(self, skill):
        result = await skill.delete_session(session_id="")
        assert result.success is False
        assert "required" in result.error

    @pytest.mark.asyncio
    async def test_delete_not_found(self, skill, agents_dir):
        """Deleting a non-existent session returns success (already scrapped)."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        skill._mark_ended_in_pg = AsyncMock(return_value=False)
        try:
            result = await skill.delete_session(session_id="nonexistent")
            assert result.success is True
            assert "already scrapped" in result.data["message"]
            assert result.data["removed_keys"] == []
        finally:
            mod._AGENTS_DIR = orig

    @pytest.mark.asyncio
    async def test_delete_kwarg_id(self, skill, agents_dir):
        """session_id can also be passed via **kwargs."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(agents_dir)
        skill._mark_ended_in_pg = AsyncMock(return_value=False)
        # Add a cron-keyed session for "def456" so protection doesn't block it
        idx_path = agents_dir / "main" / "sessions" / "sessions.json"
        idx = json.loads(idx_path.read_text())
        idx["agent:main:cron:def456"] = {"sessionId": "def456", "updatedAt": 1749600000000, "label": "cron-2"}
        idx_path.write_text(json.dumps(idx))
        # Remove the protected direct entry so only the cron entry matches
        del idx["agent:main:direct:def456"]
        idx_path.write_text(json.dumps(idx))
        try:
            result = await skill.delete_session(**{"session_id": "def456"})
            assert result.success is True
            assert result.data["deleted"] == "def456"
        finally:
            mod._AGENTS_DIR = orig


# ── prune_sessions ────────────────────────────────────────────────────


class TestPruneSessions:
    @pytest.mark.asyncio
    async def test_prune_dry_run(self, skill):
        """Dry-run prune should not actually delete anything."""
        mock_list = AsyncMock(
            return_value=SkillResult.ok({
                "session_count": 2,
                "sessions": [
                    {"id": "old1", "updatedAt": "2020-01-01T00:00:00Z"},
                    {"id": "new1", "updatedAt": "2099-01-01T00:00:00Z"},
                ],
            })
        )
        skill.list_sessions = mock_list

        result = await skill.prune_sessions(dry_run=True)
        assert result.success is True
        assert result.data["dry_run"] is True
        assert result.data["pruned_count"] == 1
        assert "old1" in result.data["deleted_ids"]

    @pytest.mark.asyncio
    async def test_prune_list_failure_propagates(self, skill):
        skill.list_sessions = AsyncMock(
            return_value=SkillResult.fail("cannot list")
        )
        result = await skill.prune_sessions()
        assert result.success is False


# ── close ─────────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self, skill):
        skill._client = AsyncMock()
        await skill.close()
        skill._client.aclose.assert_awaited_once()

# ── cleanup_orphans ──────────────────────────────────────────────────────────


class TestCleanupOrphans:
    @pytest.fixture
    def messy_agents_dir(self, tmp_path):
        """Create a dir with stale keys, orphan transcripts, and old .deleted files."""
        import time
        sess_dir = tmp_path / "main" / "sessions"
        sess_dir.mkdir(parents=True)
        # sessions.json with a stale key (transcript already deleted)
        index = {
            "agent:main:cron:live1": {"sessionId": "live1", "updatedAt": 1749600000000},
            "agent:main:cron:stale1": {"sessionId": "stale1", "updatedAt": 1749500000000},
        }
        (sess_dir / "sessions.json").write_text(json.dumps(index))
        # live1 has a transcript
        (sess_dir / "live1.jsonl").write_text('{"msg":"hi"}\n')
        # stale1 has NO transcript (gateway already deleted it)
        # orphan transcript not in index
        (sess_dir / "orphan1.jsonl").write_text('{"msg":"orphan"}\n')
        # old .deleted file (set mtime to 10 days ago)
        old_deleted = sess_dir / "old1.jsonl.deleted.2026-01-01T00-00-00.000Z"
        old_deleted.write_text('{"msg":"old"}\n')
        ten_days_ago = time.time() - (10 * 86400)
        os.utime(str(old_deleted), (ten_days_ago, ten_days_ago))
        # recent .deleted file (should NOT be purged)
        recent_deleted = sess_dir / "recent1.jsonl.deleted.2026-02-14T00-00-00.000Z"
        recent_deleted.write_text('{"msg":"recent"}\n')
        return tmp_path

    @pytest.mark.asyncio
    async def test_cleanup_orphans_dry_run(self, skill, messy_agents_dir):
        """Dry run reports issues without modifying anything."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(messy_agents_dir)
        try:
            result = await skill.cleanup_orphans(dry_run=True)
            assert result.success is True
            assert result.data["dry_run"] is True
            assert result.data["stale_keys_removed"] == 1  # stale1
            assert result.data["orphan_transcripts_archived"] == 1  # orphan1
            assert result.data["old_deleted_files_purged"] == 1  # old1
            # Verify nothing was actually changed
            index = _load_sessions_index("main")
            assert "agent:main:cron:stale1" in index  # still there
            sess_dir = messy_agents_dir / "main" / "sessions"
            assert (sess_dir / "orphan1.jsonl").exists()  # still there
        finally:
            mod._AGENTS_DIR = orig

    @pytest.mark.asyncio
    async def test_cleanup_orphans_execute(self, skill, messy_agents_dir):
        """Actually clean up stale keys, orphans, and old .deleted files."""
        import aria_skills.session_manager as mod
        orig = mod._AGENTS_DIR
        mod._AGENTS_DIR = str(messy_agents_dir)
        try:
            result = await skill.cleanup_orphans(dry_run=False)
            assert result.success is True
            assert result.data["stale_keys_removed"] == 1
            assert result.data["orphan_transcripts_archived"] == 1
            assert result.data["old_deleted_files_purged"] == 1
            # Verify stale key removed from index
            index = _load_sessions_index("main")
            assert "agent:main:cron:stale1" not in index
            assert "agent:main:cron:live1" in index  # live one kept
            # Verify orphan archived
            sess_dir = messy_agents_dir / "main" / "sessions"
            assert not (sess_dir / "orphan1.jsonl").exists()
            assert len(list(sess_dir.glob("orphan1.jsonl.deleted.*"))) == 1
            # Verify old .deleted removed
            assert not (sess_dir / "old1.jsonl.deleted.2026-01-01T00-00-00.000Z").exists()
            # Verify recent .deleted kept
            assert (sess_dir / "recent1.jsonl.deleted.2026-02-14T00-00-00.000Z").exists()
        finally:
            mod._AGENTS_DIR = orig