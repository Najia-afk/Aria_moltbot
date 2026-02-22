#!/usr/bin/env python3
"""Launch an async RPG roundtable and poll for results."""
from __future__ import annotations
import httpx
import json
import time
import sys

BASE = "https://192.168.1.53"
OUT = "aria_memories/rpg/sessions/roundtable1_setup.json"

topic = (
    "BEGIN NEW CAMPAIGN: Shadows of Absalom - Pathfinder 2e. "
    "rpg_master as Dungeon Master: Create a new campaign with ID shadows_of_absalom, "
    "title Shadows of Absalom, setting Golarion, starting level 1. "
    "Add characters claude_thorin_ashveil.yaml and aria_seraphina_lv1.yaml to the party. "
    "Start session 1 and describe the opening scene in the Precipice Quarter of Absalom at dusk. "
    "Use the rpg_campaign tools for campaign management and rpg_pathfinder tools for dice rolls. "
    "Store key entities in the knowledge graph. "
    "rpg_npc as NPC Controller: Play Sergeant Varen, a nervous city guard "
    "warning about 7 disappearances over 3 weeks near old Azlanti ruins. "
    "Register the NPC in the knowledge graph. "
    "rpg_paladin as Seraphina Dawnblade: Show concern for the missing people "
    "and offer to help investigate as a servant of Sarenrae. "
    "Player Thorin Ashveil, Dwarf Fighter Level 1, says: "
    "I grip my warhammer and look around the crumbling Precipice Quarter. "
    "Something feels wrong. I turn to the guard and ask about the disappearances."
)

payload = {
    "topic": topic,
    "agent_ids": ["rpg_master", "rpg_npc", "rpg_paladin"],
    "rounds": 3,
    "synthesizer_id": "rpg_master",
    "agent_timeout": 120,
    "total_timeout": 600,
}

print("Launching async roundtable...")
r = httpx.post(
    f"{BASE}/api/engine/roundtable/async",
    json=payload,
    verify=False,
    timeout=30,
)
print(f"Status: {r.status_code}")
print(r.text[:500])

if r.status_code >= 300:
    print("FAILED to launch")
    sys.exit(1)

d = r.json()
key = d.get("session_id", "")
print(f"Tracking key: {key}")
print("Polling for completion...")

for i in range(45):
    time.sleep(15)
    elapsed = (i + 1) * 15
    try:
        st = httpx.get(
            f"{BASE}/api/engine/roundtable/status/{key}",
            verify=False,
            timeout=10,
        )
    except Exception as e:
        print(f"  [{elapsed}s] poll error: {e}")
        continue

    if st.status_code == 404:
        print(f"  [{elapsed}s] not found yet")
        continue

    sd = st.json()
    status = sd.get("status", "?")
    print(f"  [{elapsed}s] {status}")

    if status == "completed":
        sid = sd.get("session_id", key)
        detail = httpx.get(
            f"{BASE}/api/engine/roundtable/{sid}",
            verify=False,
            timeout=30,
        )
        if detail.status_code == 200:
            result = detail.json()
            with open(OUT, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"DONE! Saved to {OUT}")
            print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
        else:
            print(f"Detail fetch failed: {detail.status_code}")
            print(detail.text[:300])
        break
    elif status == "failed":
        print(f"FAILED: {json.dumps(sd, indent=2)}")
        break
else:
    print("TIMEOUT after 11 minutes")
