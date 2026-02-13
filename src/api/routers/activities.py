"""
Activity log endpoints — CRUD + activity feed + interactions.
"""

import json as json_lib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import Float, case, cast, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog, SocialPost
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Activities"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_description(details) -> str:
    if isinstance(details, dict):
        return details.get("message") or details.get("description") or str(details)
    return str(details) if details else ""


def _should_mirror_to_social(action: str, details: dict | None) -> bool:
    action_l = (action or "").lower()
    if "commit" in action_l or "comment" in action_l:
        return True
    if isinstance(details, dict):
        txt = " ".join(str(details.get(k, "")) for k in ("action", "event", "type", "message", "description")).lower()
        return ("commit" in txt) or ("comment" in txt)
    return False


def _social_content_from_activity(action: str, skill: str | None, details: dict | None, success: bool, error_message: str | None) -> str:
    status_icon = "✅" if success else "❌"
    action_text = action or "activity"
    msg = _extract_description(details)
    parts = [f"{status_icon} {action_text}"]
    if skill:
        parts.append(f"skill={skill}")
    if msg and msg != "{}":
        parts.append(msg)
    if error_message:
        parts.append(f"error={error_message}")
    return " · ".join(parts)


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
            "action": a.action,
            "skill": a.skill,
            "success": bool(a.success),
            "status": "ok" if a.success else "error",
            "description": _extract_description(a.details),
            "details": a.details,
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

    # Mirror commit/comment-style events into social feed for dashboard visibility.
    action = data.get("action") or ""
    details = data.get("details") if isinstance(data.get("details"), dict) else {}
    if _should_mirror_to_social(action, details):
        social_post = SocialPost(
            id=uuid.uuid4(),
            platform="activity",
            content=_social_content_from_activity(
                action=action,
                skill=data.get("skill"),
                details=details,
                success=data.get("success", True),
                error_message=data.get("error_message"),
            ),
            visibility="public",
            metadata_json={
                "source": "activity_log",
                "action": action,
                "skill": data.get("skill"),
                "success": data.get("success", True),
                "details": details,
            },
        )
        db.add(social_post)

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


