# S1-04: Verify Sprint 7 Completions from Yesterday
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
Yesterday's session (2026-02-11) defined Sprints 1–7 with 74 tickets. Sprint 7 specifically addressed dashboard data fixes. We need to verify that the key completions actually work in production:
- S7-01: DOMContentLoaded Event bug fix (4 pages)
- S7-02: Working Memory JSONB display fix
- S7-03: LiteLLM direct DB queries (marked DONE)
- S7-04: Dashboard activity timeline server aggregation
- S7-05: Sprint board NULL fix + auto-refresh

## Root Cause
No automated verification was run after yesterday's sprint deployment. Container restart may have reverted uncommitted changes, or Docker rebuilds may not have picked up all file changes.

## Fix
This is a **verification-only ticket** — no code changes unless failures are found.

Run each verification check below and document results. If any fail, create a hotfix sub-ticket.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Verification only |
| 2 | .env for secrets (zero in code) | ❌ | No changes |
| 3 | models.yaml single source of truth | ❌ | No changes |
| 4 | Docker-first testing | ✅ | All checks against running containers |
| 5 | aria_memories only writable path | ❌ | No writes |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — can run immediately.

## Verification
```bash
# === S7-01: DOMContentLoaded fix ===
# Check that all templates use arrow function wrappers, not bare function refs:
echo "--- S7-01: DOMContentLoaded patterns ---"
grep -n "DOMContentLoaded" src/web/templates/thoughts.html src/web/templates/memories.html src/web/templates/social.html src/web/templates/goals.html
# EXPECTED: All use `() => loadFn()` pattern, not `loadFn` directly

# === S7-02: Working Memory JSONB fix ===
echo "--- S7-02: Working Memory endpoint ---"
curl -s http://localhost:8000/api/working-memory | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Items: {len(d) if isinstance(d,list) else \"obj\"}, Type: {type(d).__name__}')"
# EXPECTED: Items: N, Type: list (no TypeError)

# Check frontend loads:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/working-memory
# EXPECTED: 200

# === S7-03: LiteLLM direct DB ===
echo "--- S7-03: LiteLLM direct DB ---"
curl -s http://localhost:8000/api/litellm/spend | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Keys: {list(d.keys()) if isinstance(d,dict) else len(d)}')"
# EXPECTED: Valid JSON response (not timeout/OOM)

curl -s http://localhost:8000/api/litellm/models | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Models: {len(d) if isinstance(d,list) else list(d.keys())[:5]}')"
# EXPECTED: Model list or model data

# === S7-04: Activity timeline ===
echo "--- S7-04: Activity timeline ---"
curl -s "http://localhost:8000/api/activities?limit=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Type: {type(d).__name__}, Count: {len(d) if isinstance(d,list) else \"obj\"}')"
# EXPECTED: list with activities

# === S7-05: Sprint board ===
echo "--- S7-05: Sprint board ---"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/sprint-board
# EXPECTED: 200

# === Overall dashboard check ===
echo "--- All pages ---"
for page in / goals sprint-board thoughts memories models wallets social knowledge skills performance sessions working-memory services security; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:5000$page")
  echo "$code $page"
done
# EXPECTED: All 200
```

## Prompt for Agent
```
Verify that Sprint 7 changes from yesterday's session are working in production.

**Files to read FIRST (before running any commands):**
- aria_souvenirs/aria_v2_110226/plans/sprint7/ — list all files, read each S7 ticket to understand what was supposed to change
- src/web/templates/thoughts.html (lines 1-30 — check for DOMContentLoaded arrow wrapper)
- src/web/templates/memories.html (lines 1-30 — same check)
- src/web/templates/social.html (lines 1-30 — same check)
- src/web/templates/goals.html (lines 1-30 — same check)
- src/web/templates/working_memory.html (full — check JSONB rendering logic)
- src/api/routers/litellm_proxy.py (lines 1-50 — verify direct DB query exists)
- src/api/routers/activities.py (lines 1-50 — verify server-side aggregation)

**Constraints:** READ-ONLY audit. Do NOT modify any files unless a fix is trivially safe (< 3 lines).

**Steps:**
1. Read ALL S7 ticket files from yesterday's sprint to build a verification checklist
2. S7-01 DOMContentLoaded:
   a. Run: grep -n "DOMContentLoaded" src/web/templates/{thoughts,memories,social,goals}.html
   b. Verify each uses `() => loadFn()` arrow wrapper, NOT bare `loadFn`
   c. EXPECTED: 4 files, all arrow-wrapped
3. S7-02 Working Memory JSONB:
   a. Run: curl -s http://localhost:8000/api/working-memory | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Items: {len(d)}, Type: {type(d).__name__}')"
   b. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/working-memory
   c. EXPECTED: Items: N (Type: list), HTTP 200
4. S7-03 LiteLLM direct DB:
   a. Run: curl -s http://localhost:8000/api/litellm/spend | python3 -m json.tool | head -10
   b. Run: curl -s http://localhost:8000/api/litellm/models | python3 -m json.tool | head -10
   c. EXPECTED: valid JSON (not timeout, not 500)
5. S7-04 Activity timeline:
   a. Run: curl -s "http://localhost:8000/api/activities?limit=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Count: {len(d)}, Keys: {list(d[0].keys()) if d else []}')"
   b. EXPECTED: Count: 5, Keys include 'action', 'created_at'
6. S7-05 Sprint board:
   a. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/sprint-board
   b. Run: grep -n "NULL\|null.*check\|auto.*refresh" src/web/templates/sprint_board.html | head -5
   c. EXPECTED: HTTP 200, null handling present
7. Full page smoke test:
   a. Run: for page in / goals sprint-board thoughts memories models wallets social knowledge skills performance sessions working-memory services security; do curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000$page"; done
   b. EXPECTED: all 200
8. Report results as a table:
   | Ticket | Description | Status | Notes |
   |--------|-------------|--------|-------|
   | S7-01  | DOMContentLoaded | PASS/FAIL | detail |
   ...
```
