#!/usr/bin/env python3
"""Comprehensive Aria API test — exercises every endpoint category."""

import json, os, sys, time, requests, uuid
from datetime import datetime, timezone

API  = "http://localhost:45669"
WEB  = "http://localhost:55559"
LITE = "http://localhost:11577"
KEY  = os.getenv("ARIA_API_KEY", "")
ADMIN= os.getenv("ARIA_ADMIN_KEY", KEY)
LKEY = os.getenv("LITELLM_MASTER_KEY", os.getenv("LITELLM_API_KEY", ""))

H  = {"X-API-Key": KEY} if KEY else {}
HA = {"X-API-Key": ADMIN} if ADMIN else {}
HL = {"Authorization": f"Bearer {LKEY}"} if LKEY else {}

results = []

def t(name, method, url, *, ok=(200,201,204), headers=None, json_data=None, params=None, data=None, timeout=30):
    """Run a test and record PASS/FAIL."""
    hd = headers or H
    try:
        r = requests.request(method, url, headers=hd, json=json_data, params=params, data=data, timeout=timeout)
        passed = r.status_code in ok
        results.append((name, "PASS" if passed else "FAIL", r.status_code))
        if not passed:
            body = r.text[:200]
            print(f"  FAIL {name}: {r.status_code} {body}")
        return r
    except Exception as e:
        results.append((name, "ERR", str(e)[:80]))
        print(f"  ERR  {name}: {e}")
        return None

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# ─── HEALTH & STATUS ────────────────────────────────────────
section("Health & Status")
t("GET /health",             "GET", f"{API}/health")
t("GET /health/db",          "GET", f"{API}/health/db")
t("GET /status",             "GET", f"{API}/status")
t("GET /heartbeat",          "GET", f"{API}/heartbeat")
t("GET /heartbeat/latest",   "GET", f"{API}/heartbeat/latest")
t("GET /stats",              "GET", f"{API}/stats")
t("GET /metrics",            "GET", f"{API}/metrics")
t("GET /api/metrics",        "GET", f"{API}/api/metrics")
t("GET /host-stats",         "GET", f"{API}/host-stats")
t("GET /table-stats",        "GET", f"{API}/table-stats", headers=HA)
t("GET /performance",        "GET", f"{API}/performance")

# ─── WEB FRONTEND ───────────────────────────────────────────
section("Web Frontend (Flask)")
t("WEB /",                   "GET", f"{WEB}/", headers={})
t("WEB /health",             "GET", f"{WEB}/api/health", headers={}, ok=(200,404))

# ─── LITELLM ────────────────────────────────────────────────
section("LiteLLM Proxy")
t("LITE /health",            "GET", f"{LITE}/health", headers=HL, timeout=120)
t("LITE /models",            "GET", f"{LITE}/models", headers=HL)
t("GET /litellm/health",     "GET", f"{API}/litellm/health")
t("GET /litellm/models",     "GET", f"{API}/litellm/models")
t("GET /litellm/spend",      "GET", f"{API}/litellm/spend")
t("GET /litellm/global-spend","GET",f"{API}/litellm/global-spend")

# ─── MODELS ─────────────────────────────────────────────────
section("Models")
t("GET /models/db",          "GET", f"{API}/models/db")
t("GET /models/config",      "GET", f"{API}/models/config")
t("GET /models/available",   "GET", f"{API}/models/available")
t("GET /models/pricing",     "GET", f"{API}/models/pricing")
t("POST /models/db/sync",    "POST",f"{API}/models/db/sync")
# Get first model id for detail test
r = requests.get(f"{API}/models/db", headers=H, timeout=10)
model_list = r.json() if r.ok else []
if model_list:
    mid = model_list[0].get("id") or model_list[0].get("model_id")
    t("GET /models/db/:id",  "GET", f"{API}/models/db/{mid}")
    # Update a model to test app_managed
    t("PUT /models/db/:id",  "PUT", f"{API}/models/db/{mid}",
      json_data={"display_name": "Test Update", "enabled": True})
    # Re-sync should skip it
    r2 = t("POST /models/db/sync (skip managed)", "POST", f"{API}/models/db/sync")
    if r2 and r2.ok:
        body = r2.json()
        print(f"    sync result: {body}")

