"""
Activity log endpoints — CRUD + activity feed + interactions.
"""

import json as json_lib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Float, cast, func, select
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
async def api_activities(
    page: int = 1,
    limit: int = 50,
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(ActivityLog)
    if action:
        base = base.where(ActivityLog.action == action)
    base = base.order_by(ActivityLog.created_at.desc())

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
    if data.get("action") == "six_hour_review":
        last_stmt = (
            select(ActivityLog)
            .where(ActivityLog.action == "six_hour_review")
            .order_by(ActivityLog.created_at.desc())
            .limit(1)
        )
        last_activity = (await db.execute(last_stmt)).scalar_one_or_none()
        if last_activity and last_activity.created_at:
            now_utc = datetime.now(timezone.utc)
            created_at = last_activity.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if (now_utc - created_at).total_seconds() < 5 * 3600:
                next_allowed = created_at + timedelta(hours=5)
                return {
                    "status": "cooldown_active",
                    "next_allowed": next_allowed.isoformat(),
                    "created": False,
                }

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


@router.get("/activities/cron-summary")
async def cron_activity_summary(days: int = 7, db: AsyncSession = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(
            ActivityLog.action,
            func.count(ActivityLog.id).label("executions"),
            func.coalesce(func.sum(cast(ActivityLog.details["estimated_tokens"].astext, Float)), 0).label("total_estimated_tokens"),
        )
        .where(ActivityLog.action == "cron_execution")
        .where(ActivityLog.created_at >= cutoff)
        .group_by(ActivityLog.action)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "action": row.action,
            "executions": int(row.executions or 0),
            "total_estimated_tokens": float(row.total_estimated_tokens or 0),
            "days": days,
        }
        for row in rows
    ]


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



