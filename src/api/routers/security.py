"""
Security events endpoints — CRUD + stats.
"""

import json as json_lib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SecurityEvent
from deps import get_db

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
    limit: int = 100,
    threat_level: Optional[str] = None,
    blocked_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit)
    if threat_level:
        stmt = stmt.where(SecurityEvent.threat_level == threat_level.upper())
    if blocked_only:
        stmt = stmt.where(SecurityEvent.blocked == True)  # noqa: E712

    result = await db.execute(stmt)
    return [
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
        for e in result.scalars().all()
    ]


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
    recent = (
        await db.execute(
            select(func.count(SecurityEvent.id)).where(
                SecurityEvent.created_at > func.now() - func.cast("24 hours", func.literal_column("interval"))
            )
        )
    ).scalar()

    # Safer approach for the 24h filter using text
    from sqlalchemy import text
    recent = (
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
