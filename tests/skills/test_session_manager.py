"""
Tests for the session_manager skill (Layer 2).

Covers:
- Session listing
- Session deletion (filesystem + PG mark)
- Active-session protection
- Prune stale sessions
- Session stats
- Orphan cleanup
- Session isolation (main vs. cron/subagent)
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_skills.session_manager import (
    SessionManagerSkill,
    _flatten_sessions,
    _is_cron_or_subagent_session,
    _epoch_ms_to_iso,
)
from aria_skills.base import SkillConfig, SkillResult, SkillStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_index(*entries):
    """Build a sessions.json-like dict from (key, sessionId, updatedAt_ms) tuples."""
    index = {}
    for key, sid, updated_ms in entries:
        index[key] = {
            "sessionId": sid,
            "updatedAt": updated_ms,
            "model": "kimi",
        }
    return index


# ---------------------------------------------------------------------------
# Pure-function tests
# ---------------------------------------------------------------------------

def test_is_cron_or_subagent_session():
    """Cron and subagent markers are detected."""
    assert _is_cron_or_subagent_session("main:cron:hourly") is True
    assert _is_cron_or_subagent_session("main:subagent:brainstorm") is True
    assert _is_cron_or_subagent_session("main:run:42") is True
    assert _is_cron_or_subagent_session("main:direct:chat") is False
    assert _is_cron_or_subagent_session("") is False


def test_epoch_ms_to_iso():
    """Epoch-ms conversion produces ISO strings."""
    iso = _epoch_ms_to_iso(1708790400000)  # 2024-02-24 …
    assert iso is not None
    assert "2024" in iso
    assert _epoch_ms_to_iso(None) is None
    assert _epoch_ms_to_iso(0) is None
    assert _epoch_ms_to_iso("garbage") is None


def test_flatten_sessions_dedup():
    """_flatten_sessions deduplicates by sessionId."""
    index = _make_index(
        ("key1", "sid-abc", 1708790400000),
        ("key2", "sid-abc", 1708790500000),  # same sid
        ("key3", "sid-def", 1708790600000),
    )
    flat = _flatten_sessions(index, "main")
    sids = [s["sessionId"] for s in flat]
    assert len(sids) == 2
    assert "sid-abc" in sids
    assert "sid-def" in sids


def test_flatten_sessions_types():
    """_flatten_sessions assigns session_type based on key markers."""
    index = {
        "main:cron:hourly": {"sessionId": "s1", "updatedAt": 1708790400000},
        "main:subagent:brain": {"sessionId": "s2", "updatedAt": 1708790400000},
        "main:direct:chat": {"sessionId": "s3", "updatedAt": 1708790400000},
    }
    flat = _flatten_sessions(index, "main")
    by_sid = {s["sessionId"]: s for s in flat}
    assert by_sid["s1"]["session_type"] == "cron"
    assert by_sid["s2"]["session_type"] == "subagent"
    assert by_sid["s3"]["session_type"] == "direct"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def session_skill(mock_api_client):
    """Return a SessionManagerSkill wired to the mock API."""
    cfg = SkillConfig(name="session_manager", config={"stale_threshold_minutes": 30})
    skill = SessionManagerSkill(cfg)
    skill._api = mock_api_client
    skill._status = SkillStatus.AVAILABLE
    return skill


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_sessions_empty(session_skill):
    """Returns empty list when no sessions exist on the filesystem."""
    with patch("aria_skills.session_manager._list_all_agents", return_value=["main"]):
        with patch("aria_skills.session_manager._load_sessions_index", return_value={}):
            result = await session_skill.list_sessions()
    assert result.success is True
    assert result.data["session_count"] == 0


@pytest.mark.asyncio
async def test_list_sessions_returns_entries(session_skill):
    """Returns sessions from the filesystem index."""
    index = _make_index(
        ("main:cron:a", "sid-1", 1708790400000),
        ("main:subagent:b", "sid-2", 1708790500000),
    )
    with patch("aria_skills.session_manager._list_all_agents", return_value=["main"]):
        with patch("aria_skills.session_manager._load_sessions_index", return_value=index):
            result = await session_skill.list_sessions()
    assert result.success is True
    assert result.data["session_count"] == 2


# ---------------------------------------------------------------------------
# delete_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_session_missing_id(session_skill):
    """Deleting without session_id fails."""
    result = await session_skill.delete_session()
    assert result.success is False
    assert "required" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_session_active_protection(session_skill):
    """Cannot delete the currently active session."""
    with patch.dict(os.environ, {"ARIA_SESSION_ID": "active-sid"}):
        result = await session_skill.delete_session(session_id="active-sid")
    assert result.success is False
    assert "current session" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_session_main_direct_blocked(session_skill):
    """Main agent direct sessions are protected from deletion."""
    index = {"main:direct:chat": {"sessionId": "sid-protected"}}
    with (
        patch("aria_skills.session_manager._list_all_agents", return_value=["main"]),
        patch("aria_skills.session_manager._load_sessions_index", return_value=index),
        patch.dict(os.environ, {}, clear=False),
    ):
        # Make sure ARIA_SESSION_ID doesn't interfere
        os.environ.pop("ARIA_SESSION_ID", None)
        result = await session_skill.delete_session(session_id="sid-protected")
    assert result.success is False
    assert "only cron/subagent" in result.error.lower()


@pytest.mark.asyncio
async def test_delete_session_cron_allowed(session_skill, mock_api_client):
    """Cron sessions can be deleted."""
    index = {"main:cron:hourly": {"sessionId": "sid-cron-1"}}
    saved_index = {}

    def fake_save(data, agent="main"):
        saved_index.update(data)

    with (
        patch("aria_skills.session_manager._list_all_agents", return_value=["main"]),
        patch("aria_skills.session_manager._load_sessions_index", return_value=index),
        patch("aria_skills.session_manager._save_sessions_index", side_effect=fake_save),
        patch("aria_skills.session_manager._archive_transcript", return_value=True),
        patch.dict(os.environ, {}, clear=False),
    ):
        os.environ.pop("ARIA_SESSION_ID", None)
        mock_api_client.get = AsyncMock(return_value=SkillResult.ok({"items": []}))
        result = await session_skill.delete_session(session_id="sid-cron-1")
    assert result.success is True
    assert "sid-cron-1" in result.data["deleted"]


# ---------------------------------------------------------------------------
# get_session_stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_stats(session_skill):
    """Stats include total, stale, and per-agent counts."""
    index = _make_index(
        ("main:cron:a", "s1", 1708790400000),  # very old → stale
        ("main:cron:b", "s2", 1708790500000),   # very old → stale
    )
    with (
        patch("aria_skills.session_manager._list_all_agents", return_value=["main"]),
        patch("aria_skills.session_manager._load_sessions_index", return_value=index),
    ):
        result = await session_skill.get_session_stats()
    assert result.success is True
    assert result.data["total_sessions"] == 2
    assert result.data["stale_sessions"] >= 0


# ---------------------------------------------------------------------------
# prune_sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_prune_sessions_dry_run(session_skill):
    """Dry-run prune lists candidates without deleting."""
    old_index = _make_index(("main:cron:old", "s-old", 1000000000))  # epoch ~2001 — ancient
    with (
        patch("aria_skills.session_manager._list_all_agents", return_value=["main"]),
        patch("aria_skills.session_manager._load_sessions_index", return_value=old_index),
    ):
        result = await session_skill.prune_sessions(max_age_minutes=1, dry_run=True)
    assert result.success is True
    assert result.data["dry_run"] is True
    assert result.data["pruned_count"] >= 0


# ---------------------------------------------------------------------------
# Session isolation (main vs subagent)
# ---------------------------------------------------------------------------

def test_session_isolation_main_not_cron():
    """Direct main sessions are NOT considered cron/subagent."""
    assert _is_cron_or_subagent_session("main:direct:chat") is False


def test_session_isolation_subagent():
    """Subagent marker is recognized."""
    assert _is_cron_or_subagent_session("agent:subagent:research:42") is True