@router.get("/activities/visualization")
async def activity_visualization(
    hours: int = 24,
    limit: int = 25,
    include_creative: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Aggregated activity data for UI visualizations."""
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(hours=max(1, min(hours, 24 * 30)))
    limit = max(1, min(limit, 200))

    hour_bucket = func.date_trunc("hour", ActivityLog.created_at).label("hour")

    hourly_rows = (
        await db.execute(
            select(
                hour_bucket,
                func.count(ActivityLog.id).label("count"),
            )
            .where(ActivityLog.created_at >= cutoff)
            .group_by(hour_bucket)
            .order_by(hour_bucket)
        )
    ).all()

    actions_rows = (
        await db.execute(
            select(ActivityLog.action, func.count(ActivityLog.id).label("count"))
            .where(ActivityLog.created_at >= cutoff)
            .group_by(ActivityLog.action)
            .order_by(desc(func.count(ActivityLog.id)))
            .limit(12)
        )
    ).all()

    skill_bucket = func.coalesce(ActivityLog.skill, "unknown").label("skill")

    skills_rows = (
        await db.execute(
            select(
                skill_bucket,
                func.count(ActivityLog.id).label("count"),
            )
            .where(ActivityLog.created_at >= cutoff)
            .group_by(skill_bucket)
            .order_by(desc(func.count(ActivityLog.id)))
            .limit(12)
        )
    ).all()

    all_skills_rows = []
    creative_hourly_rows = []
    creative_recent_items = []
    creative_actions_rows = []
    if include_creative:
        creative_skill_targets = [
            "brainstorm",
            "experiment",
            "community",
            "fact_check",
            "model_switcher",
            "memeothy",
            "llm",
        ]

        skill_expr = func.lower(func.replace(func.coalesce(ActivityLog.skill, ""), "-", "_"))
        creative_candidates = set(creative_skill_targets)
        creative_candidates.update({f"aria_{name}" for name in creative_skill_targets})
        creative_candidates.update({
            "factcheck",
            "modelswitcher",
        })

        creative_filter = or_(*[skill_expr == value for value in sorted(creative_candidates)])

        all_skills_rows = (
            await db.execute(
                select(
                    skill_bucket,
                    func.count(ActivityLog.id).label("count"),
                )
                .where(ActivityLog.created_at >= cutoff)
                .where(creative_filter)
                .group_by(skill_bucket)
                .order_by(desc(func.count(ActivityLog.id)))
            )
        ).all()

        creative_hourly_rows = (
            await db.execute(
                select(
                    hour_bucket,
                    func.count(ActivityLog.id).label("count"),
                )
                .where(ActivityLog.created_at >= cutoff)
                .where(creative_filter)
                .group_by(hour_bucket)
                .order_by(hour_bucket)
            )
        ).all()

        creative_recent_items = (
            await db.execute(
                select(ActivityLog)
                .where(ActivityLog.created_at >= cutoff)
                .where(creative_filter)
                .order_by(ActivityLog.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()

        creative_actions_rows = (
            await db.execute(
                select(ActivityLog.action, func.count(ActivityLog.id).label("count"))
                .where(ActivityLog.created_at >= cutoff)
                .where(creative_filter)
                .group_by(ActivityLog.action)
                .order_by(desc(func.count(ActivityLog.id)))
                .limit(8)
            )
        ).all()

    total_rows = (
        await db.execute(
            select(
                func.count(ActivityLog.id).label("total"),
                func.sum(case((ActivityLog.success == True, 1), else_=0)).label("success"),
                func.sum(case((ActivityLog.success == False, 1), else_=0)).label("fail"),
            ).where(ActivityLog.created_at >= cutoff)
        )
    ).one()

    recent_items = (
        await db.execute(
            select(ActivityLog)
            .where(ActivityLog.created_at >= cutoff)
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    creative_skill_targets = [
        "brainstorm",
        "experiment",
        "community",
        "fact_check",
        "model_switcher",
        "memeothy",
        "llm",
    ]

    def _normalize_skill_name(name: str | None) -> str:
        skill = (name or "unknown").strip().lower().replace("-", "_")
        if skill.startswith("aria_"):
            skill = skill[5:]
        alias_map = {
            "apiclient": "api_client",
            "factcheck": "fact_check",
            "modelswitcher": "model_switcher",
            "hourlygoals": "hourly_goals",
            "securityscan": "security_scan",
            "sessionmanager": "session_manager",
        }
        return alias_map.get(skill, skill)

    all_skill_counts = {
        _normalize_skill_name(row.skill): int(row.count or 0)
        for row in all_skills_rows
    }
    creative_skills = [
        {
            "skill": skill_name,
            "count": int(all_skill_counts.get(skill_name, 0)),
        }
        for skill_name in creative_skill_targets
    ]
    creative_total = sum(item["count"] for item in creative_skills)

    return {
        "window_hours": hours,
        "generated_at": now_utc.isoformat(),
        "summary": {
            "total": int(total_rows.total or 0),
            "success": int(total_rows.success or 0),
            "fail": int(total_rows.fail or 0),
        },
        "hourly": [
            {"hour": row.hour.isoformat() if row.hour else None, "count": int(row.count or 0)}
            for row in hourly_rows
        ],
        "actions": [
            {"action": row.action or "unknown", "count": int(row.count or 0)}
            for row in actions_rows
        ],
        "skills": [
            {"skill": row.skill or "unknown", "count": int(row.count or 0)}
            for row in skills_rows
        ],
        "creative": {
            "enabled": include_creative,
            "targets": creative_skill_targets,
            "total": creative_total,
            "skills": creative_skills,
            "hourly": [
                {"hour": row.hour.isoformat() if row.hour else None, "count": int(row.count or 0)}
                for row in creative_hourly_rows
            ],
            "actions": [
                {"action": row.action or "unknown", "count": int(row.count or 0)}
                for row in creative_actions_rows
            ],
            "recent": [
                {
                    "id": str(item.id),
                    "action": item.action,
                    "skill": item.skill,
                    "success": bool(item.success),
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "description": _extract_description(item.details),
                }
                for item in creative_recent_items
            ],
        } if include_creative else None,
        "recent": [
            {
                "id": str(item.id),
                "action": item.action,
                "skill": item.skill,
                "success": bool(item.success),
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "description": _extract_description(item.details),
            }
            for item in recent_items
        ],
    }



