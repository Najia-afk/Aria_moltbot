"""
RPG Pathfinder 2e Rules Engine — Dice, combat, spells, conditions, and character management.

Provides Pathfinder 2e mechanical resolution for Aria's tabletop RPG system.
All game state persisted to aria_memories/rpg/.
"""
from __future__ import annotations

import json
import logging
import math
import os
import random
from pathlib import Path
from typing import Any

import yaml

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skill.rpg_pathfinder")

# ── Constants ────────────────────────────────────────────────────────────────

RPG_ROOT = Path("aria_memories/rpg")
CHARACTERS_DIR = RPG_ROOT / "characters"
ENCOUNTERS_DIR = RPG_ROOT / "encounters"

# Proficiency bonuses by rank
PROFICIENCY_BONUS = {
    "untrained": 0,
    "trained": 2,
    "expert": 4,
    "master": 6,
    "legendary": 8,
}

# Conditions that have a numeric value (value decreases by 1 each turn/event)
VALUED_CONDITIONS = {
    "clumsy", "doomed", "drained", "enfeebled", "frightened",
    "sickened", "slowed", "stunned", "stupefied", "wounded",
}

# Multiple Attack Penalty
MAP_PENALTIES = {1: 0, 2: -5, 3: -10}
MAP_PENALTIES_AGILE = {1: 0, 2: -4, 3: -8}


# ── Dice Engine ──────────────────────────────────────────────────────────────

def roll_dice(expression: str) -> dict[str, Any]:
    """
    Roll dice using standard notation: NdX+M, NdX-M, NdX, dX.
    
    Supports: 1d20, 2d6+4, 4d8-2, d20, 1d20+12, etc.
    Returns individual rolls, total, and expression.
    """
    expression = expression.strip().lower().replace(" ", "")
    
    # Parse: optional(N)d(X) optional(+/-)(M)
    import re
    match = re.match(r"(\d*)d(\d+)([+-]\d+)?", expression)
    if not match:
        raise ValueError(f"Invalid dice expression: {expression}")
    
    num_dice = int(match.group(1)) if match.group(1) else 1
    die_size = int(match.group(2))
    modifier = int(match.group(3)) if match.group(3) else 0
    
    rolls = [random.randint(1, die_size) for _ in range(num_dice)]
    subtotal = sum(rolls)
    total = subtotal + modifier
    
    return {
        "expression": expression,
        "rolls": rolls,
        "subtotal": subtotal,
        "modifier": modifier,
        "total": total,
        "natural_20": die_size == 20 and num_dice == 1 and rolls[0] == 20,
        "natural_1": die_size == 20 and num_dice == 1 and rolls[0] == 1,
    }


def degree_of_success(roll_total: int, dc: int, natural_20: bool = False, natural_1: bool = False) -> str:
    """
    Determine Pathfinder 2e degree of success.
    
    Natural 20 improves by one step. Natural 1 worsens by one step.
    """
    if roll_total >= dc + 10:
        degree = "critical_success"
    elif roll_total >= dc:
        degree = "success"
    elif roll_total <= dc - 10:
        degree = "critical_failure"
    else:
        degree = "failure"
    
    # Natural 20/1 adjustment
    degrees = ["critical_failure", "failure", "success", "critical_success"]
    idx = degrees.index(degree)
    
    if natural_20:
        idx = min(idx + 1, 3)
    if natural_1:
        idx = max(idx - 1, 0)
    
    return degrees[idx]


# ── Character Helpers ────────────────────────────────────────────────────────

def load_character(filename: str) -> dict[str, Any]:
    """Load a character sheet from aria_memories/rpg/characters/."""
    path = CHARACTERS_DIR / filename
    if not path.exists():
        # Try with .yaml extension
        path = CHARACTERS_DIR / f"{filename}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Character not found: {filename}")
    
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_character(filename: str, data: dict[str, Any]) -> Path:
    """Save a character sheet to aria_memories/rpg/characters/."""
    CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
    if not filename.endswith(".yaml"):
        filename = f"{filename}.yaml"
    path = CHARACTERS_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def get_ability_modifier(score: int) -> int:
    """Calculate ability modifier from score."""
    return math.floor((score - 10) / 2)


