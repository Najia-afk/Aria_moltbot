# S2-04: Fix GraphQL update_goal Missing completed_at
**Epic:** E1 — Bug Fixes | **Priority:** P1 | **Points:** 1 | **Phase:** 1

## Problem
`src/api/gql/resolvers.py` in the `resolve_update_goal` function (~line 237-247): when `input.status == "completed"`, the resolver does NOT set `completed_at = NOW()`. The REST endpoint in `src/api/routers/goals.py` line 76 correctly does this. This means goals completed via GraphQL have `completed_at = NULL`.

## Root Cause
The GraphQL resolver was written without the `completed_at` timestamp logic that exists in the REST endpoint. The REST endpoint does:
```python
if data["status"] == "completed":
    from sqlalchemy import text
    values["completed_at"] = text("NOW()")
```
But the GraphQL resolver just sets status without touching completed_at.

## Fix

### File: `src/api/gql/resolvers.py`
In the `resolve_update_goal` function, after setting status, add completed_at logic:

BEFORE:
```python
    values = {}
    if input.status is not None:
        values["status"] = input.status
    if input.progress is not None:
        values["progress"] = input.progress
    if input.priority is not None:
        values["priority"] = input.priority
```
AFTER:
```python
    values = {}
    if input.status is not None:
        values["status"] = input.status
        if input.status == "completed":
            from sqlalchemy import text as sa_text
            values["completed_at"] = sa_text("NOW()")
    if input.progress is not None:
        values["progress"] = input.progress
    if input.priority is not None:
        values["priority"] = input.priority
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Change is in API/GQL layer (correct) |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test via GraphQL playground |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
None — standalone GraphQL fix.

## Verification
```bash
# 1. Verify completed_at logic exists in resolver:
grep -A3 'completed' src/api/gql/resolvers.py | grep -i 'completed_at\|NOW'
# EXPECTED: values["completed_at"] = sa_text("NOW()")

# 2. Test via GraphQL:
curl -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
  -d '{"query":"mutation { updateGoal(goalId: \"test-goal\", input: {status: \"completed\"}) { id completedAt } }"}'
# EXPECTED: completedAt is not null

# 3. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are fixing a missing timestamp in the Aria GraphQL resolver.

FILES TO READ FIRST:
- src/api/gql/resolvers.py (find resolve_update_goal function)
- src/api/routers/goals.py (line 76 — reference implementation with completed_at)

STEPS:
1. Read resolvers.py and find the resolve_update_goal function
2. Add `if input.status == "completed": values["completed_at"] = sa_text("NOW()")` after setting status
3. Import `text as sa_text` from sqlalchemy (use local import like the REST endpoint does)
4. Run verification commands

CONSTRAINTS: API/GQL layer only. Match REST endpoint behavior.
```
