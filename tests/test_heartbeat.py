# tests/test_heartbeat.py
"""Tests for aria_mind/heartbeat.py — Heartbeat lifecycle & health monitoring."""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

pytestmark = pytest.mark.unit


# ── Helpers ────────────────────────────────────────────────────────────


def _make_mind(**overrides):
    """Build a minimal mock AriaMind."""
    mind = MagicMock()
    mind.soul = overrides.get("soul", MagicMock())
    mind.memory = overrides.get("memory", MagicMock())
    mind.cognition = overrides.get("cognition", MagicMock())
    return mind


# ── Construction & defaults ────────────────────────────────────────────


class TestHeartbeatInit:
    """Test Heartbeat construction and default state."""

    def test_initial_state(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        assert hb._running is False
        assert hb._last_beat is None
        assert hb._beat_count == 0
        assert hb._interval == 60

    def test_repr_unhealthy_at_start(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        assert "unhealthy" in repr(hb)

    def test_is_healthy_false_when_not_running(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        assert hb.is_healthy is False


# ── is_healthy property ────────────────────────────────────────────────


class TestIsHealthy:
    """Test the is_healthy property logic."""

    def test_false_when_no_last_beat(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._running = True
        hb._last_beat = None
        assert hb.is_healthy is False

    def test_true_when_recent_beat(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._running = True
        hb._last_beat = datetime.now(timezone.utc)
        assert hb.is_healthy is True

    def test_false_when_beat_too_old(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._running = True
        hb._last_beat = datetime.now(timezone.utc) - timedelta(seconds=300)
        assert hb.is_healthy is False


# ── start / stop ───────────────────────────────────────────────────────


class TestStartStop:
    """Test start/stop lifecycle (short interval for speed)."""

    async def test_start_sets_running(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._interval = 0.05  # very fast for testing
        await hb.start()
        assert hb._running is True
        await hb.stop()

    async def test_stop_cancels_task(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._interval = 0.05
        await hb.start()
        await hb.stop()
        assert hb._running is False
        assert hb._task.done()

    async def test_double_start_is_safe(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._interval = 0.05
        await hb.start()
        await hb.start()  # second call should be no-op
        assert hb._running is True
        await hb.stop()


# ── _beat() ────────────────────────────────────────────────────────────


class TestBeat:
    """Test single heartbeat cycle."""

    async def test_beat_increments_count(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._running = True
        await hb._beat()
        assert hb._beat_count == 1
        assert hb._last_beat is not None

    async def test_beat_records_health_status(self):
        from aria_mind.heartbeat import Heartbeat

        mind = _make_mind()
        hb = Heartbeat(mind)
        hb._running = True
        await hb._beat()
        status = hb._health_status
        assert "timestamp" in status
        assert "beat_number" in status
        assert status["beat_number"] == 1
        assert "subsystems" in status
        assert "all_healthy" in status

    async def test_beat_with_none_components(self):
        from aria_mind.heartbeat import Heartbeat

        mind = _make_mind(soul=None, memory=None, cognition=None)
        hb = Heartbeat(mind)
        hb._running = True
        await hb._beat()
        subs = hb._health_status.get("subsystems", {})
        assert subs.get("soul") is False or subs.get("soul") is None
        assert subs.get("memory") is False or subs.get("memory") is None
        assert subs.get("cognition") is False or subs.get("cognition") is None


# ── get_status() ───────────────────────────────────────────────────────


class TestGetStatus:
    """Test get_status() return structure."""

    def test_status_keys_present(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        status = hb.get_status()
        assert "running" in status
        assert "healthy" in status
        assert "last_beat" in status
        assert "beat_count" in status
        assert "details" in status

    def test_status_before_any_beat(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        status = hb.get_status()
        assert status["running"] is False
        assert status["healthy"] is False
        assert status["last_beat"] is None
        assert status["beat_count"] == 0

    async def test_status_after_beat(self):
        from aria_mind.heartbeat import Heartbeat

        hb = Heartbeat(_make_mind())
        hb._running = True
        await hb._beat()
        status = hb.get_status()
        assert status["running"] is True
        assert status["healthy"] is True
        assert status["last_beat"] is not None
        assert status["beat_count"] == 1
