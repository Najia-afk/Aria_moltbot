---
name: aria-rpg-campaign
description: "Campaign state management — sessions, world state, encounters, NPCs, quests, party, and calendar for Aria's Pathfinder 2e RPG system."
metadata: {"aria": {"emoji": "📜"}}
---

# aria-rpg-campaign

**Layer 3 — Domain** | **Status: active** | **v1.0.0**

Campaign lifecycle management for Pathfinder 2e. Create campaigns, manage sessions, track world state, register NPCs, build encounters, generate and run quests, manage the party roster, advance the Golarion calendar, and save session transcripts.

All campaign data is persisted to `aria_memories/rpg/`.

## Dependencies

| Dependency | Layer | Purpose |
|------------|-------|---------|
| `api_client` | 1 | HTTP/DB gateway (required by standard) |

## Focus Affinity

| Focus | Role |
|-------|------|
| `rpg_master` | Primary — runs full RPG sessions and campaigns |
| `orchestrator` | Coordination — delegates campaign tasks |

## Storage

| Path | Contents |
|------|----------|
| `aria_memories/rpg/campaigns/` | Campaign state files (YAML) |
| `aria_memories/rpg/sessions/` | Session transcripts (Markdown) |
| `aria_memories/rpg/world/` | World state and calendar |
| `aria_memories/rpg/encounters/` | Encounter definitions |
| `aria_memories/rpg/characters/` | Character sheets (shared with rpg_pathfinder) |

## Companion Skill

Works closely with `rpg_pathfinder` — this skill manages **campaign state** while `rpg_pathfinder` handles **mechanical resolution** (dice, combat, conditions). Together they form the complete RPG system.

## Usage

```bash
exec python3 /app/skills/run_skill.py rpg_campaign <tool> '<json_args>'
```

## Tools — Campaign Lifecycle

### create_campaign
Create a new Pathfinder 2e campaign with world state, NPC roster, and session tracking.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign create_campaign '{"campaign_id": "crimson_throne", "title": "Curse of the Crimson Throne", "setting": "Golarion", "starting_level": 1}'
```

### load_campaign
Load an existing campaign as the active campaign.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign load_campaign '{"campaign_id": "crimson_throne"}'
```

### list_campaigns
List all available RPG campaigns.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign list_campaigns '{}'
```

## Tools — Party Management

### add_to_party
Add a character sheet to the active campaign's party.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign add_to_party '{"character_file": "shiva_kael_stormwind"}'
```

### get_party_status
Get full HP, AC, conditions, and level for all party members.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign get_party_status '{}'
```

## Tools — Session Management

### start_session
Start a new numbered game session.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign start_session '{"recap": "Last time, the party cleared the goblin caves..."}'
```

### log_event
Log a narrative, combat, social, exploration, loot, or milestone event to the session.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign log_event '{"event": "Party negotiated safe passage with the troll chief", "event_type": "social"}'
```

Event types: `narrative`, `combat`, `social`, `exploration`, `loot`, `milestone`

### end_session
End the current game session and save notes.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign end_session '{"notes": "Party reached level 2, cliffhanger at the dungeon entrance"}'
```

### save_session_transcript
Save a formatted session transcript to `aria_memories/rpg/sessions/`.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign save_session_transcript '{"title": "crimson_throne_s01", "content": "# Session 1\n...", "player_name": "Kael Stormwind", "companion_name": "Seraphina Dawnblade", "dm_name": "Aria"}'
```

## Tools — World State

### update_location
Move the party to a new location, adding it to known locations if new.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign update_location '{"location": "Sandpoint", "description": "A quiet coastal town on the Lost Coast"}'
```

### advance_time
Advance the in-game Golarion calendar by N days.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign advance_time '{"days": 3, "event": "Party rested and resupplied in town"}'
```

### get_world_state
Get the full world state: location, calendar, factions, events.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign get_world_state '{}'
```

## Tools — NPCs

### add_npc
Add a named NPC to the campaign roster with role and optional stats.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign add_npc '{"npc_name": "Ameiko Kaijitsu", "role": "friendly", "description": "Owner of the Rusty Dragon Inn", "location": "Sandpoint"}'
```

Roles: `friendly`, `neutral`, `hostile`, `boss`

### list_npcs
List NPCs in the active campaign, optionally filtered by role.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign list_npcs '{"role_filter": "hostile"}'
```

## Tools — Encounters

### create_encounter
Create a pre-built encounter with enemies, environment, loot, and XP.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign create_encounter '{"encounter_id": "goblin_ambush", "title": "Goblin Ambush", "threat_level": "moderate", "enemies": [{"name": "Goblin Warrior", "level": 1, "hp": 15, "ac": 16}], "xp_reward": 80}'
```

Threat levels: `trivial`, `low`, `moderate`, `severe`, `extreme`

### list_encounters
List encounters for the active campaign.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign list_encounters '{"status_filter": "prepared"}'
```

Status filters: `prepared`, `active`, `completed`

## Tools — Quest System

### generate_quest
Generate a reusable quest template YAML with encounters, NPCs, boss, loot, and DM instructions.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign generate_quest '{"quest_id": "goblin_warrens", "title": "The Goblin Warrens", "hook": "Goblins raided the village granary", "setting_location": "Sandpoint", "target_level_start": 1, "target_level_end": 2, "tone": "heroic", "party_characters": ["shiva_kael_stormwind"], "encounter_sequence": [{"id": "ambush_01", "title": "Goblin Patrol", "type": "combat", "threat_level": "low"}], "boss": {"id": "boss_warchief", "title": "Warchief Grukk", "type": "boss", "threat_level": "severe"}}'
```

### load_quest
Load a quest template and get a full DM briefing.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign load_quest '{"quest_id": "goblin_warrens"}'
```

### list_quests
List all quest templates for the active campaign.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign list_quests '{}'
```

### complete_encounter_in_quest
Mark an encounter as completed in a quest and track progress.

```bash
exec python3 /app/skills/run_skill.py rpg_campaign complete_encounter_in_quest '{"quest_id": "goblin_warrens", "encounter_id": "ambush_01", "xp_awarded": 60, "loot_found": ["short sword", "10 gp"], "notes": "Party used stealth to ambush the goblins"}'
```

## Campaign Data Format

Campaigns are stored as YAML in `aria_memories/rpg/campaigns/<campaign_id>.yaml`:

```yaml
campaign_id: crimson_throne
title: "Curse of the Crimson Throne"
setting: Golarion
party: [shiva_kael_stormwind, aria_seraphina_dawnblade]
session_count: 3
current_location: Sandpoint
calendar:
  year: 4724
  month: 1
  day: 15
npcs:
  - name: Ameiko Kaijitsu
    role: friendly
encounters:
  - encounter_id: goblin_ambush
    status: completed
quests:
  - quest_id: goblin_warrens
    status: active
```

## Python Module

Class: `RPGCampaignSkill`
Module: `aria_skills.rpg_campaign`