def get_proficiency_bonus(rank: str, level: int) -> int:
    """Calculate proficiency bonus: rank bonus + level (if trained+)."""
    bonus = PROFICIENCY_BONUS.get(rank.lower(), 0)
    if bonus > 0:  # Trained or better adds level
        bonus += level
    return bonus


# ── Skill Implementation ────────────────────────────────────────────────────

@SkillRegistry.register
class RPGPathfinderSkill(BaseSkill):
    """Pathfinder 2e rules engine — dice rolls, combat resolution, character management."""

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._active_encounter: dict[str, Any] | None = None
        self._initiative_order: list[dict[str, Any]] = []
        self._current_round: int = 0
        self._current_turn_idx: int = 0

    @property
    def name(self) -> str:
        return "rpg_pathfinder"

    async def initialize(self) -> bool:
        """Initialize the RPG skill and ensure directories exist."""
        for d in [CHARACTERS_DIR, ENCOUNTERS_DIR, RPG_ROOT / "sessions", RPG_ROOT / "world"]:
            d.mkdir(parents=True, exist_ok=True)
        self._status = SkillStatus.AVAILABLE
        self.logger.info("RPG Pathfinder skill initialized")
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    # ── Dice Tools ───────────────────────────────────────────────────────

    @logged_method()
    async def roll(self, expression: str, reason: str = "") -> SkillResult:
        """
        Roll dice using Pathfinder notation.

        Args:
            expression: Dice expression (e.g., "1d20+12", "2d6+4", "4d8")
            reason: Optional reason for the roll (e.g., "Longsword attack")

        Returns:
            SkillResult with roll details.
        """
        try:
            result = roll_dice(expression)
            result["reason"] = reason
            summary = f"🎲 {expression} = {result['rolls']} + {result['modifier']} = **{result['total']}**"
            if result.get("natural_20"):
                summary += " ✨ NAT 20!"
            elif result.get("natural_1"):
                summary += " 💀 NAT 1!"
            if reason:
                summary = f"[{reason}] {summary}"
            result["summary"] = summary
            return SkillResult.ok(result)
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def check(self, modifier: int, dc: int, reason: str = "") -> SkillResult:
        """
        Make a Pathfinder 2e check: d20 + modifier vs DC.

        Args:
            modifier: Total modifier to add to d20.
            dc: Difficulty Class to beat.
            reason: Optional reason (e.g., "Athletics check to Grapple")

        Returns:
            SkillResult with roll, degree of success, and narrative.
        """
        try:
            d20 = roll_dice("1d20")
            total = d20["total"] + modifier
            deg = degree_of_success(
                total, dc,
                natural_20=d20.get("natural_20", False),
                natural_1=d20.get("natural_1", False),
            )
            result = {
                "d20": d20["rolls"][0],
                "modifier": modifier,
                "total": total,
                "dc": dc,
                "degree": deg,
                "natural_20": d20.get("natural_20", False),
                "natural_1": d20.get("natural_1", False),
                "reason": reason,
            }
            
            deg_display = deg.replace("_", " ").title()
            summary = f"🎲 d20({d20['rolls'][0]}) + {modifier} = {total} vs DC {dc} → **{deg_display}**"
            if reason:
                summary = f"[{reason}] {summary}"
            result["summary"] = summary
            return SkillResult.ok(result)
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def attack(
        self,
        attack_bonus: int,
        target_ac: int,
        damage_expression: str,
        attack_number: int = 1,
        agile: bool = False,
        reason: str = "",
    ) -> SkillResult:
        """
        Resolve an attack roll with MAP (Multiple Attack Penalty).

        Args:
            attack_bonus: Base attack bonus.
            target_ac: Target's Armor Class.
            damage_expression: Damage dice (e.g., "1d8+4").
            attack_number: Which attack this turn (1, 2, or 3).
            agile: Whether weapon has agile trait.
            reason: Attack description.

        Returns:
            SkillResult with hit/miss, damage, and degree of success.
        """
        try:
            # Apply MAP
            penalties = MAP_PENALTIES_AGILE if agile else MAP_PENALTIES
            map_penalty = penalties.get(min(attack_number, 3), -10)
            effective_bonus = attack_bonus + map_penalty

            d20 = roll_dice("1d20")
            total = d20["total"] + effective_bonus
            deg = degree_of_success(
                total, target_ac,
                natural_20=d20.get("natural_20", False),
                natural_1=d20.get("natural_1", False),
            )

            result = {
                "d20": d20["rolls"][0],
                "attack_bonus": attack_bonus,
                "map_penalty": map_penalty,
                "effective_bonus": effective_bonus,
                "total": total,
                "target_ac": target_ac,
                "degree": deg,
                "natural_20": d20.get("natural_20", False),
                "natural_1": d20.get("natural_1", False),
                "reason": reason,
            }

            # Resolve damage
            if deg in ("success", "critical_success"):
                dmg = roll_dice(damage_expression)
                damage = dmg["total"]
                if deg == "critical_success":
                    damage *= 2  # Double damage on crit
                result["damage"] = damage
                result["damage_rolls"] = dmg["rolls"]
                result["critical"] = deg == "critical_success"
            else:
                result["damage"] = 0
                result["critical"] = False

            # Build summary
            deg_display = deg.replace("_", " ").title()
            summary = f"⚔️ d20({d20['rolls'][0]}) + {effective_bonus} = {total} vs AC {target_ac} → **{deg_display}**"
            if map_penalty:
                summary += f" (MAP {map_penalty})"
            if result["damage"]:
                crit_tag = " 💥 CRIT!" if result["critical"] else ""
                summary += f" → {result['damage']} damage{crit_tag}"
            if reason:
                summary = f"[{reason}] {summary}"
            result["summary"] = summary
            return SkillResult.ok(result)
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def saving_throw(
        self,
        save_bonus: int,
        dc: int,
        save_type: str = "fortitude",
        reason: str = "",
    ) -> SkillResult:
        """
        Resolve a saving throw.

        Args:
            save_bonus: Total save bonus.
            dc: Difficulty Class (usually spell DC).
            save_type: "fortitude", "reflex", or "will".
            reason: What triggered the save.
        """
        try:
            result_data = await self.check(save_bonus, dc, reason=f"{save_type.title()} Save: {reason}")
            if result_data.success:
                result_data.data["save_type"] = save_type
            return result_data
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Character Management ─────────────────────────────────────────────

    @logged_method()
    async def load_character_sheet(self, character_file: str) -> SkillResult:
        """
        Load and display a character sheet.

        Args:
            character_file: Filename in aria_memories/rpg/characters/ (with or without .yaml).
        """
        try:
            char = load_character(character_file)
            return SkillResult.ok(char)
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def list_characters(self) -> SkillResult:
        """List all available character sheets."""
        try:
            CHARACTERS_DIR.mkdir(parents=True, exist_ok=True)
            chars = []
            for f in CHARACTERS_DIR.glob("*.yaml"):
                try:
                    data = yaml.safe_load(f.read_text(encoding="utf-8"))
                    chars.append({
                        "file": f.name,
                        "player": data.get("player", "Unknown"),
                        "name": data.get("character", {}).get("name", "Unknown"),
                        "class": data.get("character", {}).get("class", "Unknown"),
                        "level": data.get("character", {}).get("level", 0),
                    })
                except Exception:
                    chars.append({"file": f.name, "error": "Could not parse"})
            return SkillResult.ok({"characters": chars, "count": len(chars)})
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def update_hp(self, character_file: str, hp_change: int, reason: str = "") -> SkillResult:
        """
        Update a character's HP (positive = heal, negative = damage).

        Args:
            character_file: Character filename.
            hp_change: Amount to change HP by (+heal, -damage).
            reason: Why HP changed.
        """
        try:
            char = load_character(character_file)
            hp = char.get("hit_points", {})
            old_hp = hp.get("current", 0)
            max_hp = hp.get("max", 0)
            new_hp = max(0, min(old_hp + hp_change, max_hp))
            hp["current"] = new_hp
            char["hit_points"] = hp
            
            save_character(character_file, char)
            
            action = "healed" if hp_change > 0 else "damaged"
            summary = f"❤️ {char['character']['name']}: {old_hp} → {new_hp}/{max_hp} HP ({action} {abs(hp_change)})"
            if reason:
                summary += f" [{reason}]"
            if new_hp == 0:
                summary += " ☠️ DOWN!"
            
            return SkillResult.ok({
                "character": char["character"]["name"],
                "old_hp": old_hp,
                "new_hp": new_hp,
                "max_hp": max_hp,
                "change": hp_change,
                "summary": summary,
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def add_condition(self, character_file: str, condition: str, value: int = 0) -> SkillResult:
        """
        Add a condition to a character.

        Args:
            character_file: Character filename.
            condition: Condition name (e.g., "frightened", "prone").
            value: Condition value (for valued conditions like frightened 2).
        """
        try:
            char = load_character(character_file)
            conditions = char.get("conditions", [])
            
            # Remove existing instance of same condition
            conditions = [c for c in conditions if (c if isinstance(c, str) else c.get("name", "")) != condition]
            
            if condition.lower() in VALUED_CONDITIONS and value > 0:
                conditions.append({"name": condition, "value": value})
            else:
                conditions.append(condition)
            
            char["conditions"] = conditions
            save_character(character_file, char)

            cond_str = f"{condition} {value}" if value else condition
            return SkillResult.ok({
                "character": char["character"]["name"],
                "condition_added": cond_str,
                "all_conditions": conditions,
                "summary": f"📋 {char['character']['name']} is now {cond_str}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def remove_condition(self, character_file: str, condition: str) -> SkillResult:
        """
        Remove a condition from a character.

        Args:
            character_file: Character filename.
            condition: Condition name to remove.
        """
        try:
            char = load_character(character_file)
            conditions = char.get("conditions", [])
            conditions = [
                c for c in conditions
                if (c if isinstance(c, str) else c.get("name", "")) != condition
            ]
            char["conditions"] = conditions
            save_character(character_file, char)

            return SkillResult.ok({
                "character": char["character"]["name"],
                "condition_removed": condition,
                "all_conditions": conditions,
                "summary": f"✅ {char['character']['name']}: {condition} removed",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Initiative & Encounter ───────────────────────────────────────────

    @logged_method()
    async def roll_initiative(self, combatants: list[dict[str, Any]]) -> SkillResult:
        """
        Roll initiative for all combatants and set turn order.

        Args:
            combatants: List of dicts with "name", "modifier", and optional "is_player".
                Example: [{"name": "Kael", "modifier": 9, "is_player": true},
                          {"name": "Goblin Warrior", "modifier": 5}]
        """
        try:
            results = []
            for c in combatants:
                d20 = roll_dice("1d20")
                total = d20["total"] + c["modifier"]
                results.append({
                    "name": c["name"],
                    "d20": d20["rolls"][0],
                    "modifier": c["modifier"],
                    "total": total,
                    "is_player": c.get("is_player", False),
                    "natural_20": d20.get("natural_20", False),
                })
            
            # Sort by total (descending), ties broken by modifier
            results.sort(key=lambda x: (x["total"], x["modifier"]), reverse=True)
            
            self._initiative_order = results
            self._current_round = 1
            self._current_turn_idx = 0
            
            summary_lines = ["⚡ **Initiative Order:**"]
            for i, r in enumerate(results, 1):
                nat = " (NAT 20!)" if r["natural_20"] else ""
                player_tag = " 🎮" if r["is_player"] else " 🎭"
                summary_lines.append(f"  {i}. **{r['name']}**: {r['total']} (d20={r['d20']}+{r['modifier']}){nat}{player_tag}")
            
            return SkillResult.ok({
                "initiative_order": results,
                "round": self._current_round,
                "summary": "\n".join(summary_lines),
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def next_turn(self) -> SkillResult:
        """Advance to the next combatant's turn in initiative order."""
        try:
            if not self._initiative_order:
                return SkillResult.fail("No active initiative order. Roll initiative first.")
            
            current = self._initiative_order[self._current_turn_idx]
            
            # Advance
            self._current_turn_idx += 1
            if self._current_turn_idx >= len(self._initiative_order):
                self._current_turn_idx = 0
                self._current_round += 1
            
            next_up = self._initiative_order[self._current_turn_idx]
            
            return SkillResult.ok({
                "current_round": self._current_round,
                "just_acted": current["name"],
                "next_up": next_up["name"],
                "is_player_turn": next_up.get("is_player", False),
                "turn_index": self._current_turn_idx,
                "summary": f"🔄 Round {self._current_round} — **{next_up['name']}**'s turn!",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def end_encounter(self) -> SkillResult:
        """End the current encounter and clear initiative."""
        self._initiative_order = []
        self._current_round = 0
        self._current_turn_idx = 0
        return SkillResult.ok({
            "summary": "🏁 Encounter ended. Initiative cleared.",
        })

    # ── XP & Leveling ───────────────────────────────────────────────────

    @logged_method()
    async def award_xp(self, character_file: str, xp: int, reason: str = "") -> SkillResult:
        """
        Award XP to a character and check for level up.

        Args:
            character_file: Character filename.
            xp: XP to award.
            reason: Source of XP.
        """
        try:
            char = load_character(character_file)
            old_xp = char["character"].get("experience", 0)
            new_xp = old_xp + xp
            char["character"]["experience"] = new_xp
            
            level = char["character"].get("level", 1)
            xp_for_next = level * 1000  # PF2e: 1000 XP per level
            leveled_up = new_xp >= xp_for_next
            
            if leveled_up:
                char["character"]["level"] = level + 1
                char["character"]["experience"] = new_xp - xp_for_next
                new_xp = char["character"]["experience"]
            
            save_character(character_file, char)
            
            summary = f"⭐ {char['character']['name']}: +{xp} XP ({new_xp}/{xp_for_next})"
            if reason:
                summary += f" [{reason}]"
            if leveled_up:
                summary += f" 🎉 **LEVEL UP! Now level {level + 1}!**"
            
            return SkillResult.ok({
                "character": char["character"]["name"],
                "xp_awarded": xp,
                "total_xp": new_xp,
                "level": char["character"]["level"],
                "leveled_up": leveled_up,
                "summary": summary,
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Spell Resolution ─────────────────────────────────────────────────

    @logged_method()
    async def cast_spell(
        self,
        spell_name: str,
        spell_level: int,
        spell_dc: int = 0,
        damage_expression: str = "",
        healing_expression: str = "",
        save_type: str = "",
        target_save_bonus: int = 0,
        reason: str = "",
    ) -> SkillResult:
        """
        Resolve a spell cast with optional attack/save/damage/healing.

        Args:
            spell_name: Name of the spell.
            spell_level: Spell level (0 for cantrips).
            spell_dc: Caster's spell DC (for save spells).
            damage_expression: Damage dice if applicable.
            healing_expression: Healing dice if applicable.
            save_type: "fortitude", "reflex", or "will" if save required.
            target_save_bonus: Target's save bonus.
            reason: Additional context.
        """
        try:
            result = {
                "spell_name": spell_name,
                "spell_level": spell_level,
                "reason": reason,
            }
            
            summary_parts = [f"✨ **{spell_name}** (Level {spell_level})"]

            if save_type and spell_dc:
                save_result = await self.saving_throw(
                    target_save_bonus, spell_dc, save_type, reason=spell_name
                )
                if save_result.success:
                    result["save"] = save_result.data
                    summary_parts.append(save_result.data.get("summary", ""))
            
            if damage_expression:
                dmg = roll_dice(damage_expression)
                # Adjust damage based on save degree
                save_degree = result.get("save", {}).get("degree", "failure")
                if save_degree == "critical_success":
                    dmg["total"] = 0
                    summary_parts.append(f"Damage: 0 (Critical save negates)")
                elif save_degree == "success":
                    dmg["total"] = dmg["total"] // 2
                    summary_parts.append(f"Damage: {dmg['total']} (halved on save)")
                elif save_degree == "critical_failure":
                    dmg["total"] *= 2
                    summary_parts.append(f"Damage: {dmg['total']} 💥 (doubled on critical fail)")
                else:
                    summary_parts.append(f"Damage: {dmg['total']}")
                result["damage"] = dmg
            
            if healing_expression:
                heal = roll_dice(healing_expression)
                result["healing"] = heal
                summary_parts.append(f"Healing: {heal['total']} HP")
            
            result["summary"] = " | ".join(summary_parts)
            return SkillResult.ok(result)
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Utility ──────────────────────────────────────────────────────────

    @logged_method()
    async def lookup_condition(self, condition: str) -> SkillResult:
        """
        Look up a Pathfinder 2e condition's rules.

        Args:
            condition: Condition name.
        """
        CONDITION_RULES = {
            "blinded": "Cannot see. All terrain is difficult terrain. Auto-fail vision checks. Flat-footed. -4 to Perception.",
            "clumsy": "Penalty equal to value on DEX-based checks and DCs.",
            "confused": "Can't use reactions or concentrate. Attacks random adjacent creature or does nothing.",
            "dazzled": "-2 to attack rolls and vision-based Perception checks.",
            "doomed": "Die at dying value = 4 - doomed value. Decreases by 1 on full rest.",
            "drained": "Lose HP equal to level × value. Penalty to CON-based checks. Decreases by 1 on full rest.",
            "dying": "Unconscious. At start of turn: flat DC 10 recovery check. Die at dying 4. Stabilize at dying 0 → unconscious.",
            "encumbered": "Clumsy 1. -10 ft speed.",
            "enfeebled": "Penalty equal to value on STR-based checks and damage.",
            "fatigued": "-1 to AC and saves. Can't use exploration activities. Removed on full rest.",
            "flat-footed": "-2 to AC.",
            "fleeing": "Must spend actions to move away from source.",
            "frightened": "Penalty equal to value on all checks and DCs. Decreases by 1 at end of each turn.",
            "grabbed": "Immobilized. Flat-footed. Can't use manipulate actions unless to Escape.",
            "hidden": "Creatures unsure of your location. DC 11 flat check to target you.",
            "immobilized": "Cannot use movement. Can be teleported.",
            "invisible": "Undetected to vision. Can be heard/sensed otherwise.",
            "paralyzed": "Can't move or take actions. Flat-footed.",
            "petrified": "Turned to stone. Can't move or act. Immune to most damage.",
            "prone": "Flat-footed. -2 to attack rolls. Takes a move action to Stand.",
            "quickened": "Gain 1 extra action per turn (limited use).",
            "restrained": "Immobilized. Flat-footed. -2 to attack rolls.",
            "sickened": "Penalty equal to value on all checks and DCs. Must succeed flat check to use manipulate actions.",
            "slowed": "Lose actions equal to value at start of turn.",
            "stunned": "Lose actions equal to value at start of turn. Then value drops to 0.",
            "stupefied": "Penalty equal to value on INT/WIS/CHA checks. Flat check to cast spells.",
            "unconscious": "AC -4 penalty. Flat-footed. Perception -5. Special rules for waking.",
            "wounded": "Next time you gain dying, add wounded value to dying value.",
        }
        
        rule = CONDITION_RULES.get(condition.lower())
        if rule:
            return SkillResult.ok({
                "condition": condition,
                "rules": rule,
                "summary": f"📖 **{condition.title()}**: {rule}",
            })
        return SkillResult.fail(f"Unknown condition: {condition}")
