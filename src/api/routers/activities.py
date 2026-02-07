"""
Activity log endpoints — CRUD + activity feed + interactions.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog, Thought, Goal
from deps import get_db

router = APIRouter(tags=["Activities"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_description(details) -> str:
    if isinstance(details, dict):
        return details.get("message") or details.get("description") or str(details)
    return str(details) if details else ""


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/activities")
async def api_activities(limit: int = 25, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ActivityLog)
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "type": a.action,
            "description": _extract_description(a.details),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]


@router.post("/activities")
async def create_activity(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    activity = ActivityLog(
        id=uuid.uuid4(),
        action=data.get("action"),
        skill=data.get("skill"),
        details=data.get("details", {}),
        success=data.get("success", True),
        error_message=data.get("error_message"),
    )
    db.add(activity)
    await db.commit()
    return {"id": str(activity.id), "created": True}


@router.get("/interactions")
async def list_interactions(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return [a.to_dict() for a in result.scalars().all()]


@router.get("/activity")
async def get_activity_feed(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Recent activity across all types."""
    activities = []

    logs = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(3)
    )
    for a in logs.scalars().all():
        msg = a.action + (f": {a.skill}" if a.skill else "")
        activities.append({"type": "activity", "message": msg, "created_at": a.created_at})

    thoughts = await db.execute(
        select(Thought).order_by(Thought.created_at.desc()).limit(3)
    )
    for t in thoughts.scalars().all():
        activities.append({"type": "thought", "message": t.content, "created_at": t.created_at})

    goals = await db.execute(
        select(Goal).order_by(Goal.created_at.desc()).limit(3)
    )
    for g in goals.scalars().all():
        activities.append({"type": "goal", "message": g.title, "created_at": g.created_at})

    activities.sort(key=lambda x: x["created_at"] or "", reverse=True)
    # Serialize datetimes
    for item in activities:
        if item["created_at"]:
            item["created_at"] = item["created_at"].isoformat()
    return activities[:limit]
