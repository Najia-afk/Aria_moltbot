# S3-02: Create Sprint Board API Endpoints
**Epic:** E5 — Sprint Board | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
No API endpoints exist for sprint board operations:
- No board view endpoint (goals grouped by column)
- No move endpoint (change column/position)
- No sprint summary (for Aria's lightweight status check)
- No history/timeline endpoint (for stacked chart data)

## Root Cause
Sprint board is a new feature — these endpoints don't exist yet.

## Fix

### File: `src/api/routers/goals.py`
Add new endpoints:

```python
# ── Sprint Board ─────────────────────────────────────────────────────────

@router.get("/goals/board")
async def goal_board(
    sprint: str = "current",
    db: AsyncSession = Depends(get_db),
):
    """Get goals organized by board column for Kanban view."""
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta, timezone
    
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    
    # If "current" sprint, get the latest sprint name or default to "backlog"
    if sprint == "current":
        latest = await db.execute(
            select(Goal.sprint).where(Goal.sprint != "backlog")
            .order_by(Goal.created_at.desc()).limit(1)
        )
        sprint = latest.scalar() or "sprint-1"
    
    # Fetch all goals for this sprint + backlog
    stmt = select(Goal).where(
        Goal.sprint.in_([sprint, "backlog"])
    ).order_by(Goal.position.asc(), Goal.priority.asc())
    result = await db.execute(stmt)
    goals = result.scalars().all()
    
    columns = {
        "backlog": [],
        "todo": [],
        "doing": [],
        "on_hold": [],
        "done": [],
    }
    
    for g in goals:
        d = g.to_dict()
        col = g.board_column or "backlog"
        # Map legacy statuses to board columns
        if col == "backlog" and g.status == "pending":
            col = "backlog"
        elif g.status == "active" and (g.progress or 0) == 0:
            col = "todo"
        elif g.status == "active" and (g.progress or 0) > 0:
            col = "doing"
        elif g.status == "paused":
            col = "on_hold"
        elif g.status == "completed":
            # Only show in Done if completed in last 24h
            if g.completed_at and g.completed_at > day_ago:
                col = "done"
            else:
                continue  # Skip old completed — they go to archive
        elif g.status == "cancelled":
            continue  # Skip cancelled — goes to archive
        
        if col in columns:
            columns[col].append(d)
    
    return {
        "sprint": sprint,
        "columns": columns,
        "counts": {k: len(v) for k, v in columns.items()},
        "total": sum(len(v) for v in columns.values()),
    }


@router.get("/goals/archive")
async def goal_archive(
    page: int = 1,
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """Get completed and cancelled goals for archive view."""
    from sqlalchemy import func
    from pagination import paginate_query, build_paginated_response
    
    base = select(Goal).where(
        Goal.status.in_(["completed", "cancelled"])
    ).order_by(Goal.completed_at.asc())
    
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    
    stmt, _ = paginate_query(base, page, limit)
    result = await db.execute(stmt)
    items = [g.to_dict() for g in result.scalars().all()]
    
    return build_paginated_response(items, total, page, limit)


@router.patch("/goals/{goal_id}/move")
async def move_goal(
    goal_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Move goal to new board column (for drag-and-drop)."""
    data = await request.json()
    new_column = data.get("board_column")
    new_position = data.get("position", 0)
    
    # Map column to status
    column_to_status = {
        "backlog": "pending",
        "todo": "pending",
        "doing": "active",
        "on_hold": "paused",
        "done": "completed",
    }
    
    values = {
        "board_column": new_column,
        "position": new_position,
    }
    
    new_status = column_to_status.get(new_column)
    if new_status:
        values["status"] = new_status
        if new_status == "completed":
            from sqlalchemy import text as sa_text
            values["completed_at"] = sa_text("NOW()")
    
    try:
        uid = uuid.UUID(goal_id)
        result = await db.execute(update(Goal).where(Goal.id == uid).values(**values))
    except ValueError:
        result = await db.execute(update(Goal).where(Goal.goal_id == goal_id).values(**values))
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    
    await db.commit()
    return {"moved": True, "board_column": new_column, "position": new_position}


@router.get("/goals/sprint-summary")
async def goal_sprint_summary(
    sprint: str = "current",
    db: AsyncSession = Depends(get_db),
):
    """Lightweight sprint summary — optimized for Aria's token budget.
    
    Returns a compact summary that costs ~200 tokens instead of ~2000.
    """
    from sqlalchemy import func
    
    stmt = select(
        Goal.status,
        func.count(Goal.id).label("count"),
    ).group_by(Goal.status)
    
    result = await db.execute(stmt)
    status_counts = {row.status: row.count for row in result.all()}
    
    # Get top 3 active goals (most important for Aria to focus on)
    active = await db.execute(
        select(Goal.goal_id, Goal.title, Goal.priority, Goal.progress)
        .where(Goal.status == "active")
        .order_by(Goal.priority.asc(), Goal.progress.desc())
        .limit(3)
    )
    top_goals = [
        {"id": r.goal_id, "title": r.title, "priority": r.priority, "progress": float(r.progress or 0)}
        for r in active.all()
    ]
    
    return {
        "sprint": sprint,
        "status_counts": status_counts,
        "total": sum(status_counts.values()),
        "top_active": top_goals,
        "summary": f"{status_counts.get('active', 0)} active, {status_counts.get('pending', 0)} pending, {status_counts.get('completed', 0)} done"
    }


@router.get("/goals/history")
async def goal_history(
    days: int = 14,
    db: AsyncSession = Depends(get_db),
):
    """Get goal status distribution by day for stacked chart."""
    from sqlalchemy import func, cast, Date
    from datetime import datetime, timedelta, timezone
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Count goals by status and creation date
    stmt = select(
        cast(Goal.created_at, Date).label("day"),
        Goal.status,
        func.count(Goal.id).label("count"),
    ).where(
        Goal.created_at >= since
    ).group_by("day", Goal.status).order_by("day")
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # Build per-day data
    data = {}
    for row in rows:
        day = str(row.day)
        if day not in data:
            data[day] = {"pending": 0, "active": 0, "completed": 0, "paused": 0, "cancelled": 0}
        data[day][row.status] = row.count
    
    return {
        "days": days,
        "data": data,
        "labels": sorted(data.keys()),
    }
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API layer (correct) |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model names |
| 4 | Docker-first testing | ✅ | Test locally |
| 5 | aria_memories only writable path | ❌ | DB reads/writes |
| 6 | No soul modification | ❌ | No soul files |

## Dependencies
- **S3-01 must complete first** — uses sprint, board_column, position fields.
- **S2-06** (pagination) — archive endpoint uses pagination helpers.

## Verification
```bash
# 1. Board endpoint works:
curl -s http://localhost:8000/api/goals/board | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'Sprint: {d[\"sprint\"]}, Columns: {list(d[\"columns\"].keys())}')
print(f'Counts: {d[\"counts\"]}')
"
# EXPECTED: Sprint: sprint-1, Columns: [backlog, todo, doing, on_hold, done]

# 2. Archive endpoint works:
curl -s 'http://localhost:8000/api/goals/archive?page=1&limit=5' | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Archive: {d[\"total\"]} items')
"

# 3. Sprint summary is compact:
curl -s http://localhost:8000/api/goals/sprint-summary | python3 -c "
import sys,json; d=json.load(sys.stdin); print(d['summary'])
"
# EXPECTED: e.g. "3 active, 5 pending, 2 done"

# 4. History data for chart:
curl -s http://localhost:8000/api/goals/history?days=7 | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Days in history: {len(d[\"labels\"])}')
"

# 5. Move endpoint works:
curl -s -X PATCH http://localhost:8000/api/goals/test-goal/move \
  -H 'Content-Type: application/json' -d '{"board_column":"doing","position":1}'
# EXPECTED: {"moved": true, "board_column": "doing", "position": 1}
```

## Prompt for Agent
```
You are creating sprint board API endpoints for the Aria project.

FILES TO READ FIRST:
- src/api/routers/goals.py (existing goal endpoints)
- src/api/db/models.py (Goal model with new sprint fields from S3-01)
- src/api/pagination.py (created in S2-06)
- src/api/deps.py (get_db dependency)

STEPS:
1. Read goals.py to understand existing structure
2. Add 5 new endpoints: /goals/board, /goals/archive, /goals/{id}/move, /goals/sprint-summary, /goals/history
3. Use pagination for archive endpoint
4. sprint-summary should be token-efficient (~200 tokens)
5. history should return daily status distribution for Chart.js
6. Run verification commands

CONSTRAINTS: API layer only. No secrets. Use pagination for list endpoints.
IMPORTANT: /goals/board and /goals/sprint-summary should be GET endpoints returning minimal data for Aria's context window efficiency.
```
