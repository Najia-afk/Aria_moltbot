#!/usr/bin/env python3
"""
ARIA RPG Structured Test — P0
=============================
Multi-session, multi-agent RPG test with:
- Campaign creation via rpg_master (tool execution)
- Story continuation from existing combat (Round 4)
- /roundtable slash command for multi-agent consensus
- Session end/start for memory continuity testing
- Knowledge graph integration verification

Usage: python3 scripts/rpg_structured_test.py [phase]
  phase 1 = Campaign setup + quest generation
  phase 2 = Resume combat + advance story
  phase 3 = Roundtable NPC consensus
  phase 4 = End session + memory check
  phase 5 = New session + verify continuity
  all     = Run all phases sequentially
"""

import httpx
import json
import sys
import time
import uuid
from datetime import datetime

BASE = "http://localhost:8000"
TIMEOUT = 300  # seconds per request — LLM can be very slow with big context
TIMEOUT_ROUNDTABLE = 600  # roundtable runs multiple agents in parallel

# RPG Master session — use existing empty one or create new
RPG_MASTER_SESSION = "6eb2b6b2-756b-4446-a97e-2f49d8597ff0"


def send_message(session_id: str, content: str, enable_tools: bool = True, timeout: int = None) -> dict:
    """Send a message to a chat session and return the full response."""
    url = f"{BASE}/engine/chat/sessions/{session_id}/messages"
    payload = {
        "content": content,
        "enable_tools": enable_tools,
    }
    print(f"\n{'='*80}")
    print(f">>> SENDING TO {session_id[:8]}...")
    print(f">>> {content[:200]}{'...' if len(content) > 200 else ''}")
    print(f"{'='*80}")

    req_timeout = timeout or TIMEOUT
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=req_timeout) as client:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    print(f"ERROR {resp.status_code}: {resp.text[:500]}")
                    return {"error": resp.status_code, "detail": resp.text[:500]}

                data = resp.json()
                print(f"\n<<< RESPONSE (model={data.get('model','?')}, "
                      f"latency={data.get('latency_ms',0)}ms, "
                      f"finish={data.get('finish_reason','?')})")

                # Show tool calls if any
                tool_calls = data.get("tool_calls", [])
                if tool_calls:
                    print(f"\n🔧 TOOL CALLS ({len(tool_calls)}):")
                    for tc in tool_calls:
                        name = tc.get("function", {}).get("name", tc.get("name", "?"))
                        args = tc.get("function", {}).get("arguments", tc.get("arguments", "{}"))
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                pass
                        print(f"   → {name}({json.dumps(args, indent=2)[:200]})")

                # Show content
                content_out = data.get("content", "")
                if content_out:
                    if len(content_out) > 2000:
                        print(f"\n{content_out[:2000]}\n... [truncated, {len(content_out)} chars total]")
                    else:
                        print(f"\n{content_out}")

                return data

        except (httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError) as e:
            print(f"   ⚠️  Connection error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait = 15 * (attempt + 1)
                print(f"   Waiting {wait}s for server to recover...")
                time.sleep(wait)
            else:
                print(f"   FAILED after {max_retries} attempts")
                return {"error": "connection_failed", "detail": str(e)}


def create_session(agent_id: str, model: str = "kimi") -> str:
    """Create a new chat session and return its ID."""
    url = f"{BASE}/engine/chat/sessions"
    payload = {
        "agent_id": agent_id,
        "model": model,
        "session_type": "interactive",
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        if resp.status_code not in (200, 201):
            print(f"ERROR creating session: {resp.status_code} {resp.text[:300]}")
            return ""
        data = resp.json()
        sid = data.get("id", data.get("session_id", ""))
        print(f"✅ Created session {sid} (agent={agent_id}, model={model})")
        return sid


def check_session(session_id: str) -> dict:
    """Get session info."""
    url = f"{BASE}/engine/chat/sessions/{session_id}"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url)
        return resp.json() if resp.status_code == 200 else {}


def get_messages(session_id: str, limit: int = 5) -> list:
    """Get recent messages from a session."""
    url = f"{BASE}/engine/chat/sessions/{session_id}/messages"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            msgs = resp.json()
            if isinstance(msgs, list):
                return msgs[-limit:]
        return []


# ============================================================================
# PHASE 1: Campaign Setup
# ============================================================================
def phase_1_campaign_setup():
    """
    ARIA rpg_master creates the campaign, adds characters, starts session.
    Should trigger create_campaign, add_to_party, start_session tools.
    """
    print("\n" + "="*80)
    print("PHASE 1: CAMPAIGN SETUP — rpg_master creates campaign via tools")
    print("="*80)

    sid = RPG_MASTER_SESSION

    # First check if session exists and is usable
    info = check_session(sid)
    if not info or info.get("message_count", 0) > 0:
        print("Creating fresh rpg_master session...")
        sid = create_session("rpg_master", "kimi")
        if not sid:
            print("FAILED to create session")
            return None

    # Message 1: Instruct rpg_master to create the campaign
    msg1 = """You are the Dungeon Master for a Pathfinder 2e campaign called "Shadows of Absalom".

USE YOUR TOOLS to set up the campaign. Execute these steps:

1. Call create_campaign with:
   - campaign_id: "shadows_of_absalom"
   - title: "Shadows of Absalom"
   - setting: "Golarion — City of Absalom, Puddles district"
   - description: "A dark conspiracy lurks beneath the flooded streets of the Puddles district. Missing dockworkers, strange rituals at the Drowning Stone warehouse, and a tentacled horror pushing through from the Darklands."
   - starting_level: 1

2. Call add_to_party with: character_file: "claude_thorin_ashveil.yaml"
3. Call add_to_party with: character_file: "aria_seraphina_lv1.yaml"

4. Call add_npc with:
   - npc_name: "Caelus"
   - role: "friendly"
   - description: "Young dockworker held captive by the cult, chained with a copper collar"
   - location: "Drowning Stone warehouse"

5. Call add_npc with:
   - npc_name: "The Ritual Master"
   - role: "hostile"
   - description: "Cultist leader performing a summoning ritual at the Drowning Stone. Currently prone and injured from Thorin's attack."
   - location: "Drowning Stone warehouse"

6. Call start_session with:
   - recap: "Session 1 — The party investigated missing dockworkers in the Puddles district. Following clues to the Drowning Stone warehouse, they found a cult ritual in progress. Thorin Ashveil (Dwarf Fighter) and Seraphina (Half-Elf Champion) engaged in combat. Round 4: Thorin on the platform, Sera channeling a binding seal at 60%, Caelus chained, Ritual Master prone, water rising with a tentacled horror pushing through cracks in the floor."

Execute ALL tools now. Do not narrate — use the actual tool calls."""

    resp1 = send_message(sid, msg1)

    # Check for tool execution
    tool_calls = resp1.get("tool_calls", [])
    print(f"\n📊 Phase 1 Results:")
    print(f"   Tool calls executed: {len(tool_calls)}")
    print(f"   Tools used: {[tc.get('function',{}).get('name', tc.get('name','?')) for tc in tool_calls]}")

    return sid


# ============================================================================
# PHASE 2: Resume Combat (Story Continuation)
# ============================================================================
def phase_2_resume_combat(sid: str):
    """
    Continue the story from Round 4 combat.
    ARIA should use rpg_pathfinder tools for dice rolls and combat.
    """
    print("\n" + "="*80)
    print("PHASE 2: RESUME COMBAT — Round 4 at the Drowning Stone")
    print("="*80)

    # Set the scene and let Thorin act
    msg2 = """The campaign is set up. Now continue the COMBAT from Round 4.

Current situation:
- Thorin Ashveil (Dwarf Fighter, HP 23, AC 18) is on the stone platform next to the prone Ritual Master
- Seraphina (Half-Elf Champion, HP 20, AC 18) is channeling a binding seal (60% complete, needs 2 more rounds)
- Caelus (friendly NPC) is chained nearby with a copper collar
- Water at 5 feet, rising. Tentacled horror pushing through cracks below.
- The Ritual Master is PRONE from Thorin's previous attack.

Thorin's Round 4 actions (3 actions):
◆ Action 1: Strike the prone Ritual Master with battleaxe (he's flat-footed from prone, -2 AC)
◆ Action 2: If Ritual Master is still up, Strike again (MAP -5). If down, move toward Caelus to break his chains.
◆ Action 3: Raise Shield (free defense while others act)

USE your rpg_pathfinder tools:
- Call attack() for each Strike with proper bonuses
- Call check() for any skill checks needed
- Roll actual dice — do NOT make up results

Then narrate what happens based on the ACTUAL dice results."""

    resp2 = send_message(sid, msg2)
    tool_calls = resp2.get("tool_calls", [])
    print(f"\n📊 Phase 2 Results:")
    print(f"   Tool calls: {len(tool_calls)}")
    print(f"   Tools: {[tc.get('function',{}).get('name', tc.get('name','?')) for tc in tool_calls]}")

    # Now the tentacled horror acts
    msg3 = """Good. Now resolve the REST of Round 4:

1. The Ritual Master tries to stand up (1 action) and cast a spell if possible. 
   Use attack() or check() for their actions.

2. The tentacled horror pushes further — it gets a free Strike against anyone within 10 feet of the cracks.
   Use attack() with: attacker "Tentacled Horror", target "Thorin Ashveil", attack_bonus +12, damage "2d6+4 bludgeoning"

3. Seraphina continues channeling (her seal reaches 80% — one more round needed).

4. Then start Round 5. Roll initiative if needed with roll_initiative().

USE TOOLS for all rolls. Narrate based on actual results."""

    resp3 = send_message(sid, msg3)
    tool_calls = resp3.get("tool_calls", [])
    print(f"\n   Round 4 resolution tools: {len(tool_calls)}")
    print(f"   Tools: {[tc.get('function',{}).get('name', tc.get('name','?')) for tc in tool_calls]}")

    return sid


# ============================================================================
# PHASE 3: Roundtable for NPC Consensus
# ============================================================================
def phase_3_roundtable(sid: str):
    """
    Use the async roundtable API for multi-agent narrative consensus.
    The /roundtable slash command crashes uvicorn workers (timeout),
    so we use /engine/roundtable/async + polling instead.
    """
    print("\n" + "="*80)
    print("PHASE 3: ROUNDTABLE — Multi-agent NPC consensus (async)")
    print("="*80)

    topic = (
        "The combat at the Drowning Stone warehouse is reaching its climax. "
        "The binding seal is almost complete but the tentacled horror is breaking through. "
        "Thorin Ashveil just killed the Ritual Master with a critical hit and freed Caelus. "
        "Seraphina needs one more round to complete the binding seal. "
        "Should the party focus on protecting Sera while she completes the seal, "
        "or should Thorin try to fight the horror directly while it is partially trapped? "
        "Consider the tactical situation and how each NPC should react."
    )

    # Launch async roundtable with RPG agents
    payload = {
        "topic": topic,
        "agent_ids": ["rpg_master", "rpg_npc", "rpg_paladin", "rpg_boss"],
        "rounds": 2,
        "synthesizer_id": "rpg_master",
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/engine/roundtable/async", json=payload)
        if resp.status_code not in (200, 202):
            print(f"ERROR launching roundtable: {resp.status_code} {resp.text[:300]}")
            return sid
        data = resp.json()
        key = data.get("key", data.get("session_id", ""))
        print(f"🔄 Roundtable launched: key={key}, status={data.get('status','?')}")

    # Poll for completion
    max_polls = 60  # 10 minutes max
    for i in range(max_polls):
        time.sleep(10)
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{BASE}/engine/roundtable/status/{key}")
            if resp.status_code != 200:
                print(f"   Poll {i+1}: HTTP {resp.status_code}")
                continue
            status = resp.json()
            state = status.get("status", "unknown")
            print(f"   Poll {i+1}: {state}")
            if state == "completed":
                result = status.get("result", {})
                synthesis = result.get("synthesis", "No synthesis")
                participants = result.get("participants", [])
                turns = result.get("turn_count", 0)
                rounds = result.get("rounds", 0)
                duration = result.get("total_duration_ms", 0)
                session_id = result.get("session_id", "?")

                print(f"\n✅ ROUNDTABLE COMPLETE")
                print(f"   Participants: {participants}")
                print(f"   Rounds: {rounds}, Turns: {turns}")
                print(f"   Duration: {duration}ms")
                print(f"   Session: {session_id}")
                print(f"\n📝 SYNTHESIS:\n{synthesis[:3000]}")

                # Now feed the synthesis back into the rpg_master session
                feed_msg = f"""The roundtable of RPG agents has reached a consensus on tactics.

ROUNDTABLE SYNTHESIS:
{synthesis[:2000]}

Based on this consensus, narrate what happens next in Round 5. Seraphina should complete the seal this round. Use tools for any dice rolls needed."""

                resp5 = send_message(sid, feed_msg)
                return sid

            elif state == "failed":
                error = status.get("error", "Unknown error")
                print(f"   FAILED: {error}")
                return sid

    print("   TIMEOUT: Roundtable did not complete in 10 minutes")
    return sid


# ============================================================================
# PHASE 4: End Session + Log Events
# ============================================================================
def phase_4_end_session(sid: str):
    """
    ARIA ends the session, logs events and saves state.
    Tests memory persistence. Uses a FRESH session to avoid context overflow.
    """
    print("\n" + "="*80)
    print("PHASE 4: END SESSION — Save state and memory")
    print("="*80)

    # Create a fresh session to avoid OOM from accumulated context
    fresh_sid = create_session("rpg_master", "kimi")
    if not fresh_sid:
        print("FAILED to create session, trying original")
        fresh_sid = sid

    msg5 = """You are the Dungeon Master for the "Shadows of Absalom" Pathfinder 2e campaign.

Session 1 just ended. Here's what happened:
- Party: Thorin Ashveil (Dwarf Fighter) + Seraphina (Half-Elf Champion)
- Location: Drowning Stone warehouse, Puddles district, Absalom
- Thorin killed the Ritual Master with a critical hit and freed Caelus the dockworker
- Seraphina completed the binding seal, trapping the tentacled horror below
- NPCs: Caelus (freed prisoner), The Ritual Master (dead), Tentacled Horror (sealed)

Now USE YOUR TOOLS to save the session:

1. Call log_event: event="Thorin critical-killed the Ritual Master and freed Caelus from his chains", event_type="combat"
2. Call log_event: event="Seraphina completed the binding seal, sealing the Darklands horror beneath the Drowning Stone", event_type="milestone"
3. Call end_session: notes="Session 1 complete. Party cleared the Drowning Stone warehouse. Ritual Master dead, horror sealed, Caelus rescued. Party earned 120 XP (severe encounter)."
4. Call save_session_transcript: title="shadows_of_absalom", content="# Session 1: The Drowning Stone\\n\\nParty investigated missing dockworkers in the Puddles district. Tracked clues to the Drowning Stone warehouse where a cult was performing a summoning ritual. Combat ensued over 5 rounds. Thorin killed the Ritual Master with a critical battleaxe strike. Seraphina channeled a divine binding seal over 4 rounds, sealing the horror. Caelus the dockworker was rescued. The warehouse is now secured.", player_name="Thorin Ashveil", companion_name="Seraphina", dm_name="Aria"

Execute ALL tools."""

    resp5 = send_message(fresh_sid, msg5)
    tool_calls = resp5.get("tool_calls", [])
    print(f"\n📊 Phase 4 Results:")
    print(f"   Tool calls: {len(tool_calls)}")
    print(f"   Tools: {[tc.get('function',{}).get('name', tc.get('name','?')) for tc in tool_calls]}")

    return fresh_sid


# ============================================================================
# PHASE 5: New Session — Memory Continuity
# ============================================================================
def phase_5_new_session():
    """
    Create a brand new session and verify ARIA remembers the campaign.
    """
    print("\n" + "="*80)
    print("PHASE 5: NEW SESSION — Memory continuity test")
    print("="*80)

    # Create fresh session
    new_sid = create_session("rpg_master", "kimi")
    if not new_sid:
        print("FAILED to create new session")
        return

    # Ask ARIA to load the campaign and recall what happened
    msg6 = """You are the Dungeon Master continuing an existing Pathfinder 2e campaign.

USE YOUR TOOLS to reload the campaign state:
1. Call list_campaigns to see available campaigns
2. Call load_campaign with campaign_id "shadows_of_absalom"
3. Call get_party_status to see the current party
4. Call get_world_state to see where we are
5. Call list_npcs to see the NPC roster

Then give me a "Previously on Shadows of Absalom..." recap based on the actual saved data.

After the recap, START SESSION 2:
- Call start_session with an appropriate recap
- Set the scene: It's the morning after the Drowning Stone incident. Thorin and Sera wake in the Puddles district safe house. What happens next?

USE TOOLS for everything."""

    resp6 = send_message(new_sid, msg6)
    tool_calls = resp6.get("tool_calls", [])
    print(f"\n📊 Phase 5 Results:")
    print(f"   Tool calls: {len(tool_calls)}")
    print(f"   Tools: {[tc.get('function',{}).get('name', tc.get('name','?')) for tc in tool_calls]}")
    print(f"   New session: {new_sid}")

    # Verify campaign data exists on disk
    print("\n📁 Checking saved campaign files...")
    import subprocess
    result = subprocess.run(
        ["find", "/Users/najia/aria/aria_memories/rpg", "-type", "f", "-name", "*.yaml", "-o", "-name", "*.md"],
        capture_output=True, text=True
    )
    if result.stdout.strip():
        print("   Files found:")
        for f in result.stdout.strip().split("\n"):
            print(f"   📄 {f}")
    else:
        print("   ⚠️  No campaign files found on host (check container volume mounts)")

    return new_sid


# ============================================================================
# MAIN
# ============================================================================
def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "all"

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  ARIA RPG Structured Test — P0                               ║
║  Campaign: Shadows of Absalom                                ║
║  Player: Thorin Ashveil (Dwarf Fighter Lv1)                 ║
║  DM: rpg_master (ARIA)                                       ║
║  Started: {datetime.now().isoformat()[:19]}                            ║
║  Phase: {phase:<54s}║
╚══════════════════════════════════════════════════════════════╝
""")

    if phase in ("1", "all"):
        sid = phase_1_campaign_setup()
        if not sid:
            print("ABORT: Phase 1 failed")
            return
    else:
        sid = RPG_MASTER_SESSION

    if phase in ("2", "all"):
        sid = phase_2_resume_combat(sid)

    if phase in ("3", "all"):
        sid = phase_3_roundtable(sid)

    if phase in ("4", "all"):
        sid = phase_4_end_session(sid)

    if phase in ("5", "all"):
        phase_5_new_session()

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
