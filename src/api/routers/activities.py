"""
Activity log endpoints — CRUD + activity feed + interactions.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog
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



