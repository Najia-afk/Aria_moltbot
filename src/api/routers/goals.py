"""
Goals + hourly goals endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Goal, HourlyGoal
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Goals"])


# ── Goals ────────────────────────────────────────────────────────────────────

@router.get("/goals")
async def list_goals(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc())
    if status:
        base = base.where(Goal.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    result = await db.execute(stmt)
    items = [g.to_dict() for g in result.scalars().all()]

    return build_paginated_response(items, total, page, limit)


@router.post("/goals")
async def create_goal(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    new_id = uuid.uuid4()
    goal = Goal(
        id=new_id,
        goal_id=data.get("goal_id", f"goal-{str(new_id)[:8]}"),
        title=data.get("title"),
        description=data.get("description", ""),
        status=data.get("status", "pending"),
        progress=data.get("progress", 0),
        priority=data.get("priority", 2),
        due_date=data.get("due_date") or data.get("target_date"),
        sprint=data.get("sprint", "backlog"),
        board_column=data.get("board_column", "backlog"),
        position=data.get("position", 0),
        assigned_to=data.get("assigned_to"),
        tags=data.get("tags", []),
    )
    db.add(goal)
    await db.commit()
    return {"id": str(goal.id), "goal_id": goal.goal_id, "created": True}


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = uuid.UUID(goal_id)
        result = await db.execute(delete(Goal).where(Goal.id == uid))
    except ValueError:
        result = await db.execute(delete(Goal).where(Goal.goal_id == goal_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    await db.commit()
    return {"deleted": True}


@router.patch("/goals/{goal_id}")
async def update_goal(
    goal_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    values: dict = {}
    if data.get("status") is not None:
        values["status"] = data["status"]
        if data["status"] == "completed":
            from sqlalchemy import text
            values["completed_at"] = text("NOW()")
    if data.get("progress") is not None:
        values["progress"] = data["progress"]
    if data.get("priority") is not None:
        values["priority"] = data["priority"]
    # Sprint board fields (S3-01)
    for field in ("sprint", "board_column", "position", "assigned_to", "tags", "title", "description", "due_date"):
        if data.get(field) is not None:
            values[field] = data[field]

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


# ── Sprint Board (S3-02) ────────────────────────────────────────────────────

@router.get("/goals/board")
async def goal_board(
    sprint: str = "current",
    db: AsyncSession = Depends(get_db),
):
    """Get goals organized by board column for Kanban view."""
    from datetime import timedelta, timezone as tz

    # If "current" sprint, get the latest sprint name or default to "sprint-1"
    if sprint == "current":
        latest = await db.execute(
            select(Goal.sprint).where(Goal.sprint != "backlog")
            .order_by(Goal.created_at.desc()).limit(1)
        )
        sprint = latest.scalar() or "sprint-1"

    from sqlalchemy import or_

    # Fetch all goals for this sprint + backlog + NULL sprint
    stmt = select(Goal).where(
        or_(
            Goal.sprint.in_([sprint, "backlog"]),
            Goal.sprint.is_(None),
        )
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
    base = select(Goal).where(
        Goal.status.in_(["completed", "cancelled"])
    ).order_by(Goal.completed_at.desc().nulls_last())

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

    column_to_status = {
        "backlog": "pending",
        "todo": "pending",
        "doing": "active",
        "on_hold": "paused",
        "done": "completed",
    }

    # Validate board_column
    if not new_column or new_column not in column_to_status:
        raise HTTPException(
            status_code=400,
            detail=f"board_column is required and must be one of: {list(column_to_status.keys())}",
        )

    values = {
        "board_column": new_column,
        "position": new_position,
    }

    new_status = column_to_status[new_column]
    values["status"] = new_status
    if new_status == "completed":
        values["completed_at"] = datetime.now()
    elif new_column != "done":
        # Clear completed_at when moving away from done
        values["completed_at"] = None

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
    """Lightweight sprint summary — optimized for Aria's token budget (~200 tokens)."""
    stmt = select(
        Goal.status,
        func.count(Goal.id).label("count"),
    ).group_by(Goal.status)

    result = await db.execute(stmt)
    status_counts = {row.status: row.count for row in result.all()}

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
        "summary": f"{status_counts.get('active', 0)} active, {status_counts.get('pending', 0)} pending, {status_counts.get('completed', 0)} done",
    }


@router.get("/goals/history")
async def goal_history(
    days: int = 14,
    db: AsyncSession = Depends(get_db),
):
    """Get goal status distribution by day for stacked chart."""
    from sqlalchemy import cast, Date
    from datetime import timedelta, timezone as tz

    since = datetime.now(tz.utc) - timedelta(days=days)

    stmt = select(
        cast(Goal.created_at, Date).label("day"),
        Goal.status,
        func.count(Goal.id).label("count"),
    ).where(
        Goal.created_at >= since
    ).group_by("day", Goal.status).order_by("day")

    result = await db.execute(stmt)
    rows = result.all()

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


# ── Hourly goals ─────────────────────────────────────────────────────────────

@router.get("/hourly-goals")
async def get_hourly_goals(
    status: Optional[str] = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(HourlyGoal).order_by(HourlyGoal.hour_slot, HourlyGoal.created_at.desc())
    if status:
        stmt = stmt.where(HourlyGoal.status == status)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"goals": [g.to_dict() for g in rows], "count": len(rows)}


@router.post("/hourly-goals")
async def create_hourly_goal(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    goal = HourlyGoal(
        hour_slot=data.get("hour_slot"),
        goal_type=data.get("goal_type"),
        description=data.get("description"),
        status=data.get("status", "pending"),
    )
    db.add(goal)
    await db.commit()
    return {"created": True}


@router.patch("/hourly-goals/{goal_id}")
async def update_hourly_goal(
    goal_id: int, request: Request, db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    status = data.get("status")
    values: dict = {"status": status}
    if status == "completed":
        from sqlalchemy import text
        values["completed_at"] = text("NOW()")
    await db.execute(update(HourlyGoal).where(HourlyGoal.id == goal_id).values(**values))
    await db.commit()
    return {"updated": True}
