"""
Activity log endpoints — CRUD + activity feed + interactions.
"""

import json as json_lib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Activities"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_description(details) -> str:
    if isinstance(details, dict):
        return details.get("message") or details.get("description") or str(details)
    return str(details) if details else ""


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/activities")
async def api_activities(page: int = 1, limit: int = 50, db: AsyncSession = Depends(get_db)):
    base = select(ActivityLog).order_by(ActivityLog.created_at.desc())

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": str(a.id),
            "type": a.action,
            "description": _extract_description(a.details),
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ]
    return build_paginated_response(items, total, page, limit)


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


@router.get("/activities/timeline")
async def activity_timeline(days: int = 7, db: AsyncSession = Depends(get_db)):
    """Daily activity counts for the last N days (server-side aggregation)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(ActivityLog.created_at).label("day"),
            func.count(ActivityLog.id).label("count"),
        )
        .where(ActivityLog.created_at >= cutoff)
        .group_by(func.date(ActivityLog.created_at))
        .order_by(func.date(ActivityLog.created_at))
    )
    return [{"day": str(r.day), "count": r.count} for r in result.all()]



