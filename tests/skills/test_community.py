"""
Tests for the community skill (Layer 3 — domain).

Covers:
- Member tracking
- Engagement recording
- Community health metrics
- Champion identification
- Campaign creation
- Growth strategies
- Content calendar generation
"""
from __future__ import annotations

import pytest

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.community import CommunitySkill, GROWTH_STRATEGIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> CommunitySkill:
    return CommunitySkill(SkillConfig(name="community"))


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
# Tests — Member Tracking
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_track_member():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.track_member(member_id="m1", name="Alice", platform="discord")
    assert result.success
    assert result.data["member"]["name"] == "Alice"
    assert result.data["member"]["platform"] == "discord"
    assert result.data["total_members"] == 1


@pytest.mark.asyncio
async def test_track_multiple_members():
    skill = _make_skill()
    await skill.initialize()
    await skill.track_member(member_id="m1", name="Alice")
    result = await skill.track_member(member_id="m2", name="Bob")
    assert result.data["total_members"] == 2


# ---------------------------------------------------------------------------
# Tests — Engagement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_engagement():
    skill = _make_skill()
    await skill.initialize()
    await skill.track_member(member_id="m1", name="Alice")

    result = await skill.record_engagement(
        member_id="m1", action="message", content="Hello!"
    )
    assert result.success
    assert result.data["total_engagements"] == 1


@pytest.mark.asyncio
async def test_engagement_increments_member_count():
    skill = _make_skill()
    await skill.initialize()
    await skill.track_member(member_id="m1", name="Alice")
    await skill.record_engagement(member_id="m1", action="message")
    await skill.record_engagement(member_id="m1", action="reaction")

    health = await skill.get_community_health()
    assert health.data["active_members"] == 1
    assert health.data["total_engagements"] == 2


# ---------------------------------------------------------------------------
# Tests — Community Health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_community_health_empty():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_community_health()
    assert result.success
    assert result.data["total_members"] == 0
    assert result.data["engagement_rate"] == 0


@pytest.mark.asyncio
async def test_community_health_with_data():
    skill = _make_skill()
    await skill.initialize()
    await skill.track_member(member_id="m1", name="Alice")
    await skill.track_member(member_id="m2", name="Bob")
    await skill.record_engagement(member_id="m1", action="post")

    result = await skill.get_community_health()
    assert result.data["total_members"] == 2
    assert result.data["active_members"] == 1
    assert result.data["engagement_rate"] == 0.5


# ---------------------------------------------------------------------------
# Tests — Champions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identify_champions():
    skill = _make_skill()
    await skill.initialize()
    await skill.track_member(member_id="m1", name="Alice")
    await skill.track_member(member_id="m2", name="Bob")
    for _ in range(5):
        await skill.record_engagement(member_id="m1", action="post")
    await skill.record_engagement(member_id="m2", action="post")

    result = await skill.identify_champions(top_n=2)
    assert result.success
    assert result.data["champions"][0]["name"] == "Alice"


# ---------------------------------------------------------------------------
# Tests — Campaigns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_campaign():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.create_campaign(
        name="Summer Growth", description="Grow 50%", goal="500 members"
    )
    assert result.success
    assert result.data["campaign"]["name"] == "Summer Growth"
    assert result.data["campaign"]["status"] == "active"
    assert result.data["total_campaigns"] == 1


# ---------------------------------------------------------------------------
# Tests — Growth Strategies
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_growth_strategies():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_growth_strategies()
    assert result.success
    assert len(result.data["strategies"]) == len(GROWTH_STRATEGIES)


@pytest.mark.asyncio
async def test_get_growth_strategies_filtered():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.get_growth_strategies(focus="ambassador")
    assert result.success
    assert any("Ambassador" in s["name"] for s in result.data["strategies"])


# ---------------------------------------------------------------------------
# Tests — Content Calendar
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_content_calendar():
    skill = _make_skill()
    await skill.initialize()
    result = await skill.generate_content_calendar(weeks=2, platform="twitter")
    assert result.success
    assert result.data["weeks"] == 2
    assert result.data["platform"] == "twitter"
    assert len(result.data["calendar"]) == 2
    assert result.data["posts_per_week"] == 5