# ─── AGENTS ─────────────────────────────────────────────────
section("Agents")
t("GET /agents/db",          "GET", f"{API}/agents/db")
t("POST /agents/db/sync",    "POST",f"{API}/agents/db/sync")
t("POST /agents/db/enable-core", "POST", f"{API}/agents/db/enable-core")
r = requests.get(f"{API}/agents/db", headers=H, timeout=10)
agents = r.json() if r.ok else []
if agents:
    aid = agents[0].get("id") or agents[0].get("agent_id")
    t("GET /agents/db/:id",  "GET", f"{API}/agents/db/{aid}")
    t("PUT /agents/db/:id",  "PUT", f"{API}/agents/db/{aid}",
      json_data={"display_name": "Test Agent Update"})
    t("POST /agents/db/:id/enable", "POST", f"{API}/agents/db/{aid}/enable")

# ─── ENGINE ─────────────────────────────────────────────────
section("Engine")
t("GET /engine/agents",      "GET", f"{API}/engine/agents")
t("GET /engine/agents/metrics","GET",f"{API}/engine/agents/metrics")
# Create a chat session
r = t("POST /engine/chat/sessions", "POST", f"{API}/engine/chat/sessions",
      json_data={"user_message": "Hello Aria, respond briefly"}, ok=(200,201,202))
if r and r.ok:
    body = r.json()
    sid = body.get("session_id", "")
    t("GET /engine/chat/sessions","GET", f"{API}/engine/chat/sessions")
    if sid:
        t("GET /engine/chat/sessions/:id","GET", f"{API}/engine/chat/sessions/{sid}")

# ─── SESSIONS ───────────────────────────────────────────────
section("Sessions")
t("GET /sessions",           "GET", f"{API}/sessions")
t("GET /sessions/stats",     "GET", f"{API}/sessions/stats")
t("GET /sessions/hourly",    "GET", f"{API}/sessions/hourly")
r = t("POST /sessions",      "POST",f"{API}/sessions",
      json_data={"title": "Test Session", "source": "test"})
if r and r.ok:
    sid2 = r.json().get("id")
    if sid2:
        t("PATCH /sessions/:id", "PATCH", f"{API}/sessions/{sid2}",
          json_data={"title": "Updated Test"})
        t("DELETE /sessions/:id","DELETE",f"{API}/sessions/{sid2}")

# ─── MEMORIES ────────────────────────────────────────────────
section("Memories")
t("GET /memories",           "GET", f"{API}/memories")
t("GET /memories/search",    "GET", f"{API}/memories/search", params={"query": "test"}, ok=(200,502))
r = t("POST /memories",      "POST",f"{API}/memories",
      json_data={"key": f"test_{uuid.uuid4().hex[:8]}", "content": "Test memory content", "category": "test"})
if r and r.ok:
    mkey = r.json().get("key", "")
    if mkey:
        t("GET /memories/:key",   "GET", f"{API}/memories/{mkey}")
        t("PATCH /memories/:key", "PATCH", f"{API}/memories/{mkey}",
          json_data={"content": "Updated memory"})
        t("DELETE /memories/:key","DELETE",f"{API}/memories/{mkey}")

# ─── SEMANTIC MEMORIES ──────────────────────────────────────
section("Semantic Memories")
t("GET /memories/semantic",  "GET", f"{API}/memories/semantic")
t("GET /memories/semantic/stats","GET",f"{API}/memories/semantic/stats")
t("POST /memories/semantic", "POST",f"{API}/memories/semantic",
  json_data={"content": "Paris is the capital of France", "category": "fact"}, ok=(200,201,422,502))

# ─── THOUGHTS ───────────────────────────────────────────────
section("Thoughts")
t("GET /thoughts",           "GET", f"{API}/thoughts")
r = t("POST /thoughts",      "POST",f"{API}/thoughts",
      json_data={"content": "A test thought", "category": "reflection"})
if r and r.ok:
    tid = r.json().get("id")
    if tid:
        t("PATCH /thoughts/:id", "PATCH", f"{API}/thoughts/{tid}",
          json_data={"content": "Updated thought"})
        t("DELETE /thoughts/:id","DELETE",f"{API}/thoughts/{tid}")

# ─── ACTIVITIES ─────────────────────────────────────────────
section("Activities")
t("GET /activities",         "GET", f"{API}/activities")
t("GET /activities/timeline","GET", f"{API}/activities/timeline")
t("GET /activities/visualization","GET", f"{API}/activities/visualization")
t("GET /activities/cron-summary","GET", f"{API}/activities/cron-summary")
r = t("POST /activities",    "POST",f"{API}/activities",
      json_data={"type": "test", "description": "Test activity"})
