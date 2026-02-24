"""
Tests for the brainstorm skill (Layer 3 — domain).

Covers:
- Session lifecycle (start, add ideas, summarize)
- Technique application (valid + invalid)
- Random prompt generation
- Idea connections
- Idea evaluation
- Output formatting
"""
from __future__ import annotations

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.brainstorm import BrainstormSkill, TECHNIQUES, RANDOM_PROMPTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> BrainstormSkill:
    return BrainstormSkill(SkillConfig(name="brainstorm"))


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
async def test_start_session():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.start_session(topic="AI ethics", goal="Generate 10 ideas")
    assert result.success
    assert result.data["topic"] == "AI ethics"
    assert result.data["goal"] == "Generate 10 ideas"
    assert "session_id" in result.data


@pytest.mark.asyncio
async def test_add_idea_to_session():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Automation")
    sid = sess.data["session_id"]

    result = await skill.add_idea(session_id=sid, idea="Use LLMs for code review")
    assert result.success
    assert result.data["total_ideas"] == 1
    assert result.data["idea"]["text"] == "Use LLMs for code review"


@pytest.mark.asyncio
async def test_add_idea_missing_session():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.add_idea(session_id="nonexistent", idea="some idea")
    assert not result.success


@pytest.mark.asyncio
async def test_add_idea_empty_text():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="T")
    sid = sess.data["session_id"]
    result = await skill.add_idea(session_id=sid, idea="")
    assert not result.success


@pytest.mark.asyncio
async def test_apply_technique_scamper():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Product design")
    sid = sess.data["session_id"]

    result = await skill.apply_technique(session_id=sid, technique="scamper")
    assert result.success
    assert result.data["technique"] == "SCAMPER"
    assert len(result.data["prompts"]) == len(TECHNIQUES["scamper"]["prompts"])


@pytest.mark.asyncio
async def test_apply_technique_unknown():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="X")
    sid = sess.data["session_id"]

    result = await skill.apply_technique(session_id=sid, technique="nonexistent")
    assert not result.success


@pytest.mark.asyncio
async def test_get_random_prompt():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_random_prompt()
    assert result.success
    assert result.data["prompt"] in RANDOM_PROMPTS
    assert "tip" in result.data


@pytest.mark.asyncio
async def test_connect_ideas():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Connections")
    sid = sess.data["session_id"]
    await skill.add_idea(session_id=sid, idea="Idea A")
    await skill.add_idea(session_id=sid, idea="Idea B")

    result = await skill.connect_ideas(
        session_id=sid, idea_ids=[1, 2], connection="complementary"
    )
    assert result.success
    assert result.data["total_connections"] == 1
    assert result.data["connection"]["connection"] == "complementary"


@pytest.mark.asyncio
async def test_evaluate_ideas():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Eval test")
    sid = sess.data["session_id"]
    await skill.add_idea(session_id=sid, idea="Idea 1")
    await skill.add_idea(session_id=sid, idea="Idea 2")

    result = await skill.evaluate_ideas(session_id=sid)
    assert result.success
    assert result.data["total_ideas"] == 2
    assert "criteria" in result.data


@pytest.mark.asyncio
async def test_evaluate_ideas_empty():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Empty eval")
    sid = sess.data["session_id"]

    result = await skill.evaluate_ideas(session_id=sid)
    assert not result.success


@pytest.mark.asyncio
async def test_summarize_session():
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Summary test", goal="Test goal")
    sid = sess.data["session_id"]
    await skill.add_idea(session_id=sid, idea="Idea 1")
    await skill.apply_technique(session_id=sid, technique="six_hats")

    result = await skill.summarize_session(session_id=sid)
    assert result.success
    assert result.data["topic"] == "Summary test"
    assert result.data["total_ideas"] == 1
    assert "six_hats" in result.data["techniques_used"]
    assert "summary" in result.data


@pytest.mark.asyncio
async def test_summarize_session_invalid():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.summarize_session(session_id="bogus")
    assert not result.success


@pytest.mark.asyncio
async def test_all_techniques_available():
    """Every technique in TECHNIQUES dict can be applied."""
    skill = _make_skill()
    await skill.initialize()
    sess = await skill.start_session(topic="Technique coverage")
    sid = sess.data["session_id"]
    for name in TECHNIQUES:
        result = await skill.apply_technique(session_id=sid, technique=name)
        assert result.success, f"Technique {name} failed"
