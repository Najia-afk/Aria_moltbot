"""
Tests for the ci_cd skill (Layer 3 — domain).

Covers:
- Workflow generation (test, build, deploy, security types)
- Invalid workflow type handling
- Dockerfile generation (python, node)
- Workflow validation (via mocked filesystem)
- Deployment analysis
"""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.ci_cd import CICDSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> CICDSkill:
    return CICDSkill(SkillConfig(name="ci_cd"))


# ---------------------------------------------------------------------------
# Tests — Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize():
    skill = _make_skill()
    ok = await skill.initialize()
    assert ok is True
    assert await skill.health_check() == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Tests — Workflow Generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_test_workflow_python():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(workflow_type="test", language="python")
    assert result.success
    assert result.data["workflow_type"] == "test"
    assert result.data["language"] == "python"
    assert "yaml" in result.data
    assert "pip" in result.data["yaml"]


@pytest.mark.asyncio
async def test_generate_build_workflow():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(workflow_type="build", language="python")
    assert result.success
    assert result.data["workflow_type"] == "build"


@pytest.mark.asyncio
async def test_generate_deploy_workflow():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(workflow_type="deploy", language="python")
    assert result.success
    assert result.data["workflow_type"] == "deploy"


@pytest.mark.asyncio
async def test_generate_security_workflow():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(workflow_type="security", language="python")
    assert result.success
    assert result.data["workflow_type"] == "security"


@pytest.mark.asyncio
async def test_generate_workflow_invalid_type():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(workflow_type="nonexistent")
    assert not result.success


@pytest.mark.asyncio
async def test_generate_workflow_with_options():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_workflow(
        workflow_type="test", language="python", options={"branch": "develop"}
    )
    assert result.success
    assert "develop" in result.data["yaml"]


# ---------------------------------------------------------------------------
# Tests — Dockerfile Generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_python_dockerfile():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_dockerfile(language="python")
    assert result.success
    assert "dockerfile" in result.data
    assert result.data["language"] == "python"


@pytest.mark.asyncio
async def test_generate_node_dockerfile():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_dockerfile(language="node")
    assert result.success
    assert result.data["language"] == "node"


@pytest.mark.asyncio
async def test_generate_dockerfile_unsupported_language():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_dockerfile(language="rust")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Workflow Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_workflow_valid():
    skill = _make_skill()
    await skill.initialize()

    fake_content = """name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    concurrency:
      group: ci
    steps:
      - uses: actions/checkout@v4
"""
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = fake_content

    with patch("aria_skills.ci_cd.Path", return_value=mock_path):
        result = await skill.validate_workflow("fake.yml")
    assert result.success
    assert result.data["valid"] is True
    assert result.data["issues"] == []


@pytest.mark.asyncio
async def test_validate_workflow_missing_fields():
    skill = _make_skill()
    await skill.initialize()

    fake_content = "# empty workflow\nsteps:\n  - run: echo hi"
    mock_path = MagicMock()
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = fake_content

    with patch("aria_skills.ci_cd.Path", return_value=mock_path):
        result = await skill.validate_workflow("bad.yml")
    assert result.success
    assert result.data["valid"] is False
    assert len(result.data["issues"]) > 0


@pytest.mark.asyncio
async def test_validate_workflow_file_not_found():
    skill = _make_skill()
    await skill.initialize()

    mock_path = MagicMock()
    mock_path.exists.return_value = False

    with patch("aria_skills.ci_cd.Path", return_value=mock_path):
        result = await skill.validate_workflow("missing.yml")
    assert not result.success