if r and r.ok:
    actid = r.json().get("id")
    if actid:
        t("PATCH /activities/:id","PATCH",f"{API}/activities/{actid}",
          json_data={"description": "Updated"})
        t("DELETE /activities/:id","DELETE",f"{API}/activities/{actid}")

# ─── GOALS ──────────────────────────────────────────────────
section("Goals")
t("GET /goals",              "GET", f"{API}/goals")
t("GET /goals/sprint-summary","GET",f"{API}/goals/sprint-summary")
r = t("POST /goals",         "POST",f"{API}/goals",
      json_data={"title": "Test Goal", "status": "active", "priority": 2})
if r and r.ok:
    gid = r.json().get("id")
    if gid:
        t("GET /goals/:id",     "GET", f"{API}/goals/{gid}")
        t("PATCH /goals/:id",   "PATCH",f"{API}/goals/{gid}",
          json_data={"status": "completed"})
        t("DELETE /goals/:id",  "DELETE",f"{API}/goals/{gid}")

# ─── HOURLY GOALS ──────────────────────────────────────────
section("Hourly Goals")
t("GET /hourly-goals",       "GET", f"{API}/hourly-goals")
r = t("POST /hourly-goals",  "POST",f"{API}/hourly-goals",
      json_data={"description": "Test Hourly Goal", "status": "pending", "hour_slot": "14", "goal_type": "test"})
if r and r.ok:
    hgid = r.json().get("id")
    if hgid:
        t("PATCH /hourly-goals/:id","PATCH",f"{API}/hourly-goals/{hgid}",
          json_data={"status": "done"})

# ─── TASKS ──────────────────────────────────────────────────
section("Tasks")
t("GET /tasks",              "GET", f"{API}/tasks")
r = t("POST /tasks",         "POST",f"{API}/tasks",
      json_data={"description": "Test Task", "status": "pending", "task_type": "general", "agent_type": "coordinator"})
if r and r.ok:
    tkid = r.json().get("id")
    if tkid:
        t("PATCH /tasks/:id",   "PATCH",f"{API}/tasks/{tkid}",
          json_data={"status": "done"})

# ─── LESSONS ────────────────────────────────────────────────
section("Lessons")
t("GET /lessons",            "GET", f"{API}/lessons")
t("GET /lessons/check",      "GET", f"{API}/lessons/check")
t("POST /lessons/seed",      "POST",f"{API}/lessons/seed")
r = t("POST /lessons",       "POST",f"{API}/lessons",
      json_data={"error_pattern": "test pattern", "error_type": "test_error", "resolution": "fixed it", "skill_name": "test"})
if r and r.ok:
    lid = r.json().get("id")
    if lid:
        t("PATCH /lessons/:id", "PATCH",f"{API}/lessons/{lid}",
          json_data={"content": "Updated lesson"})
        t("DELETE /lessons/:id","DELETE",f"{API}/lessons/{lid}")

# ─── PROPOSALS ──────────────────────────────────────────────
section("Proposals")
t("GET /proposals",          "GET", f"{API}/proposals")
r = t("POST /proposals",     "POST",f"{API}/proposals",
      json_data={"title": "Test Proposal", "description": "A test", "status": "draft"})
if r and r.ok:
    pid = r.json().get("id")
    if pid:
        t("GET /proposals/:id", "GET", f"{API}/proposals/{pid}")
        t("PATCH /proposals/:id","PATCH",f"{API}/proposals/{pid}",
          json_data={"status": "approved"})
        t("DELETE /proposals/:id","DELETE",f"{API}/proposals/{pid}")

# ─── SOCIAL ─────────────────────────────────────────────────
section("Social")
t("GET /social",             "GET", f"{API}/social")
r = t("POST /social",        "POST",f"{API}/social",
      json_data={"content": "Test Post", "platform": "test"})
if r and r.ok:
    spid = r.json().get("id")
    if spid:
        t("PATCH /social/:id",  "PATCH",f"{API}/social/{spid}",
          json_data={"content": "Updated post"})
        t("DELETE /social/:id", "DELETE",f"{API}/social/{spid}")

# ─── SKILLS ─────────────────────────────────────────────────
section("Skills")
t("GET /skills",             "GET", f"{API}/skills")
t("GET /skills/stats",       "GET", f"{API}/skills/stats")
t("GET /skills/stats/summary","GET",f"{API}/skills/stats/summary")
t("GET /skills/coherence",   "GET", f"{API}/skills/coherence")
t("GET /skills/insights",    "GET", f"{API}/skills/insights")
t("GET /skills/health/dashboard","GET",f"{API}/skills/health/dashboard")
t("POST /skills/seed",       "POST",f"{API}/skills/seed")
t("GET /skill-graph",        "GET", f"{API}/skill-graph")

