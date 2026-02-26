"""
Tests for the research skill (Layer 3 — domain).

Covers:
- Initialization
- Project lifecycle (start, add source, add finding, set thesis)
- Source evaluation
- Synthesis
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.research import ResearchSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(mock_api):
    skill = ResearchSkill(SkillConfig(name="research"))
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_health_check(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
    status = await skill.health_check()
    assert status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_start_project(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        result = await skill.start_project(topic="AI Safety")
    assert result.success
    assert result.data["topic"] == "AI Safety"
    assert "project_id" in result.data
    assert len(result.data["questions"]) > 0


@pytest.mark.asyncio
async def test_add_source(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="Crypto")
        pid = proj.data["project_id"]

        result = await skill.add_source(
            project_id=pid,
            url="https://example.com/paper",
            title="Crypto Study",
            source_type="academic",
        )
    assert result.success
    assert result.data["credibility"] == 0.85  # academic credibility
    assert result.data["total_sources"] == 1


@pytest.mark.asyncio
async def test_add_source_invalid_project(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        result = await skill.add_source(project_id="nonexistent", url="http://x.com", title="X")
    assert not result.success


@pytest.mark.asyncio
async def test_add_finding(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="Topic")
        pid = proj.data["project_id"]

        result = await skill.add_finding(project_id=pid, finding="Important finding")
    assert result.success
    assert result.data["total_findings"] == 1


@pytest.mark.asyncio
async def test_add_finding_empty(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="T")
        pid = proj.data["project_id"]
        result = await skill.add_finding(project_id=pid, finding="")
    assert not result.success


@pytest.mark.asyncio
async def test_set_thesis(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="T")
        pid = proj.data["project_id"]

        result = await skill.set_thesis(project_id=pid, thesis="AI will transform education")
    assert result.success
    assert result.data["thesis"] == "AI will transform education"


@pytest.mark.asyncio
async def test_evaluate_sources(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="T")
        pid = proj.data["project_id"]

        await skill.add_source(project_id=pid, url="a.com", title="A", source_type="peer_reviewed")
        await skill.add_source(project_id=pid, url="b.com", title="B", source_type="blog")

        result = await skill.evaluate_sources(project_id=pid)
    assert result.success
    assert result.data["total_sources"] == 2
    assert result.data["average_credibility"] > 0


@pytest.mark.asyncio
async def test_evaluate_sources_no_sources(mock_api_client):
    with patch("aria_skills.research.get_api_client", new_callable=AsyncMock, return_value=mock_api_client):
        skill = ResearchSkill(SkillConfig(name="research"))
        await skill.initialize()
        proj = await skill.start_project(topic="T")
        pid = proj.data["project_id"]
        result = await skill.evaluate_sources(project_id=pid)
    assert not result.success
