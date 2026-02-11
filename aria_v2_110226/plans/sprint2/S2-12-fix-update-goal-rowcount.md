# S2-12: Fix update_goal No Rowcount Check
**Epic:** E1 — Bug Fixes | **Priority:** P2 | **Points:** 1 | **Phase:** 1

## Problem
`src/api/routers/goals.py` in `update_goal` (~line 68-86): After executing the UPDATE statement, it always returns `{"updated": True}` without checking if any row was actually modified. If the `goal_id` doesn't match any record, the API returns 200 with `{"updated": True}` — misleading.

`delete_goal` has a similar issue — it always returns `{"deleted": True}` without checking `result.rowcount`.

## Root Cause
No rowcount check after UPDATE/DELETE operations. The code assumes the goal exists.

## Fix

### File: `src/api/routers/goals.py`

BEFORE (update_goal, ~line 80-86):
```python
    if values:
        try:
            uid = uuid.UUID(goal_id)
            await db.execute(update(Goal).where(Goal.id == uid).values(**values))
        except ValueError:
            await db.execute(update(Goal).where(Goal.goal_id == goal_id).values(**values))
        await db.commit()
    return {"updated": True}
```
AFTER:
```python
    if values:
        try:
            uid = uuid.UUID(goal_id)
            result = await db.execute(update(Goal).where(Goal.id == uid).values(**values))
        except ValueError:
            result = await db.execute(update(Goal).where(Goal.goal_id == goal_id).values(**values))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
        await db.commit()
    return {"updated": True}
```

BEFORE (delete_goal, ~line 59-64):
```python
    try:
        uid = uuid.UUID(goal_id)
        await db.execute(delete(Goal).where(Goal.id == uid))
    except ValueError:
        await db.execute(delete(Goal).where(Goal.goal_id == goal_id))
    await db.commit()
    return {"deleted": True}
```
AFTER:
```python
    try:
        uid = uuid.UUID(goal_id)
        result = await db.execute(delete(Goal).where(Goal.id == uid))
    except ValueError:
        result = await db.execute(delete(Goal).where(Goal.goal_id == goal_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    await db.commit()
    return {"deleted": True}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | API layer change |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first | ✅ | Test via curl |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
None — standalone fix.

## Verification
```bash
# 1. Verify rowcount check exists:
grep -n 'rowcount' src/api/routers/goals.py
# EXPECTED: 2 lines with rowcount == 0

# 2. Test update with non-existent goal:
curl -s -o /dev/null -w "%{http_code}" -X PATCH http://localhost:8000/api/goals/nonexistent-goal-id -H 'Content-Type: application/json' -d '{"status":"completed"}'
# EXPECTED: 404

# 3. Test delete with non-existent goal:
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/goals/nonexistent-goal-id
# EXPECTED: 404

# 4. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are fixing missing rowcount checks in the Aria goals API.

FILES TO READ FIRST:
- src/api/routers/goals.py (update_goal and delete_goal functions)

STEPS:
1. Read goals.py
2. In update_goal: capture result of db.execute(), check result.rowcount == 0, raise 404
3. In delete_goal: same — capture result, check rowcount, raise 404
4. Run verification commands

CONSTRAINTS: API layer only. Use HTTPException for 404.
```