# ─── KNOWLEDGE GRAPH ───────────────────────────────────────
section("Knowledge Graph")
t("GET /knowledge-graph",    "GET", f"{API}/knowledge-graph")
t("GET /knowledge-graph/entities","GET",f"{API}/knowledge-graph/entities")
t("GET /knowledge-graph/relations","GET",f"{API}/knowledge-graph/relations")
t("GET /knowledge-graph/search","GET",f"{API}/knowledge-graph/search", params={"q": "test"})
t("GET /knowledge-graph/query-log","GET",f"{API}/knowledge-graph/query-log")
t("POST /knowledge-graph/sync-skills","POST",f"{API}/knowledge-graph/sync-skills")

# ─── WORKING MEMORY ────────────────────────────────────────
section("Working Memory")
t("GET /working-memory",     "GET", f"{API}/working-memory")
t("GET /working-memory/stats","GET",f"{API}/working-memory/stats")
t("GET /working-memory/context","GET",f"{API}/working-memory/context")
r = t("POST /working-memory", "POST",f"{API}/working-memory",
      json_data={"key": "test_wm", "value": "test data", "category": "test"})
if r and r.ok:
    wmid = r.json().get("id")
    if wmid:
        t("PATCH /working-memory/:id","PATCH",f"{API}/working-memory/{wmid}",
          json_data={"value": "updated"})
        t("DELETE /working-memory/:id","DELETE",f"{API}/working-memory/{wmid}")

# ─── JOBS / SCHEDULE ───────────────────────────────────────
section("Jobs & Schedule")
t("GET /jobs",               "GET", f"{API}/jobs")
t("GET /jobs/live",          "GET", f"{API}/jobs/live")
t("POST /jobs/sync",         "POST",f"{API}/jobs/sync")
t("GET /schedule",           "GET", f"{API}/schedule")
t("POST /schedule/tick",     "POST",f"{API}/schedule/tick")

# ─── ANALYSIS ──────────────────────────────────────────────
section("Analysis")
t("POST /analysis/patterns/detect","POST",f"{API}/analysis/patterns/detect",
  json_data={"text": "This is a test pattern"})
t("GET /analysis/patterns/history","GET",f"{API}/analysis/patterns/history")
t("GET /analysis/compression/history","GET",f"{API}/analysis/compression/history")
t("GET /analysis/sentiment/history","GET",f"{API}/analysis/sentiment/history")
t("GET /analysis/sentiment/score","GET",f"{API}/analysis/sentiment/score")

# ─── SECURITY ──────────────────────────────────────────────
section("Security")
t("GET /security-events",    "GET", f"{API}/security-events")
t("GET /security-events/stats","GET",f"{API}/security-events/stats")
t("GET /rate-limits",        "GET", f"{API}/rate-limits")

# ─── RECORDS / MODEL USAGE ─────────────────────────────────
section("Records & Model Usage")
t("GET /records",            "GET", f"{API}/records")
t("GET /model-usage",        "GET", f"{API}/model-usage")
t("GET /model-usage/stats",  "GET", f"{API}/model-usage/stats")
t("POST /model-usage",       "POST",f"{API}/model-usage",
  json_data={"model": "test-model", "tokens_in": 100, "tokens_out": 50, "cost": 0.001})

# ─── API KEY ROTATIONS ─────────────────────────────────────
section("API Key Rotations")
t("GET /api-key-rotations",  "GET", f"{API}/api-key-rotations")

# ─── ARTIFACTS ──────────────────────────────────────────────
section("Artifacts")
t("GET /artifacts",          "GET", f"{API}/artifacts")
t("POST /artifacts",         "POST",f"{API}/artifacts",
  json_data={"category": "drafts", "filename": "test.txt", "content": "hello"}, ok=(200,201,422))

# ─── ADMIN FILES ────────────────────────────────────────────
section("Admin Files")
t("GET /admin/files/agents",   "GET", f"{API}/admin/files/agents", headers=HA)
t("GET /admin/files/memories", "GET", f"{API}/admin/files/memories", headers=HA)
t("GET /admin/files/mind",     "GET", f"{API}/admin/files/mind", headers=HA)
t("GET /admin/files/souvenirs","GET", f"{API}/admin/files/souvenirs", headers=HA)

