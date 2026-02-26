"""
Tests for the pytest_runner skill (Layer 3 — domain).

Covers:
- Path validation (ALLOWED_TEST_DIRS)
- _sanitize_param stripping
- Dangerous path rejection (traversal, metacharacters)
- Mocked subprocess test execution
- Last result retrieval
"""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.pytest_runner import (
    PytestSkill,
    _validate_path,
    _sanitize_param,
    ALLOWED_TEST_DIRS,
)


# ---------------------------------------------------------------------------
# Path validation tests (S-105)
# ---------------------------------------------------------------------------

def test_validate_path_allowed():
    assert _validate_path("tests/skills/test_foo.py") == "tests/skills/test_foo.py"


def test_validate_path_allowed_dirs():
    for d in ALLOWED_TEST_DIRS:
        result = _validate_path(d)
        assert result  # Should not raise


def test_validate_path_traversal():
    with pytest.raises(ValueError, match="traversal"):
        _validate_path("tests/../etc/passwd")


def test_validate_path_disallowed():
    with pytest.raises(ValueError, match="must start with"):
        _validate_path("/tmp/evil/tests.py")


def test_validate_path_shell_metacharacters():
    with pytest.raises(ValueError, match="illegal characters"):
        _validate_path("tests/; rm -rf /")


def test_validate_path_pipe_injection():
    with pytest.raises(ValueError, match="illegal characters"):
        _validate_path("tests/ | cat /etc/passwd")


def test_validate_path_backtick_injection():
    with pytest.raises(ValueError, match="illegal characters"):
        _validate_path("tests/`whoami`")


def test_validate_path_backslash_to_forward():
    result = _validate_path("tests\\skills\\test_foo.py")
    assert result == "tests/skills/test_foo.py"


# ---------------------------------------------------------------------------
# _sanitize_param tests
# ---------------------------------------------------------------------------

def test_sanitize_param_clean():
    assert _sanitize_param("not slow") == "not slow"


def test_sanitize_param_strips_special():
    assert _sanitize_param("test; rm -rf /") == "test rm -rf "


def test_sanitize_param_allows_markers():
    result = _sanitize_param("integration,smoke-test")
    assert result == "integration,smoke-test"


def test_sanitize_param_removes_shell_chars():
    result = _sanitize_param("$(evil)")
    assert "$" not in result
    assert "(" not in result
    assert ")" not in result


# ---------------------------------------------------------------------------
# PytestSkill lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = PytestSkill(SkillConfig(name="pytest_runner"))
    ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# run_tests with mocked subprocess
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tests_success():
    skill = PytestSkill(SkillConfig(name="pytest_runner"))
    await skill.initialize()

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(
        b"tests/test_a.py::test_one passed\n1 passed in 0.5s\n",
        b""
    ))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await skill.run_tests(path="tests/")
    assert result.success
    assert result.data["success"] is True


@pytest.mark.asyncio
async def test_run_tests_failure():
    skill = PytestSkill(SkillConfig(name="pytest_runner"))
    await skill.initialize()

    mock_proc = AsyncMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(
        b"1 failed, 0 passed\n",
        b""
    ))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await skill.run_tests(path="tests/")
    assert result.success  # Skill call succeeds, test run reports failure
    assert result.data["success"] is False
    assert result.data["failed"] >= 1


@pytest.mark.asyncio
async def test_run_tests_invalid_path():
    skill = PytestSkill(SkillConfig(name="pytest_runner"))
    await skill.initialize()
    result = await skill.run_tests(path="/root/evil")
    assert not result.success
    assert "invalid" in result.error.lower()


@pytest.mark.asyncio
async def test_run_tests_timeout():
    skill = PytestSkill(SkillConfig(name="pytest_runner", config={"timeout": 1}))
    await skill.initialize()

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        result = await skill.run_tests(path="tests/")
    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_get_last_result_none():
    skill = PytestSkill(SkillConfig(name="pytest_runner"))
    await skill.initialize()
    result = await skill.get_last_result()
    assert not result.success
