# S-09: Swarm Recap UI
**Epic:** E5 — Swarm Recap | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Roundtable has a rich synthesis view rendered in `engine_roundtable.html` at L841, L959, L1090, showing:
- Agent contributions
- Consensus/dissent breakdown
- Synthesis text
- Per-agent assessment

Swarm uses the same `engine_roundtable.html` template (toggled at L424) but has **no dedicated recap view**. After a swarm execution, there is no way to see:
- Which agents participated
- Token usage per agent
- Task allocation breakdown
- Convergence metrics
- Final merged output

Aria's bug report: "there is no nice recap UI for swarm like we have for round table"

## Root Cause
Swarm was added as a mode toggle within the roundtable UI. It reuses the same template but the synthesis sections (L841, L959, L1090) only render roundtable-style consensus. Swarm has different semantics (parallel task execution vs deliberation) that need different visualization.

## Fix

### Fix 1: Create swarm recap template
**File:** `src/web/templates/engine_swarm_recap.html` (NEW)

**Layout:**
```
┌─────────────────────────────────────────┐
│ Swarm Execution Recap                   │
│ Session: {id} | Started: {ts} | {status}│
├────────────┬────────────────────────────┤
│ Task Map   │ Agent Participation        │
│ ┌────────┐ │ ┌──────────┬─────┬──────┐  │
│ │ task 1 │ │ │ Agent    │ Tkn │ Time │  │
│ │ task 2 │ │ │ analyst  │ 2.3k│ 4.2s │  │
│ │ task 3 │ │ │ coder    │ 1.8k│ 3.1s │  │
│ └────────┘ │ │ reviewer │ 0.9k│ 2.0s │  │
│            │ └──────────┴─────┴──────┘  │
├────────────┴────────────────────────────┤
│ Merged Output                           │
│ {final_synthesis}                       │
├─────────────────────────────────────────┤
│ Per-Agent Results (collapsible)         │
│  ► analyst: {output}                    │
│  ► coder: {output}                      │
│  ► reviewer: {output}                   │
└─────────────────────────────────────────┘
```

### Fix 2: Add swarm recap route
**File:** `src/web/app.py`
```python
@app.route('/engine/swarm/<session_id>/recap')
def engine_swarm_recap(session_id):
    # Fetch swarm session data via API proxy
    data = api_proxy(f'/engine/swarm/{session_id}')
    return render_template('engine_swarm_recap.html', session=data)
```

### Fix 3: Add API endpoint for swarm recap data
**File:** `src/api/` — add endpoint:
```
GET /engine/swarm/{session_id}/recap
```
Returns:
```json
{
  "session_id": "...",
  "status": "completed",
  "started_at": "...",
  "completed_at": "...",
  "agents": [
    {"name": "analyst", "model": "kimi", "tokens_used": 2300, "duration_ms": 4200, "output": "..."}
  ],
  "tasks": [
    {"id": 1, "description": "...", "assigned_to": "analyst", "status": "done"}
  ],
  "merged_output": "...",
  "total_tokens": 5000,
  "total_duration_ms": 9300
}
```

### Fix 4: Link from swarm list to recap
**File:** `src/web/templates/engine_roundtable.html` — in the swarm execution list, add a "View Recap" link for completed swarm sessions.

### Fix 5: Add to Agents nav
This page will be discoverable from the Agents nav (S-06) under Swarm, and from individual swarm session links.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | New API endpoint → skill → DB query |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

**Pagination:** If swarm has many historical sessions, the list must be paginated. The recap is for a single session so no pagination needed there.

## Dependencies
- S-06 (Agents nav) — for nav placement
- Requires understanding of `aria_engine/swarm.py` L139 `execute()` return format

## Verification
```bash
# 1. Verify template exists:
test -f src/web/templates/engine_swarm_recap.html && echo "OK"

# 2. Verify route exists:
grep 'swarm.*recap' src/web/app.py
# EXPECTED: route definition

# 3. Verify API endpoint:
curl -s http://localhost:8000/engine/swarm/test-session/recap
# EXPECTED: JSON response (even if 404 for test ID)

# 4. Verify roundtable template has "View Recap" link:
grep -i 'recap' src/web/templates/engine_roundtable.html
# EXPECTED: Link to /engine/swarm/{id}/recap

# 5. Manual: Run a swarm, click "View Recap", verify layout matches spec
```

## Prompt for Agent
```
Read these files FIRST:
- aria_engine/swarm.py (full — understand execute() and what data is available)
- aria_engine/roundtable.py (full — understand discuss() for comparison)
- src/web/templates/engine_roundtable.html (L800-L1100 — existing synthesis sections)
- src/web/app.py (find roundtable/swarm routes)
- src/api/ — find existing roundtable/swarm API endpoints

CONSTRAINTS: #1 (5-layer for new API endpoint), pagination on swarm session lists.

STEPS:
1. Understand swarm.py execute() return format — what data is stored and returned
2. Create new API endpoint GET /engine/swarm/{session_id}/recap (follow existing roundtable pattern)
3. Create engine_swarm_recap.html template with the layout shown above
4. Use same CSS/Bootstrap patterns as engine_roundtable.html
5. Add route to app.py with API proxy call
6. Add "View Recap" link in engine_roundtable.html swarm section for completed sessions
7. Handle missing/in-progress sessions gracefully (loading spinner, "in progress" badge)
8. Add token usage breakdown chart (simple bar chart using existing chart library)
9. Run verification commands
```
