"""
Security events endpoints — CRUD + stats.
"""

import json as json_lib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SecurityEvent
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Security"])


def _parse_jsonb(val, default):
    if val is None:
        return default
    if isinstance(val, str):
        try:
            return json_lib.loads(val)
        except (json_lib.JSONDecodeError, TypeError):
            return default
    return val


@router.get("/security-events")
async def api_security_events(
    page: int = 1,
    limit: int = 25,
    threat_level: Optional[str] = None,
    blocked_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    base = select(SecurityEvent).order_by(SecurityEvent.created_at.desc())
    if threat_level:
        base = base.where(SecurityEvent.threat_level == threat_level.upper())
    if blocked_only:
        base = base.where(SecurityEvent.blocked == True)  # noqa: E712

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    items = [
        {
            "id": str(e.id),
            "threat_level": e.threat_level,
            "threat_type": e.threat_type,
            "threat_patterns": _parse_jsonb(e.threat_patterns, []),
            "input_preview": e.input_preview,
            "source": e.source,
            "user_id": e.user_id,
            "blocked": e.blocked,
            "details": _parse_jsonb(e.details, {}),
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in (await db.execute(stmt)).scalars().all()
    ]
    return build_paginated_response(items, total, page, limit)


@router.post("/security-events")
async def create_security_event(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    input_preview = data.get("input_preview", "")
    if input_preview and len(input_preview) > 500:
        input_preview = input_preview[:500] + "..."
    event = SecurityEvent(
        id=uuid.uuid4(),
        threat_level=data.get("threat_level", "LOW"),
        threat_type=data.get("threat_type", "unknown"),
        threat_patterns=data.get("threat_patterns", []),
        input_preview=input_preview,
        source=data.get("source", "api"),
        user_id=data.get("user_id"),
        blocked=data.get("blocked", False),
        details=data.get("details", {}),
    )
    db.add(event)
    await db.commit()
    return {"id": str(event.id), "created": True}


@router.get("/security-events/stats")
async def api_security_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(SecurityEvent.id)))).scalar() or 0
    blocked = (
        await db.execute(
            select(func.count(SecurityEvent.id)).where(SecurityEvent.blocked == True)  # noqa: E712
        )
    ).scalar() or 0

    by_level_result = await db.execute(
        select(SecurityEvent.threat_level, func.count(SecurityEvent.id))
        .group_by(SecurityEvent.threat_level)
        .order_by(func.count(SecurityEvent.id).desc())
    )
    by_type_result = await db.execute(
        select(SecurityEvent.threat_type, func.count(SecurityEvent.id))
        .group_by(SecurityEvent.threat_type)
        .order_by(func.count(SecurityEvent.id).desc())
        .limit(10)
    )
    recent = (  # noqa: E712
        await db.execute(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.created_at > text("NOW() - INTERVAL '24 hours'")
            )
        )
    ).scalar() or 0

    return {
        "total_events": total,
        "blocked_count": blocked,
        "last_24h": recent,
        "by_level": {r[0]: r[1] for r in by_level_result.all()},
        "by_type": {r[0]: r[1] for r in by_type_result.all()},
    }
