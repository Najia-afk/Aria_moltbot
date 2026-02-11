"""
Goals + hourly goals endpoints.
"""

import uuid
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
