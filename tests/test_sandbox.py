# tests/test_sandbox.py
"""Tests for the Sandbox skill — safe code execution in isolated Docker container."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus

pytestmark = pytest.mark.unit


@pytest.fixture
def skill_config():
    return SkillConfig(
        name="sandbox",
        enabled=True,
        config={"sandbox_url": "http://test-sandbox:9999"},
    )


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx AsyncClient."""
    client = AsyncMock()
    return client


@pytest.fixture
def make_response():
    """Factory for mock httpx responses."""
    def _make(status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return resp
    return _make


@pytest.fixture
async def sandbox(skill_config, mock_httpx_client):
    """Create an initialized SandboxSkill with mocked client."""
    from aria_skills.sandbox import SandboxSkill
    skill = SandboxSkill(skill_config)
    await skill.initialize()
    skill._client = mock_httpx_client  # Replace real client with mock
    return skill


# ── name / canonical ─────────────────────────────────────────────────

class TestSandboxInit:
    """Tests for initialization and identity."""

    def test_skill_name(self, skill_config):
        from aria_skills.sandbox import SandboxSkill
        skill = SandboxSkill(skill_config)
        assert skill.name == "sandbox"

    def test_canonical_name(self, skill_config):
        from aria_skills.sandbox import SandboxSkill
        skill = SandboxSkill(skill_config)
        assert skill.canonical_name == "aria-sandbox"

    async def test_initialize(self, skill_config):
        from aria_skills.sandbox import SandboxSkill
        skill = SandboxSkill(skill_config)
        result = await skill.initialize()
        assert result is True
        assert skill._status == SkillStatus.AVAILABLE


# ── health_check ─────────────────────────────────────────────────────

class TestHealthCheck:
    """Tests for health_check."""

    async def test_health_check_success(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.get = AsyncMock(return_value=make_response(200, {"status": "healthy"}))

        status = await sandbox.health_check()
        assert status == SkillStatus.AVAILABLE
        mock_httpx_client.get.assert_called_once_with("/health")

    async def test_health_check_error(self, sandbox, mock_httpx_client):
        mock_httpx_client.get = AsyncMock(side_effect=Exception("connection refused"))

        status = await sandbox.health_check()
        assert status == SkillStatus.ERROR

    async def test_health_check_not_initialized(self, skill_config):
        from aria_skills.sandbox import SandboxSkill
        skill = SandboxSkill(skill_config)
        # Don't initialize — _client is None
        status = await skill.health_check()
        assert status == SkillStatus.UNAVAILABLE


# ── run_code ─────────────────────────────────────────────────────────

class TestRunCode:
    """Tests for run_code."""

    async def test_run_code_success(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "4\n",
                "stderr": "",
                "exit_code": 0,
            })
        )

        result = await sandbox.run_code("print(2 + 2)")
        assert result.success is True
        assert result.data["stdout"] == "4\n"
        assert result.data["exit_code"] == 0
        mock_httpx_client.post.assert_called_once_with(
            "/exec",
            json={"code": "print(2 + 2)", "timeout": 30},
        )

    async def test_run_code_failure(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "",
                "stderr": "NameError: name 'x' is not defined",
                "exit_code": 1,
            })
        )

        result = await sandbox.run_code("print(x)")
        assert result.success is False
        assert "NameError" in result.error

    async def test_run_code_not_initialized(self, skill_config):
        from aria_skills.sandbox import SandboxSkill
        skill = SandboxSkill(skill_config)
        # Don't initialize — _client is None
        result = await skill.run_code("print(1)")
        assert result.success is False
        assert "Not initialized" in result.error

    async def test_run_code_with_timeout(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "done\n",
                "stderr": "",
                "exit_code": 0,
            })
        )

        result = await sandbox.run_code("print('done')", timeout=60)
        assert result.success is True
        mock_httpx_client.post.assert_called_once_with(
            "/exec",
            json={"code": "print('done')", "timeout": 60},
        )

    async def test_run_code_connection_error(self, sandbox, mock_httpx_client):
        mock_httpx_client.post = AsyncMock(side_effect=Exception("connection refused"))

        result = await sandbox.run_code("print(1)")
        assert result.success is False
        assert "Sandbox execution failed" in result.error


# ── write_file ───────────────────────────────────────────────────────

class TestWriteFile:
    """Tests for write_file."""

    async def test_write_file(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
            })
        )

        result = await sandbox.write_file("/sandbox/test.py", "print('hello')")
        assert result.success is True
        # Verify it sent a pathlib-based write command
        call_args = mock_httpx_client.post.call_args
        assert "pathlib" in call_args.kwargs["json"]["code"]
        assert "write_text" in call_args.kwargs["json"]["code"]


# ── read_file ────────────────────────────────────────────────────────

class TestReadFile:
    """Tests for read_file."""

    async def test_read_file(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "file contents here\n",
                "stderr": "",
                "exit_code": 0,
            })
        )

        result = await sandbox.read_file("/sandbox/test.py")
        assert result.success is True
        assert result.data["content"] == "file contents here\n"
        # Verify it sent a pathlib-based read command
        call_args = mock_httpx_client.post.call_args
        assert "pathlib" in call_args.kwargs["json"]["code"]
        assert "read_text" in call_args.kwargs["json"]["code"]


# ── run_tests ────────────────────────────────────────────────────────

class TestRunTests:
    """Tests for run_tests."""

    async def test_run_tests(self, sandbox, mock_httpx_client, make_response):
        mock_httpx_client.post = AsyncMock(
            return_value=make_response(200, {
                "stdout": "===== 3 passed =====\n",
                "stderr": "",
                "exit_code": 0,
            })
        )

        result = await sandbox.run_tests("tests/")
        assert result.success is True
        assert "passed" in result.data["stdout"]
        # Verify it sent a pytest command
        call_args = mock_httpx_client.post.call_args
        assert "pytest" in call_args.kwargs["json"]["code"]


# ── registration ─────────────────────────────────────────────────────

class TestSkillRegistration:
    """Test that the skill is properly registered."""

    def test_skill_registered(self):
        from aria_skills.registry import SkillRegistry
        assert "sandbox" in SkillRegistry._skill_classes

    def test_registered_canonical(self):
        from aria_skills.registry import SkillRegistry
        assert "aria-sandbox" in SkillRegistry._skill_classes
