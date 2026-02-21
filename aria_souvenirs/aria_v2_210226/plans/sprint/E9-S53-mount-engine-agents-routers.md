# S-53: Mount Engine Agents + Metrics Routers
**Epic:** E9 — Database Integration | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem

Two API routers exist but are **not mounted** in `src/api/main.py`:

1. `src/api/routers/engine_agents.py` (69 lines) — `/api/engine/agents` endpoints
   - `GET /api/engine/agents` — list all agents with status
   - `GET /api/engine/agents/{id}` — single agent detail

2. `src/api/routers/engine_agent_metrics.py` (314 lines) — `/api/engine/agents/metrics` endpoints
   - `GET /api/engine/agents/metrics` — all agents with current stats
   - `GET /api/engine/agents/metrics/{agent_id}` — single agent detail
   - `GET /api/engine/agents/metrics/{agent_id}/history` — score history

The web UI has pages for these:
- `/agents` → `engine_agents.html`
- `/agent-dashboard` → `engine_agent_dashboard.html`

But they return 404 for all API calls because the routers aren't active.

## Root Cause

`src/api/main.py` lines 240-263 import 24 routers. The `engine_agents` and
`engine_agent_metrics` routers are NOT in the import list. They were created
(Sprint 4 tickets) but never added to the main app.

## Fix

**File:** `src/api/main.py`

### Change 1: Import the routers (after line 263)

BEFORE:
```python
from routers.engine_sessions import router as engine_sessions_router
```

AFTER:
```python
from routers.engine_sessions import router as engine_sessions_router
from routers.engine_agents import router as engine_agents_router
from routers.engine_agent_metrics import router as engine_agent_metrics_router
```

### Change 2: Mount the routers (after line 292)

BEFORE:
```python
app.include_router(engine_sessions_router)
```

AFTER:
```python
app.include_router(engine_sessions_router)
app.include_router(engine_agents_router)
app.include_router(engine_agent_metrics_router)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Adding API layer routes — correct layer |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model name references |
| 4 | Docker-first testing | ✅ | Must verify via Docker Compose |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- None — can be executed independently.
- S-57 benefits from this (agent pages get working APIs).

## Verification
```bash
# 1. Routers imported:
grep -n "engine_agents" src/api/main.py
# EXPECTED: import lines for both engine_agents and engine_agent_metrics

# 2. No import errors:
cd src/api && python -c "from main import app; print('OK')"
# EXPECTED: OK

# 3. Routes registered:
cd src/api && python -c "
from main import app
for r in app.routes:
    p = getattr(r, 'path', '')
    if 'engine/agents' in p:
        print(p)
" 
# EXPECTED: /api/engine/agents, /api/engine/agents/{agent_id}, /api/engine/agents/metrics, etc.

# 4. Agents endpoint responds:
curl -s http://localhost:8000/api/engine/agents | python -m json.tool
# EXPECTED: JSON array (possibly empty, but 200 status)
```

## Prompt for Agent
Read these files first:
- `src/api/main.py` (all 296 lines)
- `src/api/routers/engine_agents.py` (all 69 lines)
- `src/api/routers/engine_agent_metrics.py` (first 30 lines)

Steps:
1. Add import for `engine_agents` router after the `engine_sessions` import in main.py
2. Add import for `engine_agent_metrics` router after that
3. Add `app.include_router()` calls for both after the engine_sessions mount
4. Run verification commands

Constraints: #1 (API layer), #4 (Docker test)
