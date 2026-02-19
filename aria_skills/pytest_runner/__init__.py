# aria_skills/pytest_runner.py
"""
Pytest runner skill.

Executes and reports on pytest test runs.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class PytestSkill(BaseSkill):
    """
    Pytest test runner.
    
    Config:
        test_dir: Default test directory
        timeout: Test run timeout in seconds
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._last_result: Dict | None = None
    
    @property
    def name(self) -> str:
        return "pytest_runner"
    
    async def initialize(self) -> bool:
        """Initialize pytest runner."""
        self._test_dir = self.config.config.get("test_dir", "tests")
        self._timeout = self.config.config.get("timeout", 300)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Pytest runner initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check pytest availability."""
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pytest", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._status = SkillStatus.AVAILABLE if proc.returncode == 0 else SkillStatus.UNAVAILABLE
        except Exception:
            self._status = SkillStatus.UNAVAILABLE
        
        return self._status
    
    async def run_tests(
        self,
        path: str | None = None,
        markers: str | None = None,
        keywords: str | None = None,
        verbose: bool = True,
    ) -> SkillResult:
        """
        Run pytest tests.
        
        Args:
            path: Test path (file or directory)
            markers: Pytest markers to filter (e.g., "not slow")
            keywords: Keyword expression (-k)
            verbose: Enable verbose output
            
        Returns:
            SkillResult with test results
        """
        cmd = [sys.executable, "-m", "pytest", path or self._test_dir]
        
        if verbose:
            cmd.append("-v")
        
        if markers:
            cmd.extend(["-m", markers])
        
        if keywords:
            cmd.extend(["-k", keywords])
        
        # Add summary flags
        cmd.append("--tb=short")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._timeout,
            )
            
            output = stdout.decode()
            
            # Parse results
            passed = output.count(" passed")
            failed = output.count(" failed")
            skipped = output.count(" skipped")
            errors = output.count(" error")
            
            self._last_result = {
                "path": path or self._test_dir,
                "return_code": proc.returncode,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "errors": errors,
                "success": proc.returncode == 0,
                "output": output[-5000:],  # Last 5000 chars
                "run_at": datetime.now(timezone.utc).isoformat(),
            }
            
            return SkillResult.ok(self._last_result)
            
        except asyncio.TimeoutError:
            return SkillResult.fail(f"Test run timed out after {self._timeout}s")
        except Exception as e:
            return SkillResult.fail(f"Test run failed: {e}")
    
    async def get_last_result(self) -> SkillResult:
        """Get results of last test run."""
        if not self._last_result:
            return SkillResult.fail("No test run yet")
        
        return SkillResult.ok(self._last_result)
