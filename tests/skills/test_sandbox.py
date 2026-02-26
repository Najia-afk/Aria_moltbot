"""
Tests for the sandbox skill (Layer 3 — domain).

Covers:
- _sanitize_path function
- Initialization
- run_code (mocked httpx)
- write_file (mocked httpx, injection-safe)
- read_file (mocked httpx)
- run_tests (mocked httpx)
- reset
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.sandbox import SandboxSkill


# ---------------------------------------------------------------------------
# _sanitize_path tests
# ---------------------------------------------------------------------------

def test_sanitize_path_normal():
    assert SandboxSkill._sanitize_path("src/app.py") == "src/app.py"


def test_sanitize_path_removes_traversal():
    result = SandboxSkill._sanitize_path("../../etc/passwd")
    assert ".." not in result


def test_sanitize_path_removes_quotes():
    result = SandboxSkill._sanitize_path("test'file\".py")
    assert "'" not in result
    assert '"' not in result


def test_sanitize_path_removes_semicolons():
    result = SandboxSkill._sanitize_path("test;rm -rf /")
    assert ";" not in result


def test_sanitize_path_removes_newlines():
    result = SandboxSkill._sanitize_path("test\nfile\r.py")
    assert "\n" not in result
    assert "\r" not in result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _make_skill() -> SandboxSkill:
    return SandboxSkill(SkillConfig(name="sandbox", config={
        "sandbox_url": "http://aria-sandbox:9999"
    }))


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    with patch("aria_skills.sandbox.HAS_HTTPX", True):
        skill = _make_skill()
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_initialize_no_httpx():
    with patch("aria_skills.sandbox.HAS_HTTPX", False):
        skill = _make_skill()
        ok = await skill.initialize()
    assert ok is False
    assert skill._status == SkillStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_health_check_no_client():
    skill = _make_skill()
    skill._client = None
    status = await skill.health_check()
    assert status == SkillStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# run_code tests (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_code_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "exit_code": 0, "stdout": "Hello", "stderr": ""
    }))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.run_code(code="print('Hello')")
    assert result.success
    assert result.data["exit_code"] == 0


@pytest.mark.asyncio
async def test_run_code_failure():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "exit_code": 1, "stdout": "", "stderr": "SyntaxError"
    }))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.run_code(code="invalid(")
    assert not result.success


@pytest.mark.asyncio
async def test_run_code_not_initialized():
    skill = _make_skill()
    skill._client = None
    result = await skill.run_code(code="print('hi')")
    assert not result.success
    assert "not initialized" in result.error.lower()


# ---------------------------------------------------------------------------
# write_file tests (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_file_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "exit_code": 0, "stdout": "", "stderr": ""
    }))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.write_file(path="test.py", content="print('hi')")
    assert result.success


@pytest.mark.asyncio
async def test_write_file_no_path():
    skill = _make_skill()
    skill._client = AsyncMock()
    result = await skill.write_file(path="", content="x")
    assert not result.success


# ---------------------------------------------------------------------------
# read_file tests (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_read_file_success():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "exit_code": 0, "stdout": "file content here", "stderr": ""
    }))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.read_file(path="test.py")
    assert result.success


@pytest.mark.asyncio
async def test_read_file_no_path():
    skill = _make_skill()
    skill._client = AsyncMock()
    result = await skill.read_file(path="")
    assert not result.success


# ---------------------------------------------------------------------------
# run_tests tests (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tests():
    skill = _make_skill()
    skill._client = AsyncMock()
    skill._client.post = AsyncMock(return_value=_mock_response(200, {
        "exit_code": 0, "stdout": "1 passed", "stderr": ""
    }))
    skill._status = SkillStatus.AVAILABLE

    result = await skill.run_tests(test_path="tests/")
    assert result.success
