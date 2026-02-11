# tests/test_memory_deque.py
"""Tests for memory deque bug fix and datetime deprecation (TICKET-08)."""
import pytest
from collections import deque
from datetime import datetime, timezone

pytestmark = pytest.mark.unit


class TestDequePreservation:
    """Test that clear_short() preserves deque maxlen."""

    def test_clear_short_preserves_deque_type(self):
        from aria_mind.memory import MemoryManager
        mm = MemoryManager()
        mm.remember_short("test entry")
        mm.clear_short()
        assert isinstance(mm._short_term, deque), "clear_short() must preserve deque type"

    def test_clear_short_preserves_maxlen(self):
        from aria_mind.memory import MemoryManager
        mm = MemoryManager()
        mm.clear_short()
        assert mm._short_term.maxlen == mm._max_short_term, "clear_short() must preserve maxlen"

    def test_maxlen_enforced_after_clear(self):
        from aria_mind.memory import MemoryManager
        mm = MemoryManager()
        mm.clear_short()
        for i in range(300):
            mm.remember_short(f"item-{i}")
        assert len(mm._short_term) == mm._max_short_term, "deque maxlen should cap at _max_short_term"

    def test_timestamps_are_timezone_aware(self):
        from aria_mind.memory import MemoryManager
        mm = MemoryManager()
        mm.remember_short("tz test")
        entry = mm._short_term[-1]
        ts = datetime.fromisoformat(entry["timestamp"])
        assert ts.tzinfo is not None, "Timestamps should be timezone-aware"


class TestSkillResultTimestamp:
    """Test that SkillResult timestamps are timezone-aware."""

    def test_ok_result_has_aware_timestamp(self):
        from aria_skills.base import SkillResult
        result = SkillResult.ok(data="test")
        assert result.timestamp.tzinfo is not None, "SkillResult.ok() timestamp must be tz-aware"

    def test_fail_result_has_aware_timestamp(self):
        from aria_skills.base import SkillResult
        result = SkillResult.fail(error="test error")
        assert result.timestamp.tzinfo is not None, "SkillResult.fail() timestamp must be tz-aware"
