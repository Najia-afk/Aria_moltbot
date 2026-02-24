"""
Tests for the security_scan skill (Layer 3 — domain).

Covers:
- Initialization and health check
- Code scanning (secrets, code patterns)
- Config scanning
- Dependency checking
- Security score calculation
- Scan history
"""
from __future__ import annotations

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.security_scan import SecurityScanSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> SecurityScanSkill:
    return SecurityScanSkill(SkillConfig(name="security_scan"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_scan_code_clean():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.scan_code(code="x = 1\ny = x + 2\n", language="python")
    assert result.success
    assert result.data["vulnerabilities_found"] == 0
    assert result.data["security_score"] == 100


@pytest.mark.asyncio
async def test_scan_code_detects_eval():
    skill = _make_skill()
    await skill.initialize()
    code = "result = eval(user_input)\n"
    result = await skill.scan_code(code=code, language="python")
    assert result.success
    assert result.data["vulnerabilities_found"] >= 1
    titles = [v["title"] for v in result.data["vulnerabilities"]]
    assert "Use of eval()" in titles


@pytest.mark.asyncio
async def test_scan_code_detects_hardcoded_password():
    skill = _make_skill()
    await skill.initialize()
    code = "password = 'super_secret_password_123'\n"
    result = await skill.scan_code(code=code, language="python")
    assert result.success
    assert result.data["vulnerabilities_found"] >= 1
    severities = [v["severity"] for v in result.data["vulnerabilities"]]
    assert "critical" in severities


@pytest.mark.asyncio
async def test_scan_code_detects_shell_injection():
    skill = _make_skill()
    await skill.initialize()
    code = "subprocess.call(cmd, shell=True)\n"
    result = await skill.scan_code(code=code, language="python")
    assert result.success
    titles = [v["title"] for v in result.data["vulnerabilities"]]
    assert "Shell Injection Risk" in titles


@pytest.mark.asyncio
async def test_scan_config_debug_enabled():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.scan_config(config={"debug": True}, config_type="generic")
    assert result.success
    assert result.data["issues_found"] >= 1
    titles = [i["title"] for i in result.data["issues"]]
    assert "Debug mode enabled" in titles


@pytest.mark.asyncio
async def test_scan_config_privileged():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.scan_config(config={"privileged": True})
    assert result.success
    titles = [i["title"] for i in result.data["issues"]]
    assert "Privileged/root execution" in titles


@pytest.mark.asyncio
async def test_scan_config_latest_tag():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.scan_config(config={"image": "nginx:latest"})
    assert result.success
    titles = [i["title"] for i in result.data["issues"]]
    assert "Using 'latest' image tag" in titles


@pytest.mark.asyncio
async def test_scan_config_clean():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.scan_config(config={"image": "nginx:1.25.0", "resources": {"cpu": "1"}})
    assert result.success
    assert result.data["issues_found"] == 0


@pytest.mark.asyncio
async def test_check_dependencies():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.check_dependencies(
        dependencies={"requests": "2.19.0", "pyyaml": "5.3"},
        ecosystem="python",
    )
    assert result.success
    assert result.data["vulnerable_packages"] >= 1


@pytest.mark.asyncio
async def test_check_dependencies_clean():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.check_dependencies(
        dependencies={"httpx": "0.27.0"},
        ecosystem="python",
    )
    assert result.success
    assert result.data["vulnerable_packages"] == 0


@pytest.mark.asyncio
async def test_scan_history():
    skill = _make_skill()
    await skill.initialize()
    await skill.scan_code(code="x = 1", language="python")
    result = await skill.get_scan_history()
    assert result.success
    assert result.data["total_scans"] == 1


@pytest.mark.asyncio
async def test_security_score_decreases_with_vulns():
    skill = _make_skill()
    await skill.initialize()
    code = (
        "password = 'secret'\n"
        "result = eval(user_input)\n"
        "subprocess.call(cmd, shell=True)\n"
    )
    result = await skill.scan_code(code=code, language="python")
    assert result.success
    assert result.data["security_score"] < 100
