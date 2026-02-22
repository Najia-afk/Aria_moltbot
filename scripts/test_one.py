#!/usr/bin/env python3
"""Quick test: create session + send one message to Aria."""
import json, subprocess

BASE = "http://localhost:8000"

def post(path, body):
    r = subprocess.run(
        ["curl", "-s", "-X", "POST", BASE + path,
         "-H", "Content-Type: application/json",
         "-d", json.dumps(body)],
        capture_output=True, text=True, timeout=120
    )
    try:
        return json.loads(r.stdout)
    except:
        return {"raw": r.stdout[:2000], "err": r.stderr[:200]}

print("Creating session...")
s = post("/api/engine/chat/sessions", {"agent_id": "aria", "session_type": "interactive"})
print(json.dumps(s, indent=2))
sid = s.get("id")

if sid:
    print(f"\nSession: {sid}")
    print("Sending test message...")
    m = post(f"/api/engine/chat/sessions/{sid}/messages", {
        "content": "Hello Aria. Quick test — please respond in 1 sentence confirming you can hear me.",
        "enable_thinking": False,
        "enable_tools": False
    })
    print(json.dumps(m, indent=2))
