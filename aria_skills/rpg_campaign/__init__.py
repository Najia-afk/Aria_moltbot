"""
RPG Campaign Manager — Campaign state, sessions, world, and encounter management.

Manages the persistent state of Pathfinder 2e campaigns for Aria's RPG system.
All data persisted to aria_memories/rpg/.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skill.rpg_campaign")

RPG_ROOT = Path("aria_memories/rpg")
CAMPAIGNS_DIR = RPG_ROOT / "campaigns"
SESSIONS_DIR = RPG_ROOT / "sessions"
WORLD_DIR = RPG_ROOT / "world"
ENCOUNTERS_DIR = RPG_ROOT / "encounters"
CHARACTERS_DIR = RPG_ROOT / "characters"


def _ensure_dirs():
    """Create all RPG directories if they don't exist."""
    for d in [CAMPAIGNS_DIR, SESSIONS_DIR, WORLD_DIR, ENCOUNTERS_DIR, CHARACTERS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file safely."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict[str, Any]):
    """Save data to a YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


@SkillRegistry.register
class RPGCampaignSkill(BaseSkill):
    """Campaign manager — sessions, world state, encounters, and party management."""

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._active_campaign: str | None = None

    @property
    def name(self) -> str:
        return "rpg_campaign"

    async def initialize(self) -> bool:
        _ensure_dirs()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("RPG Campaign skill initialized")
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    # ── Campaign CRUD ────────────────────────────────────────────────────

    @logged_method()
    async def create_campaign(
        self,
        campaign_id: str,
        title: str,
        setting: str = "Golarion",
        description: str = "",
        dm_notes: str = "",
        starting_level: int = 1,
    ) -> SkillResult:
        """
        Create a new campaign.

        Args:
            campaign_id: Unique slug (e.g., "rise_of_the_runelords").
            title: Display title.
            setting: Campaign world (default: Golarion).
            description: Campaign pitch/summary.
            dm_notes: Private DM-only notes.
            starting_level: Party starting level.
        """
        try:
            campaign_dir = CAMPAIGNS_DIR / campaign_id
            campaign_dir.mkdir(parents=True, exist_ok=True)
            (campaign_dir / "encounters").mkdir(exist_ok=True)
            (campaign_dir / "sessions").mkdir(exist_ok=True)

            campaign = {
                "id": campaign_id,
                "title": title,
                "setting": setting,
                "description": description,
                "dm_notes": dm_notes,
                "starting_level": starting_level,
                "current_session": 0,
                "party": [],
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _save_yaml(campaign_dir / "campaign.yaml", campaign)

            # Initialize world state
            world = {
                "setting": setting,
                "current_location": "Unknown",
                "known_locations": [],
                "factions": [],
                "calendar": {"day": 1, "month": "Abadius", "year": 4724, "season": "Winter"},
                "world_events": [],
                "notes": "",
            }
            _save_yaml(campaign_dir / "world.yaml", world)

            # Initialize NPC roster
            _save_yaml(campaign_dir / "npcs.yaml", {"npcs": []})

            self._active_campaign = campaign_id
            return SkillResult.ok({
                "campaign_id": campaign_id,
                "title": title,
                "summary": f"📜 Campaign **{title}** created! Setting: {setting}, Starting Level: {starting_level}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def load_campaign(self, campaign_id: str) -> SkillResult:
        """
        Load an existing campaign as the active campaign.

        Args:
            campaign_id: Campaign slug to load.
        """
        try:
            campaign_dir = CAMPAIGNS_DIR / campaign_id
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            if not campaign:
                return SkillResult.fail(f"Campaign not found: {campaign_id}")
            
            self._active_campaign = campaign_id
            world = _load_yaml(campaign_dir / "world.yaml")
            
            return SkillResult.ok({
                "campaign": campaign,
                "world": world,
                "summary": f"📜 Campaign **{campaign['title']}** loaded. Session #{campaign.get('current_session', 0)}. Location: {world.get('current_location', 'Unknown')}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def list_campaigns(self, status: str = "") -> SkillResult:
        """
        List all available campaigns, optionally filtered by status.

        Args:
            status: Filter by campaign status (active, completed, paused). Empty = all.
        """
        try:
            _ensure_dirs()
            campaigns = []
            for d in CAMPAIGNS_DIR.iterdir():
                if d.is_dir():
                    camp = _load_yaml(d / "campaign.yaml")
                    if camp:
                        camp_status = camp.get("status", "unknown")
                        if status and camp_status != status:
                            continue
                        campaigns.append({
                            "id": camp.get("id", d.name),
                            "title": camp.get("title", "Unknown"),
                            "status": camp_status,
                            "session": camp.get("current_session", 0),
                            "party_size": len(camp.get("party", [])),
                            "setting": camp.get("setting", "Unknown"),
                            "created_at": camp.get("created_at", ""),
                        })
            return SkillResult.ok({"campaigns": campaigns, "count": len(campaigns)})
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def get_campaign_detail(self, campaign_id: str) -> SkillResult:
        """
        Get full campaign detail for dashboard display — includes party roster,
        session list, world state, and encounter summary.

        Args:
            campaign_id: Campaign slug to retrieve.
        """
        try:
            campaign_dir = CAMPAIGNS_DIR / campaign_id
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            if not campaign:
                return SkillResult.fail(f"Campaign not found: {campaign_id}")

            world = _load_yaml(campaign_dir / "world.yaml")
            npcs = _load_yaml(campaign_dir / "npcs.yaml")

            # Resolve party character details
            party_details = []
            for ref in campaign.get("party", []):
                char_path = CHARACTERS_DIR / ref
                if not char_path.suffix:
                    char_path = CHARACTERS_DIR / f"{ref}.yaml"
                char_data = _load_yaml(char_path)
                ch = char_data.get("character", char_data)
                party_details.append({
                    "file": ref,
                    "name": ch.get("name", ref),
                    "class": ch.get("class", ""),
                    "ancestry": ch.get("ancestry", ""),
                    "level": ch.get("level", ""),
                })

            # List session YAML files
            sessions_dir = campaign_dir / "sessions"
            sessions = []
            if sessions_dir.exists():
                for sf in sorted(sessions_dir.glob("*.yaml")):
                    sd = _load_yaml(sf)
                    sessions.append({
                        "file": sf.name,
                        "number": sd.get("number", 0),
                        "title": sd.get("title", sf.stem),
                        "status": sd.get("status", ""),
                    })

            # Count encounters
            enc_dir = campaign_dir / "encounters"
            encounter_count = sum(1 for _ in enc_dir.glob("*.yaml")) if enc_dir.exists() else 0

            return SkillResult.ok({
                "campaign": campaign,
                "world": world,
                "party": party_details,
                "sessions": sessions,
                "npc_count": len(npcs.get("npcs", [])),
                "encounter_count": encounter_count,
                "summary": (
                    f"📜 **{campaign.get('title')}** — {campaign.get('status', 'unknown')} | "
                    f"Party: {len(party_details)} | Sessions: {len(sessions)} | "
                    f"NPCs: {len(npcs.get('npcs', []))} | Encounters: {encounter_count}"
                ),
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def get_session_transcript(self, session_id: str = "", campaign_id: str = "") -> SkillResult:
        """
        Retrieve a session transcript. Searches sessions directory by id or filename.

        Args:
            session_id: Session identifier or transcript filename.
            campaign_id: Optional campaign slug to scope the search.
        """
        try:
            # Search in campaign-specific sessions first
            search_dirs = []
            if campaign_id:
                search_dirs.append(CAMPAIGNS_DIR / campaign_id / "sessions")
            if self._active_campaign:
                search_dirs.append(CAMPAIGNS_DIR / self._active_campaign / "sessions")
            search_dirs.append(SESSIONS_DIR)

            for sdir in search_dirs:
                if not sdir.exists():
                    continue
                for f in sorted(sdir.glob("*")):
                    if session_id in f.stem or session_id in f.name:
                        content = f.read_text(encoding="utf-8")
                        return SkillResult.ok({
                            "file": str(f),
                            "filename": f.name,
                            "content": content,
                            "lines": len(content.splitlines()),
                        })

            return SkillResult.fail(f"Transcript not found for session: {session_id}")
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Party Management ────────────────────────────────────────────────

    @logged_method()
    async def add_to_party(self, character_file: str) -> SkillResult:
        """
        Add a character to the active campaign's party.

        Args:
            character_file: Character YAML filename from aria_memories/rpg/characters/.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign. Load one first.")
            
            # Verify character exists
            char_path = CHARACTERS_DIR / character_file
            if not char_path.exists():
                char_path = CHARACTERS_DIR / f"{character_file}.yaml"
            if not char_path.exists():
                return SkillResult.fail(f"Character not found: {character_file}")
            
            char_data = _load_yaml(char_path)
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            party = campaign.get("party", [])
            
            char_ref = char_path.name
            if char_ref not in party:
                party.append(char_ref)
                campaign["party"] = party
                campaign["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_yaml(campaign_dir / "campaign.yaml", campaign)
            
            char_name = char_data.get("character", {}).get("name", "Unknown")
            return SkillResult.ok({
                "character": char_name,
                "character_file": char_ref,
                "party": party,
                "summary": f"🛡️ **{char_name}** joined the party! Party size: {len(party)}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def get_party_status(self) -> SkillResult:
        """Get the full status of the current campaign's party."""
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            party_files = campaign.get("party", [])
            
            party = []
            for pf in party_files:
                try:
                    char = _load_yaml(CHARACTERS_DIR / pf)
                    c = char.get("character", {})
                    hp = char.get("hit_points", {})
                    party.append({
                        "file": pf,
                        "player": char.get("player", "Unknown"),
                        "name": c.get("name", "Unknown"),
                        "class": c.get("class", "?"),
                        "level": c.get("level", 0),
                        "hp": f"{hp.get('current', '?')}/{hp.get('max', '?')}",
                        "ac": char.get("armor_class", "?"),
                        "conditions": char.get("conditions", []),
                    })
                except Exception:
                    party.append({"file": pf, "error": "Could not load"})
            
            lines = ["🛡️ **Party Status:**"]
            for p in party:
                if "error" in p:
                    lines.append(f"  - ❌ {p['file']}: {p['error']}")
                else:
                    conds = ", ".join(str(c) for c in p["conditions"]) if p["conditions"] else "None"
                    lines.append(
                        f"  - **{p['name']}** ({p['player']}) — {p['class']} Lv{p['level']} | "
                        f"HP: {p['hp']} | AC: {p['ac']} | Conditions: {conds}"
                    )
            
            return SkillResult.ok({
                "party": party,
                "count": len(party),
                "summary": "\n".join(lines),
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Session Management ──────────────────────────────────────────────

    @logged_method()
    async def start_session(self, recap: str = "") -> SkillResult:
        """
        Start a new game session for the active campaign.

        Args:
            recap: Optional recap of previous session.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            session_num = campaign.get("current_session", 0) + 1
            campaign["current_session"] = session_num
            campaign["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_yaml(campaign_dir / "campaign.yaml", campaign)
            
            session = {
                "session": session_num,
                "campaign": self._active_campaign,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "ended_at": None,
                "recap": recap,
                "events": [],
                "combat_log": [],
                "xp_awarded": 0,
                "loot": [],
                "notes": "",
            }
            session_file = campaign_dir / "sessions" / f"session_{session_num:03d}.yaml"
            _save_yaml(session_file, session)
            
            return SkillResult.ok({
                "session": session_num,
                "campaign": campaign.get("title", self._active_campaign),
                "summary": f"🎲 **Session #{session_num}** started for {campaign.get('title', self._active_campaign)}!",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def log_event(self, event: str, event_type: str = "narrative") -> SkillResult:
        """
        Log an event to the current session.

        Args:
            event: Event description.
            event_type: "narrative", "combat", "social", "exploration", "loot", "milestone".
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            session_num = campaign.get("current_session", 0)
            
            session_file = campaign_dir / "sessions" / f"session_{session_num:03d}.yaml"
            session = _load_yaml(session_file)
            
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": event_type,
                "description": event,
            }
            session.setdefault("events", []).append(entry)
            _save_yaml(session_file, session)
            
            type_emoji = {
                "narrative": "📖", "combat": "⚔️", "social": "💬",
                "exploration": "🗺️", "loot": "💰", "milestone": "🏆",
            }
            emoji = type_emoji.get(event_type, "📝")
            
            return SkillResult.ok({
                "event": entry,
                "session": session_num,
                "summary": f"{emoji} [{event_type.upper()}] {event}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def end_session(self, notes: str = "") -> SkillResult:
        """
        End the current game session and generate a summary.

        Args:
            notes: DM closing notes.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            session_num = campaign.get("current_session", 0)
            
            session_file = campaign_dir / "sessions" / f"session_{session_num:03d}.yaml"
            session = _load_yaml(session_file)
            session["ended_at"] = datetime.now(timezone.utc).isoformat()
            session["notes"] = notes
            _save_yaml(session_file, session)

            events = session.get("events", [])
            return SkillResult.ok({
                "session": session_num,
                "events_count": len(events),
                "summary": f"🏁 Session #{session_num} ended. {len(events)} events logged.",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── World State ─────────────────────────────────────────────────────

    @logged_method()
    async def update_location(self, location: str, description: str = "") -> SkillResult:
        """
        Update the party's current location.

        Args:
            location: New location name.
            description: Location description.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            world = _load_yaml(campaign_dir / "world.yaml")
            
            old_location = world.get("current_location", "Unknown")
            world["current_location"] = location
            
            known = world.get("known_locations", [])
            if not any(loc.get("name") == location for loc in known):
                known.append({"name": location, "description": description, "discovered_at": datetime.now(timezone.utc).isoformat()})
                world["known_locations"] = known
            
            _save_yaml(campaign_dir / "world.yaml", world)
            
            return SkillResult.ok({
                "old_location": old_location,
                "new_location": location,
                "summary": f"🗺️ Party moved: {old_location} → **{location}**",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def add_npc(
        self,
        npc_name: str,
        role: str = "neutral",
        description: str = "",
        location: str = "",
        stats: dict[str, Any] | None = None,
    ) -> SkillResult:
        """
        Add an NPC to the campaign roster.

        Args:
            npc_name: NPC's name.
            role: "friendly", "neutral", "hostile", "boss".
            description: Physical/personality description.
            location: Where the NPC is found.
            stats: Optional combat stats (AC, HP, attacks, etc.).
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            npcs_data = _load_yaml(campaign_dir / "npcs.yaml")
            npc_list = npcs_data.get("npcs", [])
            
            npc = {
                "name": npc_name,
                "role": role,
                "description": description,
                "location": location,
                "alive": True,
                "met": False,
                "stats": stats or {},
                "notes": "",
            }
            npc_list.append(npc)
            npcs_data["npcs"] = npc_list
            _save_yaml(campaign_dir / "npcs.yaml", npcs_data)
            
            role_emoji = {"friendly": "💚", "neutral": "💛", "hostile": "🔴", "boss": "💀"}
            emoji = role_emoji.get(role, "👤")
            
            return SkillResult.ok({
                "npc": npc,
                "total_npcs": len(npc_list),
                "summary": f"{emoji} NPC **{npc_name}** added ({role}) at {location or 'unknown location'}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def list_npcs(self, role_filter: str = "") -> SkillResult:
        """
        List NPCs in the active campaign.

        Args:
            role_filter: Optional filter by role ("friendly", "hostile", "boss", etc.).
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            npcs_data = _load_yaml(campaign_dir / "npcs.yaml")
            npc_list = npcs_data.get("npcs", [])
            
            if role_filter:
                npc_list = [n for n in npc_list if n.get("role") == role_filter]
            
            return SkillResult.ok({"npcs": npc_list, "count": len(npc_list)})
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Encounter Management ────────────────────────────────────────────

    @logged_method()
    async def create_encounter(
        self,
        encounter_id: str,
        title: str,
        threat_level: str = "moderate",
        description: str = "",
        enemies: list[dict[str, Any]] | None = None,
        environment: str = "",
        loot: list[str] | None = None,
        xp_reward: int = 80,
    ) -> SkillResult:
        """
        Create a pre-built encounter.

        Args:
            encounter_id: Unique ID (e.g., "E001_goblin_ambush").
            title: Encounter title.
            threat_level: "trivial", "low", "moderate", "severe", "extreme".
            description: Scene description for DM.
            enemies: Enemy combatant list [{name, level, hp, ac, attacks, abilities}].
            environment: Terrain/environmental features.
            loot: Treasure to award on completion.
            xp_reward: Total XP for defeating encounter.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            encounter = {
                "id": encounter_id,
                "title": title,
                "threat_level": threat_level,
                "description": description,
                "enemies": enemies or [],
                "environment": environment,
                "loot": loot or [],
                "xp_reward": xp_reward,
                "status": "prepared",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            
            enc_file = campaign_dir / "encounters" / f"{encounter_id}.yaml"
            _save_yaml(enc_file, encounter)
            
            threat_emoji = {
                "trivial": "🟢", "low": "🟡", "moderate": "🟠", "severe": "🔴", "extreme": "💀"
            }
            emoji = threat_emoji.get(threat_level, "⚔️")
            
            return SkillResult.ok({
                "encounter": encounter,
                "summary": f"{emoji} Encounter **{title}** ({threat_level}) created with {len(enemies or [])} enemies. XP: {xp_reward}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def list_encounters(self, status_filter: str = "") -> SkillResult:
        """
        List encounters for the active campaign.

        Args:
            status_filter: Optional filter by status ("prepared", "active", "completed").
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            enc_dir = campaign_dir / "encounters"
            enc_dir.mkdir(parents=True, exist_ok=True)
            
            encounters = []
            for f in enc_dir.glob("*.yaml"):
                enc = _load_yaml(f)
                if enc:
                    if status_filter and enc.get("status") != status_filter:
                        continue
                    encounters.append({
                        "id": enc.get("id", f.stem),
                        "title": enc.get("title", "Unknown"),
                        "threat_level": enc.get("threat_level", "?"),
                        "status": enc.get("status", "unknown"),
                        "enemies": len(enc.get("enemies", [])),
                        "xp": enc.get("xp_reward", 0),
                    })
            
            return SkillResult.ok({"encounters": encounters, "count": len(encounters)})
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Calendar ────────────────────────────────────────────────────────

    @logged_method()
    async def advance_time(self, days: int = 1, event: str = "") -> SkillResult:
        """
        Advance the in-game calendar.

        Args:
            days: Number of days to advance.
            event: Optional event that occurred during this time.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            world = _load_yaml(campaign_dir / "world.yaml")
            calendar = world.get("calendar", {"day": 1, "month": "Abadius", "year": 4724})
            
            MONTHS = [
                "Abadius", "Calistril", "Pharast", "Gozran", "Desnus", "Sarenith",
                "Erastus", "Arodus", "Rova", "Lamashan", "Neth", "Kuthona",
            ]
            DAYS_PER_MONTH = 28  # Golarion months ~28 days
            
            day = calendar.get("day", 1) + days
            month_idx = MONTHS.index(calendar.get("month", "Abadius")) if calendar.get("month") in MONTHS else 0
            year = calendar.get("year", 4724)
            
            while day > DAYS_PER_MONTH:
                day -= DAYS_PER_MONTH
                month_idx += 1
                if month_idx >= 12:
                    month_idx = 0
                    year += 1
            
            season_map = {0: "Winter", 1: "Winter", 2: "Spring", 3: "Spring", 4: "Spring",
                          5: "Summer", 6: "Summer", 7: "Summer", 8: "Autumn", 9: "Autumn",
                          10: "Autumn", 11: "Winter"}
            
            calendar = {
                "day": day,
                "month": MONTHS[month_idx],
                "year": year,
                "season": season_map[month_idx],
            }
            world["calendar"] = calendar
            
            if event:
                world.setdefault("world_events", []).append({
                    "date": f"{day} {MONTHS[month_idx]}, {year}",
                    "event": event,
                })
            
            _save_yaml(campaign_dir / "world.yaml", world)
            
            date_str = f"{day} {MONTHS[month_idx]}, {year} AR ({calendar['season']})"
            summary = f"📅 {days} day(s) pass. Date: **{date_str}**"
            if event:
                summary += f"\n  Event: {event}"
            
            return SkillResult.ok({
                "calendar": calendar,
                "date_string": date_str,
                "summary": summary,
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def get_world_state(self) -> SkillResult:
        """Get the full world state for the active campaign."""
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")
            
            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            world = _load_yaml(campaign_dir / "world.yaml")
            campaign = _load_yaml(campaign_dir / "campaign.yaml")
            
            return SkillResult.ok({
                "campaign": campaign.get("title", self._active_campaign),
                "world": world,
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    # ── Quest Templates ─────────────────────────────────────────────────

    @logged_method()
    async def generate_quest(
        self,
        quest_id: str,
        title: str,
        hook: str,
        setting_location: str,
        target_level_start: int = 1,
        target_level_end: int = 2,
        tone: str = "dark fantasy",
        party_characters: list[str] | None = None,
        companion_characters: list[str] | None = None,
        encounter_sequence: list[dict[str, Any]] | None = None,
        npcs: list[dict[str, Any]] | None = None,
        boss: dict[str, Any] | None = None,
        loot_table: list[dict[str, Any]] | None = None,
        dm_instructions: str = "",
    ) -> SkillResult:
        """
        Generate a reusable quest template YAML that Aria can run as DM.

        This creates a complete quest definition file at
        aria_memories/rpg/campaigns/{active_campaign}/quests/{quest_id}.yaml

        Args:
            quest_id: Unique quest slug (e.g., "goblin_warrens").
            title: Quest display title.
            hook: The story hook — why the party is here.
            setting_location: Starting location for the quest.
            target_level_start: Party expected level at start.
            target_level_end: Party expected level at end.
            tone: Narrative tone (e.g., "dark fantasy", "heroic", "horror").
            party_characters: List of character YAML filenames for player characters.
            companion_characters: List of character YAML filenames for NPC companions (Aria-controlled).
            encounter_sequence: Ordered list of encounters. Each dict:
                {
                    "id": "E001_...",
                    "title": "Goblin Sentries",
                    "type": "combat" | "social" | "exploration" | "puzzle" | "boss",
                    "threat_level": "trivial" | "low" | "moderate" | "severe" | "extreme",
                    "description": "Scene description for DM narration",
                    "enemies": [{"name": "Goblin Warrior", "level": -1, "hp": 6, "ac": 16, "attack_bonus": 7, "damage": "1d6+2", "perception": 2}],
                    "environment": "Narrow mine tunnel with low ceiling, rubble, and dim torchlight",
                    "xp_reward": 60,
                    "loot": ["Shortsword", "3 sp"],
                    "special_rules": "Low ceiling: Medium creatures are flat-footed"
                }
            npcs: Named NPCs for the quest. Each dict:
                {"name": "...", "role": "friendly|neutral|hostile|boss", "description": "...", "location": "...", "stats": {...}}
            boss: Boss encounter definition (same format as encounter_sequence entry).
            loot_table: Loot rewards. Each: {"item": "...", "value_gp": 0, "source": "encounter_id or milestone"}.
            dm_instructions: Free-form DM guidance for running this quest.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign. Create or load one first.")

            campaign_dir = CAMPAIGNS_DIR / self._active_campaign
            quest_dir = campaign_dir / "quests"
            quest_dir.mkdir(parents=True, exist_ok=True)

            # Calculate total XP from encounters
            total_xp = 0
            if encounter_sequence:
                total_xp += sum(e.get("xp_reward", 0) for e in encounter_sequence)
            if boss:
                total_xp += boss.get("xp_reward", 0)

            xp_needed = (target_level_end - target_level_start) * 1000

            quest = {
                "quest_id": quest_id,
                "title": title,
                "campaign": self._active_campaign,
                "hook": hook,
                "setting_location": setting_location,
                "target_level_start": target_level_start,
                "target_level_end": target_level_end,
                "tone": tone,
                "party_characters": party_characters or [],
                "companion_characters": companion_characters or [],
                "encounter_sequence": encounter_sequence or [],
                "npcs": npcs or [],
                "boss": boss or {},
                "loot_table": loot_table or [],
                "dm_instructions": dm_instructions,
                "metadata": {
                    "total_xp_available": total_xp,
                    "xp_needed_for_target": xp_needed,
                    "encounter_count": len(encounter_sequence or []) + (1 if boss else 0),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "ready",
                },
            }

            _save_yaml(quest_dir / f"{quest_id}.yaml", quest)

            summary_lines = [
                f"Quest **{title}** generated!",
                f"  Hook: {hook[:100]}{'...' if len(hook) > 100 else ''}",
                f"  Location: {setting_location}",
                f"  Level range: {target_level_start} -> {target_level_end}",
                f"  Encounters: {len(encounter_sequence or [])} + {'1 boss' if boss else 'no boss'}",
                f"  Total XP available: {total_xp} (need {xp_needed} for target)",
                f"  Party: {', '.join(party_characters or ['none set'])}",
                f"  Companions: {', '.join(companion_characters or ['none set'])}",
                f"  Saved to: quests/{quest_id}.yaml",
            ]

            return SkillResult.ok({
                "quest_id": quest_id,
                "quest_file": str(quest_dir / f"{quest_id}.yaml"),
                "total_xp": total_xp,
                "xp_needed": xp_needed,
                "encounter_count": quest["metadata"]["encounter_count"],
                "summary": "\n".join(summary_lines),
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def load_quest(self, quest_id: str) -> SkillResult:
        """
        Load a quest template and return the full quest definition.

        Aria uses this to read the quest data and know what encounters to run,
        what NPCs to voice, what loot to drop, etc.

        Args:
            quest_id: Quest slug to load.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")

            quest_dir = CAMPAIGNS_DIR / self._active_campaign / "quests"
            quest_file = quest_dir / f"{quest_id}.yaml"
            if not quest_file.exists():
                return SkillResult.fail(f"Quest not found: {quest_id}")

            quest = _load_yaml(quest_file)

            # Build a DM briefing from the quest data
            briefing_lines = [
                f"# Quest Briefing: {quest.get('title', quest_id)}",
                f"",
                f"**Hook**: {quest.get('hook', 'N/A')}",
                f"**Location**: {quest.get('setting_location', 'Unknown')}",
                f"**Tone**: {quest.get('tone', 'standard')}",
                f"**Level**: {quest.get('target_level_start', '?')} -> {quest.get('target_level_end', '?')}",
                f"",
                f"## Party",
            ]
            for pc in quest.get("party_characters", []):
                briefing_lines.append(f"  - {pc}")
            briefing_lines.append(f"## Companions (you control)")
            for cc in quest.get("companion_characters", []):
                briefing_lines.append(f"  - {cc}")
            briefing_lines.append(f"")
            briefing_lines.append(f"## Encounter Sequence")
            for i, enc in enumerate(quest.get("encounter_sequence", []), 1):
                briefing_lines.append(
                    f"  {i}. [{enc.get('type', '?').upper()}] **{enc.get('title', '?')}** "
                    f"({enc.get('threat_level', '?')}, {enc.get('xp_reward', 0)} XP)"
                )
                if enc.get("description"):
                    briefing_lines.append(f"     {enc['description'][:120]}")
            boss_data = quest.get("boss", {})
            if boss_data:
                briefing_lines.append(
                    f"  BOSS: **{boss_data.get('title', '?')}** "
                    f"({boss_data.get('threat_level', '?')}, {boss_data.get('xp_reward', 0)} XP)"
                )
            briefing_lines.append(f"")
            briefing_lines.append(f"## NPCs")
            for npc in quest.get("npcs", []):
                briefing_lines.append(f"  - **{npc.get('name', '?')}** ({npc.get('role', '?')}): {npc.get('description', '')[:80]}")
            if quest.get("dm_instructions"):
                briefing_lines.append(f"")
                briefing_lines.append(f"## DM Instructions")
                briefing_lines.append(quest["dm_instructions"])

            return SkillResult.ok({
                "quest": quest,
                "briefing": "\n".join(briefing_lines),
                "summary": f"Quest **{quest.get('title', quest_id)}** loaded. {len(quest.get('encounter_sequence', []))} encounters + boss.",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def list_quests(self) -> SkillResult:
        """List all quest templates for the active campaign."""
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")

            quest_dir = CAMPAIGNS_DIR / self._active_campaign / "quests"
            quest_dir.mkdir(parents=True, exist_ok=True)
            quests = []
            for f in quest_dir.glob("*.yaml"):
                q = _load_yaml(f)
                meta = q.get("metadata", {})
                quests.append({
                    "quest_id": q.get("quest_id", f.stem),
                    "title": q.get("title", "Unknown"),
                    "level_range": f"{q.get('target_level_start', '?')}-{q.get('target_level_end', '?')}",
                    "encounters": meta.get("encounter_count", 0),
                    "total_xp": meta.get("total_xp_available", 0),
                    "status": meta.get("status", "unknown"),
                })
            return SkillResult.ok({"quests": quests, "count": len(quests)})
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def complete_encounter_in_quest(
        self,
        quest_id: str,
        encounter_id: str,
        xp_awarded: int = 0,
        loot_found: list[str] | None = None,
        notes: str = "",
    ) -> SkillResult:
        """
        Mark an encounter as completed in a quest and track progress.

        Args:
            quest_id: Quest slug.
            encounter_id: Encounter ID within the quest.
            xp_awarded: XP actually awarded (may differ from template due to RP bonuses).
            loot_found: Items actually found.
            notes: DM notes about how it went.
        """
        try:
            if not self._active_campaign:
                return SkillResult.fail("No active campaign.")

            quest_dir = CAMPAIGNS_DIR / self._active_campaign / "quests"
            quest_file = quest_dir / f"{quest_id}.yaml"
            if not quest_file.exists():
                return SkillResult.fail(f"Quest not found: {quest_id}")

            quest = _load_yaml(quest_file)

            # Find and update the encounter
            found = False
            for enc in quest.get("encounter_sequence", []):
                if enc.get("id") == encounter_id:
                    enc["completed"] = True
                    enc["actual_xp"] = xp_awarded
                    enc["actual_loot"] = loot_found or []
                    enc["completion_notes"] = notes
                    enc["completed_at"] = datetime.now(timezone.utc).isoformat()
                    found = True
                    break

            # Check boss
            boss = quest.get("boss", {})
            if not found and boss.get("id") == encounter_id:
                boss["completed"] = True
                boss["actual_xp"] = xp_awarded
                boss["actual_loot"] = loot_found or []
                boss["completion_notes"] = notes
                boss["completed_at"] = datetime.now(timezone.utc).isoformat()
                quest["boss"] = boss
                found = True

            if not found:
                return SkillResult.fail(f"Encounter {encounter_id} not found in quest {quest_id}")

            # Update progress
            encounters = quest.get("encounter_sequence", [])
            completed = sum(1 for e in encounters if e.get("completed"))
            total = len(encounters) + (1 if quest.get("boss") else 0)
            boss_done = quest.get("boss", {}).get("completed", False)
            if boss_done:
                completed += 1
            quest["metadata"]["progress"] = f"{completed}/{total}"
            if completed >= total:
                quest["metadata"]["status"] = "completed"

            _save_yaml(quest_file, quest)

            return SkillResult.ok({
                "encounter_id": encounter_id,
                "xp_awarded": xp_awarded,
                "progress": f"{completed}/{total}",
                "quest_completed": completed >= total,
                "summary": f"Encounter **{encounter_id}** completed! Progress: {completed}/{total}. +{xp_awarded} XP.",
            })
        except Exception as e:
            return SkillResult.fail(str(e))

    @logged_method()
    async def save_session_transcript(
        self,
        title: str = "session",
        content: str = "",
        player_name: str = "",
        companion_name: str = "",
        dm_name: str = "Aria",
    ) -> SkillResult:
        """
        Save a formatted session transcript to aria_memories/rpg/sessions/.

        Args:
            title: Transcript title / campaign name slug.
            content: Full markdown transcript content to save.
            player_name: Player character name for the header.
            companion_name: Companion NPC name for the header.
            dm_name: DM name for the header.
        """
        try:
            SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"transcript_{title}_{ts}.md"
            path = SESSIONS_DIR / filename

            header = [
                f"# RPG Session Transcript",
                f"**Title**: {title}",
                f"**Date**: {datetime.now(timezone.utc).isoformat()}",
                f"**System**: Pathfinder 2e",
                f"**DM**: {dm_name}",
            ]
            if player_name:
                header.append(f"**Player**: {player_name}")
            if companion_name:
                header.append(f"**Companion**: {companion_name}")
            header.extend(["", "---", ""])

            full_content = "\n".join(header) + "\n" + content
            path.write_text(full_content, encoding="utf-8")

            return SkillResult.ok({
                "file": str(path),
                "filename": filename,
                "summary": f"Transcript saved: {filename}",
            })
        except Exception as e:
            return SkillResult.fail(str(e))
