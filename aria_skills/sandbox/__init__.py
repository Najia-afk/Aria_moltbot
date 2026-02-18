# aria_skills/sandbox/__init__.py
"""
Sandbox Skill — safe code execution in isolated Docker container.

Provides Aria with the ability to run code, write/read files, and run tests
in an isolated sandbox environment with resource limits.
All sandbox operations are logged via api_client.
"""
import os
import logging
from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@SkillRegistry.register
class SandboxSkill(BaseSkill):
    """
    Executes code in an isolated Docker sandbox.

    The sandbox container (aria-sandbox) runs on aria-net with:
    - No internet access
    - 2 CPU, 2GB RAM limits
    - Python 3.12 + common packages (httpx, pytest, pyyaml)

    Methods:
        run_code(code, timeout) — Execute Python code
        write_file(path, content) — Write file in sandbox
        read_file(path) — Read file from sandbox
        run_tests(test_path) — Run pytest in sandbox
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: httpx.AsyncClient | None = None
        self._sandbox_url: str = ""

    @property
    def name(self) -> str:
        return "sandbox"

    @property
    def canonical_name(self) -> str:
        return "aria-sandbox"

    async def initialize(self) -> bool:
        if not HAS_HTTPX:
            self.logger.error("httpx not installed — sandbox unavailable")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._sandbox_url = self.config.config.get(
            "sandbox_url",
            os.environ.get("SANDBOX_URL", "http://aria-sandbox:9999"),
        )
        self._client = httpx.AsyncClient(
            base_url=self._sandbox_url,
            timeout=120.0,
        )
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        if not self._client:
            return SkillStatus.UNAVAILABLE
        try:
            resp = await self._client.get("/health")
            if resp.status_code == 200:
                self._status = SkillStatus.AVAILABLE
            else:
                self._status = SkillStatus.ERROR
        except Exception:
            self._status = SkillStatus.ERROR
        return self._status

    @logged_method()
    async def run_code(self, code: str, timeout: int = 30) -> SkillResult:
        """Execute Python code in the sandbox."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        try:
            resp = await self._client.post(
                "/exec",
                json={"code": code, "timeout": timeout},
            )
            resp.raise_for_status()
            data = resp.json()

            success = data.get("exit_code", -1) == 0
            self._log_usage("run_code", success)

            return SkillResult(
                success=success,
                data=data,
                error=data.get("stderr") if not success else None,
            )
        except Exception as e:
            self._log_usage("run_code", False, error=str(e))
            return SkillResult.fail(f"Sandbox execution failed: {e}")

    @logged_method()
    async def write_file(self, path: str, content: str) -> SkillResult:
        """Write a file in the sandbox via code execution."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        # Escape content for Python string
        escaped = content.replace("\\", "\\\\").replace("'", "\\'")
        code = (
            f"import pathlib; p = pathlib.Path('{path}'); "
            f"p.parent.mkdir(parents=True, exist_ok=True); "
            f"p.write_text('''{escaped}''')"
        )

        return await self.run_code(code, timeout=10)

    @logged_method()
    async def read_file(self, path: str) -> SkillResult:
        """Read a file from the sandbox via code execution."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        code = f"import pathlib; print(pathlib.Path('{path}').read_text())"
        result = await self.run_code(code, timeout=10)

        if result.success and result.data:
            result.data["content"] = result.data.get("stdout", "")

        return result

    @logged_method()
    async def run_tests(self, test_path: str = "tests/") -> SkillResult:
        """Run pytest in the sandbox."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        code = (
            f"import subprocess, sys; "
            f"r = subprocess.run([sys.executable, '-m', 'pytest', '{test_path}', '-v', '--tb=short'], "
            f"capture_output=True, text=True, timeout=60); "
            f"print(r.stdout); print(r.stderr, file=sys.stderr); sys.exit(r.returncode)"
        )

        return await self.run_code(code, timeout=90)

    async def reset(self) -> SkillResult:
        """Reset the sandbox (kill switch — terminate and restart)."""
        if not self._client:
            return SkillResult.fail("Not initialized")

        # Send a cleanup code
        code = (
            "import shutil, os; "
            "[shutil.rmtree(d) for d in ['/sandbox/tmp', '/tmp'] "
            "if os.path.isdir(d) and d != '/tmp']; "
            "print('sandbox reset')"
        )
        return await self.run_code(code, timeout=10)
