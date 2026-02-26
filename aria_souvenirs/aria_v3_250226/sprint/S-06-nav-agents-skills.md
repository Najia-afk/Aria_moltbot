# S-06: Regroup Navigation — Agents & Skills
**Epic:** E3 — Nav Regrouping | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
Agent and Skill pages are scattered across multiple nav sections:
- **Operations** has: Agents, Skills, Roundtable, Swarm (4 of 8 items)
- There is a `/agents` route AND `/operations/agents/` route (different templates!)
- Skills are buried inside Operations but are a first-class concept in Aria's architecture

The user said: "we need to regroup html for agents / skills / focus"

## Root Cause
Agents/skills/roundtable were added to Operations as a catch-all. They deserve their own top-level nav sections.

## Fix

### Fix 1: Create "Agents" nav group
**File:** `src/web/templates/base.html`
**New "Agents" dropdown:**
| Label | Route | Notes |
|-------|-------|-------|
| Agent Pool | `/agents` | Main agent listing |
| Roundtable | `/engine/roundtable` | Multi-agent discussion |
| Swarm | `/engine/swarm` | Swarm execution (after S-09 adds recap) |
| Delegation | `/engine/delegation` | NEW — after S-10/S-11 |

### Fix 2: Create "Skills" nav group
**File:** `src/web/templates/base.html`
**New "Skills" dropdown:**
| Label | Route | Notes |
|-------|-------|-------|
| Skill Catalog | `/skills` | Main skill listing |
| Pipelines | `/skills/pipelines` | If exists, or future |
| Health Dashboard | `/skills/health` | If exists via skill_health_dashboard.py |

### Fix 3: Remove agent/skill items from Operations
**File:** `src/web/templates/base.html`
Remove from Operations dropdown: Agents, Skills, Roundtable, Swarm
**Operations reduced to:**
| Label | Route |
|-------|-------|
| Cron Jobs | `/operations/cron/` |
| Heartbeat | `/heartbeat` |
| Goals | `/goals` (moved from Intelligence in S-05) |
| Exports | `/exports` |

### Fix 4: Resolve /agents vs /operations/agents/ duplication
**File:** `src/web/app.py`
- Check what template each route uses
- If `/operations/agents/` is the older page, add 301 redirect: `/operations/agents/` → `/agents`
- If they show different data, keep both but clarify naming

### Fix 5: Resolve /skills vs duplicate routes
Similar analysis for any skill route duplication.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Frontend nav only |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- S-05 (Memory/Intelligence regrouping) should be done first
- S-09 (Swarm recap) should come before or with this

## Verification
```bash
# 1. Verify Agents dropdown exists:
grep 'Agents' src/web/templates/base.html | head -5
# EXPECTED: Agents dropdown label + 3-4 items

# 2. Verify Skills dropdown exists:
grep 'Skills' src/web/templates/base.html | head -5
# EXPECTED: Skills dropdown label + 2-3 items

# 3. Verify Operations is slimmed:
# Manual: Check Operations dropdown has ≤ 4 items

# 4. Verify no duplication:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/operations/agents/
# EXPECTED: 301 redirect or 404 (not 200 with different page)
```

## Prompt for Agent
```
Read these files FIRST:
- src/web/templates/base.html (L100-L300 — full nav)
- src/web/app.py (find ALL agent, skill, roundtable, swarm routes)
- src/web/templates/engine_agents.html (if exists)
- src/web/templates/agents.html (if exists)
- src/web/templates/skills.html (if exists)

CONSTRAINTS: Frontend nav restructuring. Resolve route duplication with 301 redirects.

STEPS:
1. Map ALL agent-related routes and their templates
2. Map ALL skill-related routes and their templates
3. Decide which route is canonical for agents (probably /agents)
4. Add 301 redirects for duplicate routes
5. Create "Agents" nav dropdown in base.html (Agent Pool, Roundtable, Swarm, Delegation placeholder)
6. Create "Skills" nav dropdown in base.html (Skill Catalog, + health if exists)
7. Remove agent/skill items from Operations dropdown
8. Keep Operations lean: Cron, Heartbeat, Goals, Exports
9. Follow same HTML pattern as other nav dropdowns
10. Run verification commands
```
