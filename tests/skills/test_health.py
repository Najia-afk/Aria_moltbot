"""
Tests for the health monitoring skill (Layer 1/L2).

Covers:
- Initialization and health_check
- System health check execution (check_system)
- Individual sub-checks (python, memory, disk, environment)
- Response parsing and overall status logic
- get_last_check before/after running a check
"""
from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aria_skills.health import HealthMonitorSkill
from aria_skills.base import SkillConfig, SkillResult, SkillStatus


@pytest.fixture
def health_skill():
    """Return an initialized HealthMonitorSkill."""
    cfg = SkillConfig(name="health", config={})
    skill = HealthMonitorSkill(cfg)
    return skill


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(health_skill):
    """Skill initializes and reports AVAILABLE."""
    ok = await health_skill.initialize()
    assert ok is True
    assert await health_skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# check_system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_system_returns_overall_status(health_skill):
    """check_system reports overall status and a timestamp."""
    await health_skill.initialize()
    result = await health_skill.check_system()
    assert result.success is True
    assert "overall_status" in result.data
    assert "timestamp" in result.data
    assert "checks" in result.data


@pytest.mark.asyncio
async def test_check_system_includes_python_check(health_skill):
    """Python sub-check is always healthy and contains version info."""
    await health_skill.initialize()
    result = await health_skill.check_system()
    python_check = result.data["checks"]["python"]
    assert python_check["status"] == "healthy"
    assert sys.version in python_check["version"]


@pytest.mark.asyncio
async def test_check_system_includes_environment(health_skill):
    """Environment sub-check reports ARIA_* env vars."""
    await health_skill.initialize()
    result = await health_skill.check_system()
    env_check = result.data["checks"]["environment"]
    assert "status" in env_check
    assert "aria_vars" in env_check


@pytest.mark.asyncio
async def test_check_system_memory_with_psutil(health_skill):
    """If psutil is available, memory check returns numeric fields."""
    await health_skill.initialize()
    result = await health_skill.check_system()
    mem = result.data["checks"]["memory"]
    # psutil may not be installed — either way the check must not crash
    assert "status" in mem
    if mem["status"] != "unknown":
        assert "percent_used" in mem
        assert isinstance(mem["percent_used"], (int, float))


@pytest.mark.asyncio
async def test_check_system_memory_without_psutil(health_skill):
    """Memory check degrades gracefully when psutil is missing."""
    await health_skill.initialize()
    with patch.dict("sys.modules", {"psutil": None}):
        # Force ImportError inside _check_memory
        mem = await health_skill._check_memory()
    assert mem["status"] == "unknown"
    assert "psutil" in mem.get("message", "").lower()


@pytest.mark.asyncio
async def test_check_system_disk_without_psutil(health_skill):
    """Disk check degrades gracefully when psutil is missing."""
    await health_skill.initialize()
    with patch.dict("sys.modules", {"psutil": None}):
        disk = await health_skill._check_disk()
    assert disk["status"] == "unknown"


# ---------------------------------------------------------------------------
# Overall status logic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_overall_status_critical(health_skill):
    """Overall status is 'critical' if any sub-check is critical."""
    await health_skill.initialize()

    async def _critical_memory():
        return {"status": "critical", "percent_used": 99}

    with patch.object(health_skill, "_check_memory", _critical_memory):
        result = await health_skill.check_system()
    assert result.data["overall_status"] == "critical"


@pytest.mark.asyncio
async def test_overall_status_warning(health_skill):
    """Overall status is 'warning' if any sub-check is warning (but none critical)."""
    await health_skill.initialize()

    async def _warning_disk():
        return {"status": "warning", "percent_used": 85}

    with (
        patch.object(health_skill, "_check_disk", _warning_disk),
        patch.object(health_skill, "_check_memory", AsyncMock(return_value={"status": "healthy"})),
        patch.object(health_skill, "_check_network", AsyncMock(return_value={"status": "healthy"})),
    ):
        result = await health_skill.check_system()
    assert result.data["overall_status"] == "warning"


# ---------------------------------------------------------------------------
# get_last_check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_last_check_before_first_run(health_skill):
    """get_last_check fails before any check has been run."""
    await health_skill.initialize()
    result = await health_skill.get_last_check()
    assert result.success is False
    assert "no health check" in result.error.lower()


@pytest.mark.asyncio
async def test_get_last_check_after_run(health_skill):
    """get_last_check returns cached results after a check."""
    await health_skill.initialize()
    await health_skill.check_system()
    result = await health_skill.get_last_check()
    assert result.success is True
    assert "timestamp" in result.data
    assert "checks" in result.data
