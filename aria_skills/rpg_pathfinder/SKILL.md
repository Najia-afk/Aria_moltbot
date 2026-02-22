---
name: aria-rpg-pathfinder
description: "Pathfinder 2e rules engine — dice rolls, combat resolution, character and condition management for Aria's tabletop RPG system."
metadata: {"aria": {"emoji": "🎲"}}
---

# aria-rpg-pathfinder

**Layer 3 — Domain** | **Status: active** | **v1.0.0**

Pathfinder 2e mechanical resolution engine. Handles dice rolls, skill checks, attack resolution (with MAP), saving throws, spell casting, initiative tracking, condition management, HP tracking, XP awards, and character sheet I/O.

All game state is persisted to `aria_memories/rpg/`.

## Dependencies

| Dependency | Layer | Purpose |
|------------|-------|---------|
| `api_client` | 1 | HTTP/DB gateway (required by standard) |

## Focus Affinity

| Focus | Role |
|-------|------|
| `rpg_master` | Primary — runs full RPG sessions |
| `orchestrator` | Coordination — delegates RPG tasks |

## Storage

| Path | Contents |
|------|----------|
| `aria_memories/rpg/characters/` | Character sheets (YAML) |
| `aria_memories/rpg/encounters/` | Encounter state files |
| `aria_memories/rpg/sessions/` | Session transcripts |

## Usage

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder <tool> '<json_args>'
```

## Tools

### roll
Roll dice using standard Pathfinder notation (e.g., `1d20+12`, `2d6+4`). Returns individual rolls, total, and natural 20/1 detection.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder roll '{"expression": "1d20+7", "reason": "Perception check"}'
```

### check
Make a Pathfinder 2e check (d20 + modifier vs DC) with full degree of success calculation: critical success, success, failure, critical failure.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder check '{"modifier": 12, "dc": 20, "reason": "Athletics to Grapple"}'
```

### attack
Resolve an attack roll with MAP (Multiple Attack Penalty), damage, and critical hit detection.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder attack '{"attack_bonus": 14, "target_ac": 18, "damage_expression": "1d8+4", "attack_number": 1}'
# Second attack with MAP
exec python3 /app/skills/run_skill.py rpg_pathfinder attack '{"attack_bonus": 14, "target_ac": 18, "damage_expression": "1d8+4", "attack_number": 2, "agile": false}'
```

**MAP table:**
| Attack # | Standard | Agile |
|----------|----------|-------|
| 1 | +0 | +0 |
| 2 | -5 | -4 |
| 3 | -10 | -8 |

### saving_throw
Resolve a saving throw (Fortitude, Reflex, or Will) against a DC.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder saving_throw '{"save_bonus": 10, "dc": 22, "save_type": "reflex", "reason": "Fireball"}'
```

### cast_spell
Resolve a spell cast with optional save, damage, or healing components.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder cast_spell '{"spell_name": "Heal", "spell_level": 1, "healing_expression": "1d8+8"}'
exec python3 /app/skills/run_skill.py rpg_pathfinder cast_spell '{"spell_name": "Fireball", "spell_level": 3, "spell_dc": 23, "damage_expression": "6d6", "save_type": "reflex", "target_save_bonus": 12}'
```

### load_character_sheet
Load and display a character sheet from `aria_memories/rpg/characters/`.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder load_character_sheet '{"character_file": "shiva_kael_stormwind"}'
```

### list_characters
List all available player character sheets.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder list_characters '{}'
```

### update_hp
Update a character's HP. Positive for healing, negative for damage.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder update_hp '{"character_file": "shiva_kael_stormwind", "hp_change": -12, "reason": "Goblin crit"}'
```

### add_condition
Add a Pathfinder 2e condition to a character.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder add_condition '{"character_file": "shiva_kael_stormwind", "condition": "frightened", "value": 2}'
```

### remove_condition
Remove a condition from a character.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder remove_condition '{"character_file": "shiva_kael_stormwind", "condition": "frightened"}'
```

### roll_initiative
Roll initiative for all combatants and establish turn order.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder roll_initiative '{"combatants": [{"name": "Kael", "modifier": 7, "is_player": true}, {"name": "Goblin Warrior", "modifier": 3}]}'
```

### next_turn
Advance to the next combatant's turn in initiative order.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder next_turn '{}'
```

### end_encounter
End the current encounter and clear initiative.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder end_encounter '{}'
```

### award_xp
Award XP to a character and check for level up (1000 XP per level).

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder award_xp '{"character_file": "shiva_kael_stormwind", "xp": 120, "reason": "Defeated goblin patrol"}'
```

### lookup_condition
Look up a Pathfinder 2e condition's rules text.

```bash
exec python3 /app/skills/run_skill.py rpg_pathfinder lookup_condition '{"condition": "frightened"}'
```

## Pathfinder 2e Rules Reference

### Degrees of Success
- **Critical Success**: Beat DC by 10+ or natural 20 upgrades success
- **Success**: Meet or beat DC
- **Failure**: Miss DC
- **Critical Failure**: Miss DC by 10+ or natural 1 downgrades failure

### Proficiency Ranks
| Rank | Bonus |
|------|-------|
| Untrained | +0 |
| Trained | +2 |
| Expert | +4 |
| Master | +6 |
| Legendary | +8 |

Total modifier = ability mod + proficiency bonus + level (if trained+).

## Python Module

Class: `RPGPathfinderSkill`
Module: `aria_skills.rpg_pathfinder`
