"""
Tests for the fact_check skill (Layer 3 — domain).

Covers:
- Claim extraction from text
- Claim assessment with evidence
- Quick-check single statements
- Source comparison
- Verdict summary
- Edge cases (empty inputs, missing claims)
"""
from __future__ import annotations

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.fact_check import FactCheckSkill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> FactCheckSkill:
    return FactCheckSkill(SkillConfig(name="fact_check"))


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
# Tests — Claim Extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_claims():
    skill = _make_skill()
    await skill.initialize()
    text = (
        "Python is the most popular language. "
        "AI will replace 50 percent of jobs. "
        "The sky is blue."
    )
    result = await skill.extract_claims(text=text, source="test")
    assert result.success
    assert result.data["total_extracted"] >= 2
    for claim in result.data["claims"]:
        assert claim["status"] == "unverified"
        assert claim["source"] == "test"


@pytest.mark.asyncio
async def test_extract_claims_empty_text():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.extract_claims(text="")
    assert not result.success


@pytest.mark.asyncio
async def test_extract_claims_no_assertive_sentences():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.extract_claims(text="Hello world. Nice day.")
    assert result.success
    # Might extract 0 or few claims; no crash
    assert isinstance(result.data["claims"], list)


# ---------------------------------------------------------------------------
# Tests — Claim Assessment
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_assess_claim():
    skill = _make_skill()
    await skill.initialize()
    ext = await skill.extract_claims(text="Python is the most popular language.")
    claim_id = ext.data["claims"][0]["id"]

    result = await skill.assess_claim(
        claim_id=claim_id, evidence="TIOBE index 2025",
        confidence=0.85, verdict="mostly_true"
    )
    assert result.success
    assert result.data["claim"]["verdict"] == "mostly_true"
    assert result.data["claim"]["status"] == "assessed"


@pytest.mark.asyncio
async def test_assess_claim_not_found():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.assess_claim(claim_id="bogus", evidence="none")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Quick Check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quick_check_with_absolutes():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.quick_check(statement="Everyone always loves Python")
    assert result.success
    assert result.data["risk_level"] == "high"
    assert result.data["claim"]["analysis"]["has_absolutes"] is True


@pytest.mark.asyncio
async def test_quick_check_with_numbers():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.quick_check(statement="There are 8 billion people on Earth")
    assert result.success
    assert result.data["risk_level"] == "medium"
    assert result.data["claim"]["analysis"]["has_numbers"] is True


@pytest.mark.asyncio
async def test_quick_check_low_risk():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.quick_check(statement="Python uses indentation for blocks")
    assert result.success
    assert result.data["risk_level"] == "low"


@pytest.mark.asyncio
async def test_quick_check_empty():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.quick_check(statement="")
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Source Comparison
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compare_sources():
    skill = _make_skill()
    await skill.initialize()
    ext = await skill.extract_claims(text="Python is the top language.")
    cid = ext.data["claims"][0]["id"]

    sources = [
        {"name": "TIOBE", "supports": True},
        {"name": "StackOverflow", "supports": True},
        {"name": "Random blog", "supports": False},
    ]
    result = await skill.compare_sources(claim_id=cid, sources=sources)
    assert result.success
    assert result.data["agreements"] == 2
    assert result.data["contradictions"] == 1
    assert result.data["consensus_ratio"] == pytest.approx(0.67, abs=0.01)


@pytest.mark.asyncio
async def test_compare_sources_no_sources():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.compare_sources(claim_id="x", sources=[])
    assert not result.success


# ---------------------------------------------------------------------------
# Tests — Verdict Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_verdict_summary_empty():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_verdict_summary()
    assert result.success
    assert result.data["total_claims"] == 0


@pytest.mark.asyncio
async def test_verdict_summary_with_data():
    skill = _make_skill()
    await skill.initialize()
    await skill.quick_check(statement="Test statement with numbers 123")
    result = await skill.get_verdict_summary()
    assert result.success
    assert result.data["total_claims"] >= 1
    assert result.data["assessed"] >= 1
