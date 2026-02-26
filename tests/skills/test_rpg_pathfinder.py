"""
Tests for the rpg_pathfinder skill (Layer 3 — domain).

Covers:
- Dice rolling and parsing
- Degree of success calculation
- Ability modifier / proficiency bonus
- Skill checks, attack rolls, saving throws
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from aria_skills.base import SkillConfig, SkillResult, SkillStatus
from aria_skills.rpg_pathfinder import (
    RPGPathfinderSkill,
    roll_dice,
    degree_of_success,
    get_ability_modifier,
    get_proficiency_bonus,
    MAP_PENALTIES,
    MAP_PENALTIES_AGILE,
)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------

def test_roll_dice_basic():
    result = roll_dice("1d20")
    assert 1 <= result["total"] <= 20
    assert len(result["rolls"]) == 1
    assert result["modifier"] == 0


def test_roll_dice_with_modifier():
    result = roll_dice("1d20+5")
    assert result["modifier"] == 5
    assert result["total"] == result["rolls"][0] + 5


def test_roll_dice_negative_modifier():
    result = roll_dice("2d6-2")
    assert result["modifier"] == -2
    assert len(result["rolls"]) == 2


def test_roll_dice_no_count():
    result = roll_dice("d8")
    assert 1 <= result["total"] <= 8
    assert len(result["rolls"]) == 1


def test_roll_dice_invalid():
    with pytest.raises(ValueError):
        roll_dice("not_dice")


def test_degree_of_success_critical_success():
    assert degree_of_success(30, 20) == "critical_success"


def test_degree_of_success_success():
    assert degree_of_success(22, 20) == "success"


def test_degree_of_success_failure():
    assert degree_of_success(15, 20) == "failure"


def test_degree_of_success_critical_failure():
    assert degree_of_success(5, 20) == "critical_failure"


def test_degree_of_success_nat20_upgrade():
    # A failure (15 vs DC 20) + nat 20 → success
    assert degree_of_success(15, 20, natural_20=True) == "success"


def test_degree_of_success_nat1_downgrade():
    # A success (22 vs DC 20) + nat 1 → failure
    assert degree_of_success(22, 20, natural_1=True) == "failure"


def test_ability_modifier():
    assert get_ability_modifier(10) == 0
    assert get_ability_modifier(14) == 2
    assert get_ability_modifier(8) == -1
    assert get_ability_modifier(20) == 5


def test_proficiency_bonus_untrained():
    assert get_proficiency_bonus("untrained", 5) == 0


def test_proficiency_bonus_trained():
    # trained = 2 + level
    assert get_proficiency_bonus("trained", 5) == 7


def test_proficiency_bonus_legendary():
    assert get_proficiency_bonus("legendary", 10) == 18


# ---------------------------------------------------------------------------
# Skill lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_initialize(tmp_path):
    with patch("aria_skills.rpg_pathfinder.CHARACTERS_DIR", tmp_path / "characters"), \
         patch("aria_skills.rpg_pathfinder.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_pathfinder.RPG_ROOT", tmp_path):
        skill = RPGPathfinderSkill(SkillConfig(name="rpg_pathfinder"))
        ok = await skill.initialize()
    assert ok is True
    assert skill._status == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# Skill methods (dice seeded for determinism)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_roll(tmp_path):
    with patch("aria_skills.rpg_pathfinder.CHARACTERS_DIR", tmp_path / "characters"), \
         patch("aria_skills.rpg_pathfinder.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_pathfinder.RPG_ROOT", tmp_path):
        skill = RPGPathfinderSkill(SkillConfig(name="rpg_pathfinder"))
        await skill.initialize()
        result = await skill.roll(expression="2d6+4", reason="Fire damage")
    assert result.success
    assert "total" in result.data
    assert result.data["reason"] == "Fire damage"


@pytest.mark.asyncio
async def test_skill_check(tmp_path):
    with patch("aria_skills.rpg_pathfinder.CHARACTERS_DIR", tmp_path / "characters"), \
         patch("aria_skills.rpg_pathfinder.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_pathfinder.RPG_ROOT", tmp_path), \
         patch("aria_skills.rpg_pathfinder.roll_dice", return_value={
             "total": 15, "rolls": [15], "natural_20": False, "natural_1": False,
         }):
        skill = RPGPathfinderSkill(SkillConfig(name="rpg_pathfinder"))
        await skill.initialize()
        result = await skill.check(modifier=7, dc=20, reason="Athletics")
    assert result.success
    assert result.data["degree"] in ("success", "failure", "critical_success", "critical_failure")


@pytest.mark.asyncio
async def test_skill_attack(tmp_path):
    with patch("aria_skills.rpg_pathfinder.CHARACTERS_DIR", tmp_path / "characters"), \
         patch("aria_skills.rpg_pathfinder.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_pathfinder.RPG_ROOT", tmp_path):
        skill = RPGPathfinderSkill(SkillConfig(name="rpg_pathfinder"))
        await skill.initialize()
        result = await skill.attack(
            attack_bonus=12, target_ac=18,
            damage_expression="1d8+4",
            attack_number=1,
        )
    assert result.success
    assert "damage" in result.data
    assert "degree" in result.data


@pytest.mark.asyncio
async def test_skill_saving_throw(tmp_path):
    with patch("aria_skills.rpg_pathfinder.CHARACTERS_DIR", tmp_path / "characters"), \
         patch("aria_skills.rpg_pathfinder.ENCOUNTERS_DIR", tmp_path / "encounters"), \
         patch("aria_skills.rpg_pathfinder.RPG_ROOT", tmp_path):
        skill = RPGPathfinderSkill(SkillConfig(name="rpg_pathfinder"))
        await skill.initialize()
        result = await skill.saving_throw(save_bonus=10, dc=18, save_type="reflex")
    assert result.success
    assert result.data["save_type"] == "reflex"
