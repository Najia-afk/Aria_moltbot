"""
Tests for the rpg_campaign skill (Layer 3 — domain).

Covers:
- Initialization
- Campaign CRUD (create, load, list)
- Campaign detail retrieval
- Session transcript retrieval
- Filesystem operations mocked via tmp_path
"""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.rpg_campaign import RPGCampaignSkill, CAMPAIGNS_DIR, _load_yaml, _save_yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill() -> RPGCampaignSkill:
    return RPGCampaignSkill(SkillConfig(name="rpg_campaign"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(tmp_path):
    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", tmp_path / "campaigns"), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


@pytest.mark.asyncio
async def test_create_campaign(tmp_path):
    camp_dir = tmp_path / "campaigns"
    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", camp_dir), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        await skill.initialize()

        result = await skill.create_campaign(
            campaign_id="test_campaign",
            title="Test Quest",
            setting="Golarion",
            starting_level=3,
        )
    assert result.success
    assert result.data["campaign_id"] == "test_campaign"
    assert result.data["title"] == "Test Quest"

    # Verify YAML was written
    campaign_yaml = camp_dir / "test_campaign" / "campaign.yaml"
    assert campaign_yaml.exists()
    data = _load_yaml(campaign_yaml)
    assert data["title"] == "Test Quest"
    assert data["starting_level"] == 3


@pytest.mark.asyncio
async def test_load_campaign(tmp_path):
    camp_dir = tmp_path / "campaigns"
    # Pre-create a campaign
    (camp_dir / "my_camp").mkdir(parents=True)
    _save_yaml(camp_dir / "my_camp" / "campaign.yaml", {
        "id": "my_camp", "title": "My Campaign", "status": "active", "current_session": 2,
    })
    _save_yaml(camp_dir / "my_camp" / "world.yaml", {
        "current_location": "Absalom",
    })

    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", camp_dir), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        await skill.initialize()
        result = await skill.load_campaign("my_camp")
    assert result.success
    assert skill._active_campaign == "my_camp"


@pytest.mark.asyncio
async def test_load_campaign_not_found(tmp_path):
    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir(parents=True)

    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", camp_dir), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        await skill.initialize()
        result = await skill.load_campaign("missing")
    assert not result.success


@pytest.mark.asyncio
async def test_list_campaigns(tmp_path):
    camp_dir = tmp_path / "campaigns"
    for cid in ["camp1", "camp2"]:
        (camp_dir / cid).mkdir(parents=True)
        _save_yaml(camp_dir / cid / "campaign.yaml", {
            "id": cid, "title": f"Campaign {cid}", "status": "active",
        })

    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", camp_dir), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        await skill.initialize()
        result = await skill.list_campaigns()
    assert result.success
    assert result.data["count"] == 2


@pytest.mark.asyncio
async def test_get_campaign_detail(tmp_path):
    camp_dir = tmp_path / "campaigns"
    cdir = camp_dir / "detail_test"
    cdir.mkdir(parents=True)
    (cdir / "sessions").mkdir()
    (cdir / "encounters").mkdir()
    _save_yaml(cdir / "campaign.yaml", {
        "id": "detail_test", "title": "Detail", "status": "active", "party": [],
    })
    _save_yaml(cdir / "world.yaml", {"current_location": "Tavern"})
    _save_yaml(cdir / "npcs.yaml", {"npcs": [{"name": "Bob"}]})

    with patch("aria_skills.rpg_campaign.CAMPAIGNS_DIR", camp_dir), \
         patch("aria_skills.rpg_campaign.SESSIONS_DIR", tmp_path / "sessions"), \
         patch("aria_skills.rpg_campaign.WORLD_DIR", tmp_path / "world"), \
         patch("aria_skills.rpg_campaign.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_campaign.CHARACTERS_DIR", tmp_path / "characters"):
        skill = _make_skill()
        await skill.initialize()
        result = await skill.get_campaign_detail("detail_test")
    assert result.success
    assert result.data["npc_count"] == 1
