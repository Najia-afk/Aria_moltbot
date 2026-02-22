#!/usr/bin/env python3
"""Live audit of Aria's production state. Run on Mac Mini."""
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone

BASE = "http://localhost:8000"

def get(path):
    r = subprocess.run(["curl", "-s", f"{BASE}{path}"], capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout.strip() else {}

print("\n" + "="*60)
print("ARIA LIVE AUDIT — " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
print("="*60)

# Health
h = get("/api/health")
print(f"\n[HEALTH] status={h.get('status')} db={h.get('database')} uptime={h.get('uptime_seconds')}s v={h.get('version')}")

# Session stats
st = get("/api/engine/sessions/stats")
print(f"\n[SESSIONS STATS]")
print(f"  total_sessions  : {st.get('total_sessions')}")
print(f"  total_messages  : {st.get('total_messages')}")
print(f"  active_agents   : {st.get('active_agents')}")
print(f"  oldest_session  : {st.get('oldest_session','')[:19]}")
print(f"  newest_activity : {st.get('newest_activity','')[:19]}")

# List all sessions
def get_all_sessions():
    sessions = []
    offset = 0
    while True:
        d = get(f"/api/engine/sessions?limit=100&offset={offset}&order=desc")
        batch = d.get("sessions", [])
        sessions.extend(batch)
        if not d.get("has_more") or not batch:
            break
        offset += 100
    return sessions

sessions = get_all_sessions()
print(f"\n[ALL SESSIONS] fetched={len(sessions)}")

# Break down by type
types = Counter(s.get("session_type", "?") for s in sessions)
print(f"\n[BY TYPE] {dict(types)}")

# Break down by agent
agents = Counter(s.get("agent_id", "?") for s in sessions)
print(f"\n[BY AGENT]")
for agent, count in agents.most_common():
    print(f"  {agent:<30} {count}")

# Ghost sessions
ghosts = [s for s in sessions if s.get("message_count", 0) == 0]
print(f"\n[GHOST SESSIONS] (message_count=0) count={len(ghosts)}")
for g in ghosts[:10]:
    print(f"  id={g['session_id'][:36]} created={g['created_at'][:19]} agent={g['agent_id']} type={g['session_type']}")

# Cron sessions
crons = [s for s in sessions if s.get("session_type") == "cron"]
print(f"\n[CRON SESSIONS] count={len(crons)}")
for c in crons[:5]:
    print(f"  id={c['session_id'][:36]} created={c['created_at'][:19]} agent={c['agent_id']} msgs={c.get('message_count',0)}")

# Models used across sessions
models_used = Counter(s.get("model", "?") for s in sessions if s.get("model"))
print(f"\n[MODELS USED IN SESSIONS]")
for m, count in models_used.most_common():
    print(f"  {m:<50} {count}")

# Archive table
a = get("/api/engine/sessions/archive?limit=5")
if isinstance(a, dict):
    print(f"\n[ARCHIVE TABLE] total={a.get('total', a.get('count','unknown'))}")
else:
    print(f"\n[ARCHIVE TABLE] response={str(a)[:100]}")

# Session with Shiva's ID
shiva_id = "7d4953a6-beda-4d9c-b9dc-6f77614bde3b"
sv = get(f"/api/engine/sessions/{shiva_id}")
print(f"\n[SHIVA SESSION {shiva_id[:8]}...]")
if "session_id" in sv:
    print(f"  agent={sv.get('agent_id')} type={sv.get('session_type')} msgs={sv.get('message_count')} model={sv.get('model')}")
else:
    print(f"  {sv}")

# Agents registered
ag = get("/api/engine/agents?limit=30")
if isinstance(ag, dict):
    agent_list = ag.get("agents", ag.get("items", []))
elif isinstance(ag, list):
    agent_list = ag
else:
    agent_list = []
print(f"\n[REGISTERED AGENTS] count={len(agent_list)}")
for a in agent_list:
    if isinstance(a, dict):
        print(f"  {str(a.get('id','')):<25} model={a.get('model','?'):<40} status={a.get('status','?')}")

# Routing config
rc = get("/api/engine/config")
if isinstance(rc, dict):
    print(f"\n[ENGINE CONFIG]")
    for k, v in list(rc.items())[:15]:
        print(f"  {k}: {v}")

print("\n" + "="*60 + "\n")
