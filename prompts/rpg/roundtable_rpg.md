# RPG Roundtable Protocol — Pathfinder 2e Campaign Play

> Defines how Aria's multi-agent roundtable system adapts for tabletop RPG sessions.
> This protocol replaces the standard EXPLORE → WORK → VALIDATE phases with RPG-specific flow.

---

## Overview

The RPG Roundtable is a specialized mode of Aria's multi-agent discussion system
designed for Pathfinder 2e campaign play. Instead of analyzing a topic from multiple
perspectives, agents play distinct RPG roles in a collaborative storytelling experience.

### Participants

| Agent ID | Role | When Active |
|----------|------|-------------|
| `rpg_master` | Dungeon Master | Always — orchestrates everything |
| `rpg_npc` | NPC Controller | Social scenes, town interactions |
| `rpg_boss` | Boss Controller | Boss encounters, villain scenes |
| `rpg_paladin` | AI Companion | Always (if party has Sera) |
| **Human Players** | Player Characters | Always — via chat interface |

---

## Game Modes

### 1. Exploration Mode 🗺️

**Active agents**: `rpg_master`, `rpg_npc` (if NPCs present), `rpg_paladin`

**Flow:**
```
1. rpg_master: Describes the scene, environment, notable features
2. [Players declare actions: "I search the room", "I check for traps"]
3. rpg_master: Resolves actions (rpg_pathfinder.check() for skill checks)
4. rpg_npc: Reacts if NPCs are present
5. rpg_paladin: Offers observations or assists
6. Repeat until scene changes or encounter triggers
```

**Round protocol:**
```
Phase: EXPLORE
Round prompt: "Describe what the party finds. Players can declare movement,
               searches, skill checks, or interactions."
```

### 2. Social Mode 💬

**Active agents**: `rpg_master`, `rpg_npc`, `rpg_paladin`

**Flow:**
```
1. rpg_master: Sets the social scene (who's here, mood, stakes)
2. rpg_npc: Plays the NPCs, responds to player dialogue
3. [Players roleplay: dialogue, Diplomacy, Intimidation, Deception checks]
4. rpg_master: Resolves checks (rpg_pathfinder.check())
5. rpg_npc: Reacts to check results in character
6. rpg_paladin: May interject diplomatically
7. rpg_master: Resolves the social outcome
```

**Round protocol:**
```
Phase: SOCIAL
Round prompt: "NPCs respond to the party. Players can speak, persuade,
               intimidate, or learn information through roleplay."
```

### 3. Combat Mode ⚔️

**Active agents**: `rpg_master`, `rpg_boss` (if boss present), `rpg_paladin`

**Flow:**
```
1. rpg_master: "ROLL INITIATIVE!" → rpg_pathfinder.roll_initiative()
2. rpg_master: Announces initiative order and round 1

FOR EACH ROUND:
  FOR EACH COMBATANT (in initiative order):
    IF player_character:
      rpg_master: "It's [Player]'s turn. 3 actions. What do you do?"
      [Player declares actions]
      rpg_master: Resolves via rpg_pathfinder (attack, check, cast_spell)
    
    IF rpg_paladin (Sera):
      rpg_paladin: Declares and resolves 3 actions (via rpg_pathfinder)
    
    IF enemy (non-boss):
      rpg_master: Plays enemy turn, resolves attacks
    
    IF boss:
      rpg_boss: Plays boss turn with full tactical AI (via rpg_pathfinder)
    
    rpg_master: Narrates the action cinematically
  
  END OF ROUND:
    rpg_master: Updates conditions (frightened decreases, persistent damage, etc.)
    rpg_master: Announces next round

ENCOUNTER END:
  rpg_master: Narrates victory/defeat
  rpg_master: Awards XP (rpg_pathfinder.award_xp())
  rpg_campaign.log_event(type="combat")
```

**Round protocol:**
```
Phase: COMBAT
Round prompt: "Combat round [N]. Current turn: [combatant].
               Declare your 3 actions. The DM will resolve each."
```

### 4. Rest Mode 🏕️

**Active agents**: `rpg_master`, `rpg_paladin`

