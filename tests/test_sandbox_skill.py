# tests/test_sandbox_skill.py
"""
Unit tests for the SandboxSkill.

All httpx calls are mocked — no real sandbox container needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Optional

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.sandbox import SandboxSkill

pytestmark = pytest.mark.unit


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def sandbox_config() -> SkillConfig:
    return SkillConfig(
        name="sandbox",
        enabled=True,
        config={"sandbox_url": "http://aria-sandbox:9999"},
    )


@pytest.fixture
def sandbox_skill(sandbox_config) -> SandboxSkill:
    return SandboxSkill(sandbox_config)


def _mock_response(status_code: int = 200, json_data: Optional[dict] = None):
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# ── Properties ────────────────────────────────────────────────────────

class TestSandboxProperties:

    def test_name(self, sandbox_skill):
        assert sandbox_skill.name == "sandbox"

    def test_canonical_name(self, sandbox_skill):
        assert sandbox_skill.canonical_name == "aria-sandbox"

    def test_initial_status_unavailable(self, sandbox_skill):
        assert sandbox_skill.status == SkillStatus.UNAVAILABLE


# ── Initialize ────────────────────────────────────────────────────────

class TestSandboxInitialize:

    @pytest.mark.asyncio
    async def test_initialize_success(self, sandbox_skill):
        """initialize() should return True and set status AVAILABLE."""
        result = await sandbox_skill.initialize()
        assert result is True
        assert sandbox_skill.status == SkillStatus.AVAILABLE
        assert sandbox_skill._client is not None

    @pytest.mark.asyncio
    async def test_initialize_without_httpx(self, sandbox_skill):
        """initialize() should fail gracefully when httpx is missing."""
        with patch("aria_skills.sandbox.HAS_HTTPX", False):
            result = await sandbox_skill.initialize()
        assert result is False
        assert sandbox_skill.status == SkillStatus.UNAVAILABLE


# ── Health Check ──────────────────────────────────────────────────────

class TestSandboxHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.get = AsyncMock(
            return_value=_mock_response(200, {"status": "healthy"})
        )
        status = await sandbox_skill.health_check()
        assert status == SkillStatus.AVAILABLE

    @pytest.mark.asyncio
    async def test_health_check_unavailable_no_client(self, sandbox_skill):
        """health_check before initialize should return UNAVAILABLE."""
        status = await sandbox_skill.health_check()
        assert status == SkillStatus.UNAVAILABLE

    @pytest.mark.asyncio
    async def test_health_check_error(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.get = AsyncMock(side_effect=Exception("connection refused"))
        status = await sandbox_skill.health_check()
        assert status == SkillStatus.ERROR


# ── run_code ──────────────────────────────────────────────────────────

class TestSandboxRunCode:

    @pytest.mark.asyncio
    async def test_run_code_success(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.post = AsyncMock(
            return_value=_mock_response(200, {
                "stdout": "hello\n",
                "stderr": "",
                "exit_code": 0,
            })
        )
        result = await sandbox_skill.run_code("print('hello')")
        assert result.success is True
        assert result.data["stdout"] == "hello\n"
        assert result.data["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_run_code_failure_nonzero_exit(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.post = AsyncMock(
            return_value=_mock_response(200, {
                "stdout": "",
                "stderr": "NameError: name 'x' is not defined",
                "exit_code": 1,
            })
        )
        result = await sandbox_skill.run_code("print(x)")
        assert result.success is False
        assert "NameError" in (result.error or "")

    @pytest.mark.asyncio
    async def test_run_code_not_initialized(self, sandbox_skill):
        result = await sandbox_skill.run_code("print(1)")
        assert result.success is False
        assert "Not initialized" in result.error

    @pytest.mark.asyncio
    async def test_run_code_http_error(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.post = AsyncMock(
            return_value=_mock_response(500, {"error": "internal"})
        )
        result = await sandbox_skill.run_code("print(1)")
        assert result.success is False
        assert "Sandbox execution failed" in result.error


# ── write_file ────────────────────────────────────────────────────────

class TestSandboxWriteFile:

    @pytest.mark.asyncio
    async def test_write_file_success(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.post = AsyncMock(
            return_value=_mock_response(200, {
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
            })
        )
        result = await sandbox_skill.write_file("/sandbox/test.py", "x = 1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_write_file_not_initialized(self, sandbox_skill):
        result = await sandbox_skill.write_file("/sandbox/test.py", "x = 1")
        assert result.success is False


# ── read_file ────────────────────────────────────────────────────────

class TestSandboxReadFile:

    @pytest.mark.asyncio
    async def test_read_file_success(self, sandbox_skill):
        await sandbox_skill.initialize()
        sandbox_skill._client.post = AsyncMock(
            return_value=_mock_response(200, {
                "stdout": "x = 1\n",
                "stderr": "",
                "exit_code": 0,
            })
        )
        result = await sandbox_skill.read_file("/sandbox/test.py")
        assert result.success is True
        assert result.data["content"] == "x = 1\n"

    @pytest.mark.asyncio
    async def test_read_file_not_initialized(self, sandbox_skill):
        result = await sandbox_skill.read_file("/sandbox/test.py")
        assert result.success is False
