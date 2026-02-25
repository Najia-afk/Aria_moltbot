#!/usr/bin/env python3
"""
Comprehensive dev test — hit every API endpoint, GraphQL, Web page, DB table.
Run: python scripts/dev_test_all.py
"""
import json
import sys
import time
import traceback
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

API = "http://localhost:8000"
WEB = "http://localhost:5050"

PASS = 0
FAIL = 0
ERRORS: list[str] = []


def _req(method: str, url: str, body=None, headers=None, expect_status=None):
    """Make HTTP request, return (status, parsed_body)."""
    hdrs = {"Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = urlopen(req, timeout=30)
        raw = resp.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return resp.status, parsed
    except HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return e.code, parsed
    except URLError as e:
        return 0, str(e)


def check(name: str, method: str, url: str, body=None, expect=200, allow=None):
    """Test an endpoint, log pass/fail."""
    global PASS, FAIL
    allowed = {expect} if allow is None else allow
    status, resp = _req(method, url, body)
    ok = status in allowed
    icon = "✅" if ok else "❌"

    detail = ""
    if isinstance(resp, dict):
        # Show first few keys
        keys = list(resp.keys())[:5]
        detail = f" keys={keys}"
    elif isinstance(resp, list):
        detail = f" len={len(resp)}"
    elif isinstance(resp, str):
        detail = f" {resp[:80]}"

    print(f"  {icon} {name}: {method} → {status}{detail}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(f"{name}: expected {allowed}, got {status} — {str(resp)[:200]}")
    return status, resp


def check_web(name: str, path: str, expect=200):
    """Test a web page returns expected status."""
    global PASS, FAIL
    status, resp = _req("GET", f"{WEB}{path}")
    ok = status == expect
    icon = "✅" if ok else "❌"
    title = ""
    if isinstance(resp, str) and "<title>" in resp:
        import re
        m = re.search(r"<title>(.*?)</title>", resp)
        if m:
            title = f' title="{m.group(1)}"'
    print(f"  {icon} {name}: GET {path} → {status}{title}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        ERRORS.append(f"WEB {name}: expected {expect}, got {status}")
    return status, resp


def graphql(name: str, query: str, variables=None, expect_data=True):
    """Test a GraphQL query."""
    global PASS, FAIL
    body = {"query": query}
    if variables:
        body["variables"] = variables
    status, resp = _req("POST", f"{API}/graphql", body)
    has_data = isinstance(resp, dict) and "data" in resp and resp["data"] is not None
    has_errors = isinstance(resp, dict) and "errors" in resp
    ok = status == 200 and (has_data if expect_data else True) and not has_errors
    icon = "✅" if ok else "❌"

    detail = ""
    if has_data and resp["data"]:
        keys = list(resp["data"].keys())
        detail = f" data_keys={keys}"
    if has_errors:
        detail += f" ERRORS={resp['errors'][:1]}"

    print(f"  {icon} GQL {name}: {status}{detail}")
    if ok:
        PASS += 1
    else:
        FAIL += 1
        err_msg = str(resp.get("errors", ""))[:200] if isinstance(resp, dict) else str(resp)[:200]
        ERRORS.append(f"GQL {name}: {err_msg}")
    return status, resp


# ─── 1. API HEALTH ──────────────────────────────────────────────────────────
print("\n═══ 1. API HEALTH ═══")
check("health", "GET", f"{API}/health")
check("health/detailed", "GET", f"{API}/health/detailed", allow={200, 404})

# ─── 2. CRUD — READ ENDPOINTS ───────────────────────────────────────────────
print("\n═══ 2. CRUD READ ENDPOINTS ═══")
check("activities", "GET", f"{API}/activities/")
check("thoughts", "GET", f"{API}/thoughts/")
check("memories", "GET", f"{API}/memories/")
check("goals", "GET", f"{API}/goals/")
check("sessions", "GET", f"{API}/sessions/")
check("lessons", "GET", f"{API}/lessons/")
check("social", "GET", f"{API}/social/")
check("proposals", "GET", f"{API}/proposals/")
check("model-usage", "GET", f"{API}/model-usage/")
check("security", "GET", f"{API}/security-events/")
check("records", "GET", f"{API}/records/")
check("working-memory", "GET", f"{API}/working-memory/")

# ─── 3. CRUD — WRITE + DELETE CYCLES ────────────────────────────────────────
print("\n═══ 3. CRUD WRITE/DELETE CYCLES ═══")

# Activity
s, r = check("POST activity", "POST", f"{API}/activities", body={
    "action": "test_dev_check", "skill": "dev_test", "details": {}, "success": True
}, allow={200, 201})
if s in (200, 201) and isinstance(r, dict) and "id" in r:
    aid = r["id"]
    check("PATCH activity", "PATCH", f"{API}/activities/{aid}", body={"details": {"updated": True}})
    check("DELETE activity", "DELETE", f"{API}/activities/{aid}", allow={200, 204})

# Thought
s, r = check("POST thought", "POST", f"{API}/thoughts", body={
    "content": "Test thought from dev script", "thought_type": "observation"
}, allow={200, 201})
if s in (200, 201) and isinstance(r, dict) and "id" in r:
    tid = r["id"]
    check("PATCH thought", "PATCH", f"{API}/thoughts/{tid}", body={"content": "Updated thought"})
    check("DELETE thought", "DELETE", f"{API}/thoughts/{tid}", allow={200, 204})

# Goal
s, r = check("POST goal", "POST", f"{API}/goals", body={
    "title": "Dev test goal", "description": "Created by automated test", "priority": 5
}, allow={200, 201})
if s in (200, 201) and isinstance(r, dict) and "id" in r:
    gid = r["id"]
    check("GET goal", "GET", f"{API}/goals/{gid}")
    check("DELETE goal", "DELETE", f"{API}/goals/{gid}", allow={200, 204})

# Memory  (use realistic data — POST noise filter rejects keys/values containing "test")
_mem_key = "aria_devcheck_preference_2026"
s, r = check("POST memory", "POST", f"{API}/memories", body={
    "key": _mem_key, "value": "Aria prefers concise summaries when reviewing logs.", "category": "preference"
}, allow={200, 201})
if s in (200, 201) and isinstance(r, dict) and r.get("upserted"):
    check("PATCH memory", "PATCH", f"{API}/memories/{_mem_key}", body={"value": "Aria prefers detailed summaries."})
    check("DELETE memory", "DELETE", f"{API}/memories/{_mem_key}", allow={200, 204})

# ─── 4. ANALYSIS / PATTERNS / COMPRESSION ───────────────────────────────────
print("\n═══ 4. ANALYSIS ENDPOINTS ═══")
check("patterns", "GET", f"{API}/analysis/patterns/", allow={200, 404})
check("compression-stats", "GET", f"{API}/analysis/compression/stats", allow={200, 404})

# ─── 5. SENTIMENT ────────────────────────────────────────────────────────────
print("\n═══ 5. SENTIMENT ENDPOINTS ═══")
check("sentiment/score", "POST", f"{API}/analysis/sentiment/message", body={
    "message": "I love how Aria is evolving, this is amazing progress!", "method": "lexicon"
}, allow={200, 422})
check("sentiment/history", "GET", f"{API}/analysis/sentiment/history", allow={200, 404})

# ─── 6. SKILL HEALTH ────────────────────────────────────────────────────────
print("\n═══ 6. SKILL HEALTH ═══")
check("skill-catalog", "GET", f"{API}/skills/skills", allow={200, 404})
check("skill-health", "GET", f"{API}/skills/health/dashboard")

# ─── 7. OPERATIONS ──────────────────────────────────────────────────────────
print("\n═══ 7. OPERATIONS ═══")
check("cron-jobs", "GET", f"{API}/operations/cron-jobs", allow={200, 404})
check("rate-limits", "GET", f"{API}/operations/rate-limits", allow={200, 404})

# ─── 8. LITELLM ─────────────────────────────────────────────────────────────
print("\n═══ 8. LITELLM ═══")
check("litellm/spend", "GET", f"{API}/litellm/spend", allow={200, 500})
check("litellm/models", "GET", f"{API}/litellm/models", allow={200, 500})

# ─── 9. MODELS CONFIG ───────────────────────────────────────────────────────
print("\n═══ 9. MODELS CONFIG ═══")
check("models/catalog", "GET", f"{API}/models/catalog", allow={200, 404})

# ─── 10. GRAPHQL ─────────────────────────────────────────────────────────────
print("\n═══ 10. GRAPHQL QUERIES ═══")
graphql("activities", "{ activities(limit: 3) { id action } }")
graphql("thoughts", "{ thoughts(limit: 3) { id content } }")
graphql("memories", "{ memories(limit: 3) { id key value } }")
graphql("goals", "{ goals(limit: 3) { id title } }")
graphql("sessions", "{ sessions(limit: 3) { id sessionType } }")

print("\n═══ 11. GRAPHQL CURSOR PAGINATION ═══")
graphql("activities_connection", """
    { activitiesConnection(first: 2) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges { cursor node { id action } }
    } }
""")
graphql("thoughts_connection", """
    { thoughtsConnection(first: 2) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges { cursor node { id content } }
    } }
""")
graphql("memories_connection", """
    { memoriesConnection(first: 2) {
        totalCount
        pageInfo { hasNextPage endCursor }
        edges { cursor node { id key } }
    } }
""")

print("\n═══ 12. GRAPHQL MUTATIONS ═══")
s, r = graphql("createActivity", """
    mutation { createActivity(input: { action: "gql_dev_test", details: "From GraphQL" }) {
        id action details
    } }
""")
if isinstance(r, dict) and r.get("data", {}).get("createActivity"):
    aid = r["data"]["createActivity"]["id"]
    graphql("deleteActivity", f'mutation {{ deleteActivity(activityId: "{aid}") {{ deleted id }} }}')

s, r = graphql("createThought", """
    mutation { createThought(input: { content: "GQL test thought", category: "test" }) {
        id content
    } }
""")
if isinstance(r, dict) and (r.get("data") or {}).get("createThought"):
    tid = r["data"]["createThought"]["id"]
    graphql("deleteThought", f'mutation {{ deleteThought(thoughtId: "{tid}") {{ deleted id }} }}')

# ─── 13. GRAPH (Semantic Knowledge Graph) ────────────────────────────────────
print("\n═══ 13. SEMANTIC GRAPH ═══")
graphql("stats", "{ stats { activitiesCount thoughtsCount memoriesCount goalsCount lastActivity } }")
graphql("knowledgeEntities", '{ knowledgeEntities(limit: 3) { id name entityType } }')

# ─── 14. WEB PAGES ──────────────────────────────────────────────────────────
print("\n═══ 14. WEB PAGES ═══")
check_web("home", "/")
check_web("chat", "/chat")
check_web("operations-hub", "/operations")
check_web("operations-cron", "/operations/cron/")
check_web("model-manager", "/model-manager")
check_web("sessions", "/sessions")
check_web("skill-health", "/skill-health")
check_web("skill-catalog", "/skills")
check_web("sentiment", "/sentiment")
check_web("goals", "/goals")
check_web("thoughts", "/thoughts")
check_web("activities", "/activities")
check_web("memories", "/memories")
check_web("social", "/social")
check_web("security", "/security")

# ─── 15. DB TABLE CHECK (via API records) ────────────────────────────────────
print("\n═══ 15. DB TABLES (via /records/) ═══")
s, r = check("records-overview", "GET", f"{API}/records/")
if isinstance(r, dict):
    tables = r.get("tables", r.get("data", r))
    if isinstance(tables, dict):
        for table, info in sorted(tables.items()):
            if isinstance(info, int):
                count = info
            elif isinstance(info, dict):
                count = info.get("count", "?")
            else:
                count = "?"
            print(f"    📊 {table}: {count} rows")
    elif isinstance(tables, list):
        for t in tables:
            if isinstance(t, dict):
                name = t.get("name", t.get("table", "?"))
                count = t.get("count", t.get("total", "?"))
            else:
                name = str(t)
                count = "?"
            print(f"    📊 {name}: {count} rows")

# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed")
print(f"{'='*60}")
if ERRORS:
    print("\n  FAILURES:")
    for e in ERRORS:
        print(f"    ❌ {e}")
print()
sys.exit(1 if FAIL else 0)
