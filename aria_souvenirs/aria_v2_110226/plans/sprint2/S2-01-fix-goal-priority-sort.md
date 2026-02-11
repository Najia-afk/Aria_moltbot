# S2-01: Fix Goal Priority Sort Inversion
**Epic:** E1 — Bug Fixes | **Priority:** P0 | **Points:** 1 | **Phase:** 1

## Problem
`src/api/routers/goals.py` line 30 sorts goals by `Goal.priority.desc()`. Since priority 1 = urgent and priority 5 = background, this shows background goals first. The GraphQL resolver in `src/api/gql/resolvers.py` line ~111 has the same bug: `Goal.priority.desc()`.

## Root Cause
Both the REST endpoint `list_goals()` and GraphQL resolver `resolve_goals()` use `.desc()` ordering on `Goal.priority`. The intent is P1 (urgent) goals first, but `.desc()` puts P5 first. Should be `.asc()` for priority (lower number = higher priority) while keeping `.desc()` for `created_at` (newest first within same priority).

## Fix

### File: `src/api/routers/goals.py`
**Line 30**
BEFORE:
```python
    stmt = select(Goal).order_by(Goal.priority.desc(), Goal.created_at.desc()).limit(limit)
```
AFTER:
```python
    stmt = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc()).limit(limit)
```

### File: `src/api/gql/resolvers.py`
Find the `resolve_goals` function where it has `Goal.priority.desc()`:
BEFORE:
```python
    stmt = select(Goal).order_by(Goal.priority.desc(), Goal.created_at.desc()).limit(limit)
```
AFTER:
```python
    stmt = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc()).limit(limit)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Change is in API layer (correct) |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via `docker compose exec aria-api pytest` |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone bug fix.

## Verification
```bash
# 1. Verify REST sort order changed:
grep -n "priority\." src/api/routers/goals.py
# EXPECTED: line 30: .order_by(Goal.priority.asc(), Goal.created_at.desc())

# 2. Verify GraphQL sort order changed:
grep -n "priority\." src/api/gql/resolvers.py
# EXPECTED: .order_by(Goal.priority.asc(), Goal.created_at.desc())

# 3. Test API returns P1 goals first:
curl -s http://localhost:8000/api/goals?limit=5 | python3 -c "import sys,json; goals=json.load(sys.stdin); print([g['priority'] for g in goals])"
# EXPECTED: [1, 1, 2, 2, 3, ...] (ascending priority order)

# 4. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are fixing a priority sort bug in the Aria project.

FILES TO READ FIRST:
- src/api/routers/goals.py (line 30 — the .desc() on priority)
- src/api/gql/resolvers.py (find resolve_goals function — same .desc() bug)

STEPS:
1. Read both files to find the exact lines
2. Change Goal.priority.desc() to Goal.priority.asc() in both files
3. Keep Goal.created_at.desc() unchanged (newest first within same priority)
4. Run verification commands

CONSTRAINTS: Layer 1 (API) changes only. No secrets. No model names.
```
