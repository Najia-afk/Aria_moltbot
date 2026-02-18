"""
Agent sessions endpoints - CRUD + stats.
Reads from agent_sessions (PostgreSQL-native). No external sync.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AgentSession, ModelUsage
from deps import get_db, get_litellm_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Sessions"])


# -- List sessions -----------------------------------------------------------

@router.get("/sessions")
async def get_agent_sessions(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    session_type: Optional[str] = None,
    search: Optional[str] = None,
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List chat sessions with filtering, search, and pagination."""
    base = select(AgentSession).order_by(AgentSession.started_at.desc())

    if not include_runtime_events:
        base = base.where(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        base = base.where(AgentSession.session_type != "cron")
    if status:
        base = base.where(AgentSession.status == status)
    if agent_id:
        base = base.where(AgentSession.agent_id == agent_id)
    if session_type:
        base = base.where(AgentSession.session_type == session_type)
    if search:
        pattern = f"%{search}%"
        base = base.where(AgentSession.agent_id.ilike(pattern))

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()

    items = [_session_to_dict(s) for s in rows]
    return build_paginated_response(items, total, page, limit)


# -- Hourly breakdown --------------------------------------------------------

@router.get("/sessions/hourly")
async def get_sessions_hourly(
    hours: int = 24,
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Hourly session counts grouped by agent for time-series charts."""
    bounded_hours = max(1, min(int(hours), 168))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=bounded_hours)
    hour_bucket = func.date_trunc("hour", AgentSession.started_at).label("hour")

    hourly_stmt = (
        select(
            hour_bucket,
            AgentSession.agent_id,
            func.count(AgentSession.id).label("count"),
        )
        .where(AgentSession.started_at.is_not(None))
        .where(AgentSession.started_at >= cutoff)
    )

    if not include_runtime_events:
        hourly_stmt = hourly_stmt.where(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        hourly_stmt = hourly_stmt.where(AgentSession.session_type != "cron")
    if status:
        hourly_stmt = hourly_stmt.where(AgentSession.status == status)
    if agent_id:
        hourly_stmt = hourly_stmt.where(AgentSession.agent_id == agent_id)

    result = await db.execute(
        hourly_stmt
        .group_by(hour_bucket, AgentSession.agent_id)
        .order_by(hour_bucket.asc(), AgentSession.agent_id.asc())
    )

    items = [
        {
            "hour": row.hour.isoformat() if row.hour else None,
            "agent_id": row.agent_id,
            "count": int(row.count or 0),
        }
        for row in result.all()
        if row.hour is not None
    ]

    return {"hours": bounded_hours, "timezone": "UTC", "items": items}


# -- Create session ----------------------------------------------------------

@router.post("/sessions")
async def create_agent_session(request: Request, db: AsyncSession = Depends(get_db)):
    """Create a new chat session."""
    data = await request.json()
    status_val = str(data.get("status") or "active").strip().lower()
    allowed_status = {"active", "completed", "ended", "error"}
    if status_val not in allowed_status:
        status_val = "active"

    started_at = _parse_iso_dt(data.get("started_at"))
    ended_at = _parse_iso_dt(data.get("ended_at"))
    if status_val in {"completed", "ended", "error"} and ended_at is None:
        ended_at = datetime.now(timezone.utc)

    metadata_payload = data.get("metadata", {})
    if not isinstance(metadata_payload, dict):
        metadata_payload = {}

    external_session_id = str(data.get("external_session_id") or "").strip()
    if external_session_id:
        metadata_payload["external_session_id"] = external_session_id

    payload = {
        "id": uuid.uuid4(),
        "agent_id": data.get("agent_id", "main"),
        "session_type": data.get("session_type", "interactive"),
        "messages_count": int(data.get("messages_count") or 0),
        "tokens_used": int(data.get("tokens_used") or 0),
        "cost_usd": float(data.get("cost_usd") or 0),
        "status": status_val,
        "metadata_json": metadata_payload,
    }
    if started_at is not None:
        payload["started_at"] = started_at
    if ended_at is not None:
        payload["ended_at"] = ended_at

    session = AgentSession(**payload)
    db.add(session)
    await db.commit()
    return {"id": str(session.id), "created": True}


# -- Update session ----------------------------------------------------------

@router.patch("/sessions/{session_id}")
async def update_agent_session(
    session_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    """Update session status, metadata, or counters."""
    data = await request.json()
    values = {}

    if data.get("status"):
        values["status"] = data["status"]
        if data["status"] in ("completed", "ended", "error"):
            values["ended_at"] = text("NOW()")
    if data.get("messages_count") is not None:
        values["messages_count"] = data["messages_count"]
    if data.get("tokens_used") is not None:
        values["tokens_used"] = data["tokens_used"]
    if data.get("cost_usd") is not None:
        values["cost_usd"] = data["cost_usd"]

    if values:
        await db.execute(
            update(AgentSession)
            .where(AgentSession.id == uuid.UUID(session_id))
            .values(**values)
        )
        await db.commit()
    return {"updated": True}


# -- Delete session ----------------------------------------------------------

@router.delete("/sessions/{session_id}")
async def delete_agent_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session by ID."""
    try:
        session_uuid = uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session_id") from exc

    result = await db.execute(
        delete(AgentSession).where(AgentSession.id == session_uuid)
    )
    await db.commit()

    if not (result.rowcount or 0):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True, "id": session_id}


# -- Session stats -----------------------------------------------------------

@router.get("/sessions/stats")
async def get_session_stats(
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    litellm_db: AsyncSession = Depends(get_litellm_db),
):
    """Session statistics with LiteLLM enrichment."""
    session_filters = []
    if not include_runtime_events:
        session_filters.append(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        session_filters.append(AgentSession.session_type != "cron")
    if status:
        session_filters.append(AgentSession.status == status)
    if agent_id:
        session_filters.append(AgentSession.agent_id == agent_id)

    total_stmt = select(func.count(AgentSession.id))
    if session_filters:
        total_stmt = total_stmt.where(*session_filters)
    total = (await db.execute(total_stmt)).scalar() or 0

    active_stmt = select(func.count(AgentSession.id)).where(AgentSession.status == "active")
    if session_filters:
        active_stmt = active_stmt.where(*session_filters)
    active = (await db.execute(active_stmt)).scalar() or 0

    skill_tokens = (
        await db.execute(
            select(func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0))
        )
    ).scalar() or 0
    skill_cost = (
        await db.execute(select(func.coalesce(func.sum(ModelUsage.cost_usd), 0)))
    ).scalar() or 0

    llm_totals = {"tokens": 0, "cost": 0.0, "rows": 0}
    try:
        llm_result = await litellm_db.execute(
            text(
                'SELECT COUNT(*) AS rows, '
                'COALESCE(SUM(total_tokens), 0) AS tokens, '
                'COALESCE(SUM(spend), 0) AS cost '
                'FROM "LiteLLM_SpendLogs"'
            )
        )
        row = llm_result.mappings().one()
        llm_totals = {
            "rows": int(row.get("rows") or 0),
            "tokens": int(row.get("tokens") or 0),
            "cost": float(row.get("cost") or 0),
        }
    except Exception:
        pass

    total_tokens = int(skill_tokens) + int(llm_totals["tokens"])
    total_cost = float(skill_cost) + float(llm_totals["cost"])

    by_agent_stmt = select(
        AgentSession.agent_id,
        func.count(AgentSession.id).label("sessions"),
    )
    if session_filters:
        by_agent_stmt = by_agent_stmt.where(*session_filters)
    by_agent_stmt = by_agent_stmt.group_by(AgentSession.agent_id).order_by(
        func.count(AgentSession.id).desc()
    )
    by_agent_result = await db.execute(by_agent_stmt)
    by_agent_map = {
        str(r[0]): {"agent_id": str(r[0]), "sessions": int(r[1] or 0), "tokens": 0, "cost": 0.0}
        for r in by_agent_result.all()
    }

    usage_stmt = (
        select(
            AgentSession.agent_id,
            func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0).label("tokens"),
            func.coalesce(func.sum(ModelUsage.cost_usd), 0).label("cost"),
        )
        .select_from(ModelUsage)
        .join(AgentSession, AgentSession.id == ModelUsage.session_id)
    )
    if session_filters:
        usage_stmt = usage_stmt.where(*session_filters)
    usage_stmt = usage_stmt.group_by(AgentSession.agent_id)
    by_agent_skill_usage = await db.execute(usage_stmt)
    for r in by_agent_skill_usage.all():
        agent = str(r[0] or "unknown")
        if agent == "unknown":
            continue
        if agent not in by_agent_map:
            by_agent_map[agent] = {"agent_id": agent, "sessions": 0, "tokens": 0, "cost": 0.0}
        by_agent_map[agent]["tokens"] += int(r[1] or 0)
        by_agent_map[agent]["cost"] += float(r[2] or 0)

    by_agent = sorted(
        by_agent_map.values(),
        key=lambda entry: entry["sessions"],
        reverse=True,
    )

    by_status_stmt = select(
        AgentSession.status,
        func.count(AgentSession.id).label("count"),
    )
    if session_filters:
        by_status_stmt = by_status_stmt.where(*session_filters)
    by_status_result = await db.execute(by_status_stmt.group_by(AgentSession.status))
    by_status = [{"status": r[0], "count": r[1]} for r in by_status_result.all()]

    by_type_stmt = select(
        AgentSession.session_type,
        func.count(AgentSession.id).label("count"),
    )
    if session_filters:
        by_type_stmt = by_type_stmt.where(*session_filters)
    by_type_result = await db.execute(by_type_stmt.group_by(AgentSession.session_type))
    by_type = [{"type": r[0], "count": r[1]} for r in by_type_result.all()]

    return {
        "total_sessions": total,
        "active_sessions": active,
        "total_tokens": total_tokens,
        "total_cost": float(total_cost),
        "by_agent": by_agent,
        "by_status": by_status,
        "by_type": by_type,
        "litellm": {
            "sessions": llm_totals["rows"],
            "tokens": llm_totals["tokens"],
            "cost": llm_totals["cost"],
        },
        "sources": {
            "skills": {"tokens": int(skill_tokens), "cost": float(skill_cost)},
            "litellm": {"tokens": int(llm_totals["tokens"]), "cost": float(llm_totals["cost"])},
        },
    }


# -- Helpers -----------------------------------------------------------------

def _parse_iso_dt(value):
    """Parse an ISO datetime string, tolerating Z suffix."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _session_to_dict(s):
    """Convert an AgentSession ORM object to a JSON-serializable dict."""
    return {
        "id": str(s.id),
        "agent_id": s.agent_id,
        "session_type": s.session_type,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "messages_count": s.messages_count,
        "tokens_used": s.tokens_used,
        "cost_usd": float(s.cost_usd) if s.cost_usd else 0,
        "status": s.status,
        "metadata": s.metadata_json or {},
    }