**Flow:**
```
Short Rest (10 min):
  - Treat Wounds checks (Medicine DC based on proficiency)
  - Refocus (1 focus point recovered)
  - No random encounters

Long Rest (8 hours):
  1. rpg_master: Roll for random encounter (DC 15 flat check)
  2. If no encounter: Full HP recovery, conditions reduced
  3. rpg_master: Describes the rest scene (campfire RP opportunity)
  4. rpg_paladin: Sera may pray, share stories, keep watch
  5. rpg_campaign.advance_time(days=0)  # Advances ~8 hours
  6. Next morning description
```

---

## Roundtable Configuration

### RPG Roundtable Parameters

```python
# Override defaults for RPG mode
RPG_ROUNDTABLE_CONFIG = {
    "mode": "rpg",
    "rounds": -1,             # Unlimited — runs until scene changes
    "agent_timeout": 120,     # 2 min per agent response (more creative time)
    "total_timeout": 7200,    # 2 hour session max
    "synthesis_mode": "narrative",  # DM synthesizes as narration, not analysis
    "turn_order": "initiative",     # In combat, follow initiative order
}
```

### Phase Overrides

| Standard Phase | RPG Phase | Behavior |
|---------------|-----------|----------|
| EXPLORE | **Scene Setting** | DM describes. Players and NPCs react. |
| WORK | **Actions** | Players act. DM resolves. Enemies respond. |
| VALIDATE | **Resolution** | DM narrates outcomes. State updates. |

---

## Message Format

### DM Messages
```json
{
  "agent_id": "rpg_master",
  "role": "dungeon_master",
  "content": "...",
  "metadata": {
    "game_mode": "combat|exploration|social|rest",
    "round": 3,
    "initiative_position": 2,
    "dice_results": [{"expression": "1d20+12", "total": 24}]
  }
}
```

### Player Messages
```json
{
  "agent_id": null,
  "role": "player",
  "content": "I attack the goblin with my longsword!",
  "metadata": {
    "player": "Shiva",
    "character": "Kael Stormwind",
    "character_file": "shiva_kael_stormwind.yaml"
  }
}
```

### NPC Messages
```json
{
  "agent_id": "rpg_npc",
  "role": "npc",
  "content": "...",
  "metadata": {
    "npc_name": "Bartender Grok",
    "npc_role": "friendly",
    "location": "The Rusty Tankard"
  }
}
```

### Boss Messages
```json
{
  "agent_id": "rpg_boss",
  "role": "boss",
  "content": "...",
  "metadata": {
    "boss_name": "Warchief Gnarlak",
    "boss_hp": "45/120",
    "boss_conditions": ["frightened 1"]
  }
}
```

---

## Session Lifecycle

```
┌─────────────────────────────────────────────────┐
│ SESSION START                                    │
│  1. rpg_campaign.load_campaign()                │
│  2. rpg_campaign.start_session()                │
│  3. rpg_campaign.get_party_status()             │
│  4. rpg_master: Recap + Opening Scene           │
├─────────────────────────────────────────────────┤
│ PLAY LOOP                                        │
│  ┌───────────────────┐                          │
│  │ Exploration Mode   │ ←──────────┐            │
│  │  ├→ Social Mode    │            │            │
│  │  ├→ Combat Mode    │            │            │
│  │  └→ Rest Mode      │ ───────────┘            │
│  └───────────────────┘                          │
├─────────────────────────────────────────────────┤
│ SESSION END                                      │
│  1. rpg_pathfinder.award_xp() (each player)    │
│  2. rpg_campaign.end_session()                  │
│  3. rpg_master: Cliffhanger / Next time on...   │
└─────────────────────────────────────────────────┘
```

---

## Quick Commands for Players

| Command | Action |
|---------|--------|
| `I attack [target] with [weapon]` | DM resolves attack via rpg_pathfinder |
| `I cast [spell] on [target]` | DM resolves spell |
| `I check [skill] on [thing]` | DM rolls skill check |
| `I talk to [NPC]` | NPC controller responds |
| `I move to [location]` | DM describes new position |
| `I search [area]` | DM rolls Perception/Investigation |
| `I use [item]` | DM resolves item use |
| `rest` | Triggers rest mode |
| `party status` | Show all party HP/conditions |
| `map` | DM describes current environment |
| `what do I know about [topic]` | DM calls for Recall Knowledge |

---

## Integration Notes

- The RPG roundtable uses the same `Roundtable` class from `aria_engine/roundtable.py`
- Custom `on_turn` callback can stream RPG turns via WebSocket
- Session state persisted to `aria_memories/rpg/` after each turn
- Character sheets updated in real-time during combat
- All dice rolls logged for auditability
