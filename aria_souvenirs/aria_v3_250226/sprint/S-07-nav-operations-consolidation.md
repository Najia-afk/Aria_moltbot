# S-07: Regroup Navigation — Operations Consolidation
**Epic:** E3 — Nav Regrouping | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
After S-05 and S-06 extract Memory, Intelligence, Agents, and Skills into their own sections, Operations needs a final cleanup pass. Currently 8 items:
- Cron Jobs, Agents, Skills, Roundtable, Swarm, Heartbeat, Exports, Security

After S-05/S-06 extract agents + skills, and with Security already having its own nav section, Operations should be a lean system-ops section.

Additionally, 3 orphaned "operations hub" sub-routes exist that aren't in nav:
- `/operations/scheduler/`
- `/operations/hub/` (or similar)

These need to be evaluated: include in nav or remove.

## Root Cause
Operations became a dumping ground. With proper section extraction in S-05/S-06, it needs a cleanup pass.

## Fix

### Fix 1: Final Operations nav structure
**File:** `src/web/templates/base.html`
**Operations dropdown — final state:**
| Label | Route | Notes |
|-------|-------|-------|
| Cron Jobs | `/operations/cron/` | Keep — core ops |
| Scheduler | `/operations/scheduler/` | Promote from orphan — scheduling is ops |
| Heartbeat | `/heartbeat` | Keep — system health |
| Exports | `/exports` | Keep — data ops |
| Goals | `/goals` | Moved from Intelligence (S-05) |

### Fix 2: Remove Security from Operations if separate section exists
Verify Security already has its own nav section (it does — 2 items). Ensure no duplication.

### Fix 3: Evaluate orphan operations routes
**File:** `src/web/app.py` — check these routes:
- `/operations/scheduler/` — if functional, add to nav
- `/operations/hub/` — if functional, add to nav; if empty, remove
- Any `/operations/*` route not linked from nav

### Fix 4: Clean nav order
Final nav bar order (left to right):
1. Home
2. Overview (Dashboard, Sessions, Creative Pulse)
3. Memory (6 items — from S-05)
4. Intelligence (6 items — from S-05)
5. Agents (4 items — from S-06)
6. Skills (2-3 items — from S-06)
7. Models (3 items — remove rate_limits link per S-04)
8. Operations (5 items — this ticket)
9. Security (2 items — existing)
10. Identity (existing)
11. Social (existing)
12. RPG (existing)

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend only |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- **Requires:** S-05, S-06 (this is the cleanup pass after extraction)
- S-04 (rate limits removal from nav)

## Verification
```bash
# 1. Count nav dropdowns:
grep -c 'nav-item dropdown' src/web/templates/base.html
# EXPECTED: ~12 (Home + 11 sections)

# 2. Verify Operations has 5 items:
# Manual: Check dropdown

# 3. Verify no orphan routes unlinked:
# Extract all routes from app.py, compare with all hrefs in base.html
python -c "
import re
with open('src/web/app.py') as f:
    routes = set(re.findall(r\"@app\.route\('([^']+)'\)\", f.read()))
with open('src/web/templates/base.html') as f:
    links = set(re.findall(r'href=\"([^\"]+)\"', f.read()))
orphans = routes - links - {'/api/proxy', '/health'}  # exclude API routes
print('Orphan routes:', orphans)
"
# EXPECTED: Empty or intentional API-only routes
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/base.html (full nav section, output of S-05 and S-06)
- src/web/app.py (full — all routes)

CONSTRAINTS: This ticket MUST run AFTER S-05 and S-06 are merged.

STEPS:
1. Read the nav as modified by S-05 and S-06
2. Verify Operations no longer has agents/skills/roundtable/swarm
3. Check orphan /operations/* routes — evaluate if they should be in nav
4. Add /operations/scheduler/ to Operations nav if functional
5. Move /goals to Operations (if S-05 didn't already)
6. Remove Security items from Operations if already in separate Security section
7. Verify final nav order matches the spec above
8. Run the orphan-route detection script
9. Run verification commands
```