# ─── SOUL ───────────────────────────────────────────────────
section("Soul")
t("GET /soul/SOUL.md",        "GET", f"{API}/soul/SOUL.md", headers=HA)
t("GET /soul/IDENTITY.md",    "GET", f"{API}/soul/IDENTITY.md", headers=HA)

# ─── SEARCH ─────────────────────────────────────────────────
section("Search")
t("GET /search",              "GET", f"{API}/search", params={"q": "aria"})

# ─── GRAPHQL ────────────────────────────────────────────────
section("GraphQL")
t("POST /graphql",            "POST",f"{API}/graphql",
  json_data={"query": "{ __schema { types { name } } }"}, ok=(200,))

# ─── HEARTBEAT POST ────────────────────────────────────────
section("Heartbeat Post")
t("POST /heartbeat",          "POST",f"{API}/heartbeat",
  json_data={"source": "test", "status": "ok"})

# ─── PERFORMANCE POST ──────────────────────────────────────
section("Performance Post")
t("POST /performance",        "POST",f"{API}/performance",
  json_data={"endpoint": "/test", "method": "GET", "duration_ms": 42, "status_code": 200, "review_period": "2026-02"})

# ─── MAINTENANCE ────────────────────────────────────────────
section("Maintenance")
t("POST /maintenance",        "POST",f"{API}/maintenance", headers=HA, ok=(200,201,202,422))

# ─── RPG ────────────────────────────────────────────────────
section("RPG")
t("GET /rpg/campaigns",       "GET", f"{API}/rpg/campaigns")

# ─── PROVIDERS ──────────────────────────────────────────────
section("Providers")
t("GET /providers/balances",   "GET", f"{API}/providers/balances")

# ─── SOCIAL SPECIAL ENDPOINTS ──────────────────────────────
section("Social Special")
t("POST /social/cleanup",     "POST",f"{API}/social/cleanup",
  json_data={"days_old": 30}, ok=(200,201,202))
t("POST /social/dedupe",      "POST",f"{API}/social/dedupe",
  json_data={}, ok=(200,201,202))

# ─── SKILLS INVOCATIONS ────────────────────────────────────
section("Skills Invocations")
t("POST /skills/invocations", "POST",f"{API}/skills/invocations",
  json_data={"skill_name": "health", "status": "success", "duration_ms": 100},
  ok=(200,201))

# ─── SECURITY POST ─────────────────────────────────────────
section("Security Events Post")
t("POST /security-events",    "POST",f"{API}/security-events",
  json_data={"event_type": "test", "severity": "low", "description": "Test event"})

# ─── API KEY ROTATION POST ─────────────────────────────────
section("API Key Rotation Post")
t("POST /api-key-rotations",  "POST",f"{API}/api-key-rotations",
  json_data={"service": "test", "reason": "rotation test"})

# ─── ENGINE DELEGATES ──────────────────────────────────────
section("Engine Agent Delegation")
t("POST /engine/agents/delegate","POST",f"{API}/engine/agents/delegate",
  json_data={"agent_id": "aria_coordinator", "task": "Say hello"},
  ok=(200,201,202,422,404))

# ─── MODELS RELOAD ─────────────────────────────────────────
section("Models Reload")
t("POST /models/reload",      "POST",f"{API}/models/reload")

# ─── KNOWLEDGE GRAPH ENTITIES/RELATIONS POST ───────────────
section("KG write")
t("POST /knowledge-graph/entities","POST",f"{API}/knowledge-graph/entities",
  json_data={"name": "TestEntity", "type": "concept", "description": "A test"})
t("POST /knowledge-graph/relations","POST",f"{API}/knowledge-graph/relations",
  json_data={"source": "TestEntity", "target": "Aria", "relation": "created_by"},
  ok=(200,201,422))

# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
section("RESULTS SUMMARY")
passes = sum(1 for _,s,_ in results if s == "PASS")
fails  = sum(1 for _,s,_ in results if s == "FAIL")
errs   = sum(1 for _,s,_ in results if s == "ERR")
total  = len(results)

print(f"\n  Total: {total}  |  PASS: {passes}  |  FAIL: {fails}  |  ERR: {errs}")
print(f"  Rate:  {passes/total*100:.1f}%\n")

if fails + errs > 0:
    print("  Failed/Error tests:")
    for name, status, code in results:
        if status != "PASS":
            print(f"    [{status}] {name} -> {code}")

print()
sys.exit(0 if errs == 0 else 1)
