"""
Agent sessions endpoints — CRUD + stats with LiteLLM enrichment.
"""

import json as json_lib
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import LITELLM_MASTER_KEY, SERVICE_URLS
from db.models import AgentSession
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Sessions"])


@router.get("/sessions")
async def get_agent_sessions(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(AgentSession).order_by(AgentSession.started_at.desc())
    if status:
        base = base.where(AgentSession.status == status)
    if agent_id:
        base = base.where(AgentSession.agent_id == agent_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
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
        for s in rows
    ]
    return build_paginated_response(items, total, page, limit)


@router.post("/sessions")
async def create_agent_session(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    session = AgentSession(
        id=uuid.uuid4(),
        agent_id=data.get("agent_id", "main"),
        session_type=data.get("session_type", "interactive"),
        status="active",
        metadata_json=data.get("metadata", {}),
    )
    db.add(session)
    await db.commit()
    return {"id": str(session.id), "created": True}


@router.patch("/sessions/{session_id}")
async def update_agent_session(
    session_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    values: dict = {}
    if data.get("status"):
        values["status"] = data["status"]
        if data["status"] in ("completed", "ended", "error"):
            from sqlalchemy import text
            values["ended_at"] = text("NOW()")
    if data.get("messages_count") is not None:
        values["messages_count"] = data["messages_count"]
    if data.get("tokens_used") is not None:
        values["tokens_used"] = data["tokens_used"]
    if data.get("cost_usd") is not None:
        values["cost_usd"] = data["cost_usd"]
    if values:
        await db.execute(
            update(AgentSession).where(AgentSession.id == uuid.UUID(session_id)).values(**values)
        )
        await db.commit()
    return {"updated": True}


@router.get("/sessions/stats")
async def get_session_stats(db: AsyncSession = Depends(get_db)):
    """Session statistics, enriched with LiteLLM data."""
    total = (await db.execute(select(func.count(AgentSession.id)))).scalar() or 0
    active = (
        await db.execute(
            select(func.count(AgentSession.id)).where(AgentSession.status == "active")
        )
    ).scalar() or 0
    total_tokens = (
        await db.execute(select(func.coalesce(func.sum(AgentSession.tokens_used), 0)))
    ).scalar() or 0
    total_cost = (
        await db.execute(select(func.coalesce(func.sum(AgentSession.cost_usd), 0)))
    ).scalar() or 0

    by_agent_result = await db.execute(
        select(
            AgentSession.agent_id,
            func.count(AgentSession.id).label("sessions"),
            func.coalesce(func.sum(AgentSession.tokens_used), 0).label("tokens"),
            func.coalesce(func.sum(AgentSession.cost_usd), 0).label("cost"),
        )
        .group_by(AgentSession.agent_id)
        .order_by(func.count(AgentSession.id).desc())
    )
    by_agent = [
        {"agent_id": r[0], "sessions": r[1], "tokens": r[2], "cost": float(r[3])}
        for r in by_agent_result.all()
    ]

    by_status_result = await db.execute(
        select(
            AgentSession.status,
            func.count(AgentSession.id).label("count"),
        ).group_by(AgentSession.status)
    )
    by_status = [{"status": r[0], "count": r[1]} for r in by_status_result.all()]

    by_type_result = await db.execute(
        select(
            AgentSession.session_type,
            func.count(AgentSession.id).label("count"),
        ).group_by(AgentSession.session_type)
    )
    by_type = [{"type": r[0], "count": r[1]} for r in by_type_result.all()]

    # Enrich with LiteLLM totals
    litellm_tokens = 0
    litellm_cost = 0.0
    litellm_sessions = 0
    try:
        litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000",))[0]
        headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{litellm_base}/global/spend", headers=headers)
            if resp.status_code == 200:
                gdata = resp.json()
                litellm_cost = float(gdata.get("spend", 0) or 0)
            logs_resp = await client.get(f"{litellm_base}/spend/logs", headers=headers)
            if logs_resp.status_code == 200:
                logs = logs_resp.json()
                if isinstance(logs, list):
                    litellm_sessions = len(
                        {l.get("session_id", "") for l in logs if l.get("session_id")}
                    )
                    litellm_tokens = sum(l.get("total_tokens", 0) or 0 for l in logs)
    except Exception:
        pass

    return {
        "total_sessions": total + litellm_sessions,
        "active_sessions": active,
        "total_tokens": total_tokens + litellm_tokens,
        "total_cost": float(total_cost) + litellm_cost,
        "by_agent": by_agent,
        "by_status": by_status,
        "by_type": by_type,
        "litellm": {
            "sessions": litellm_sessions,
            "tokens": litellm_tokens,
            "cost": litellm_cost,
        },
    }
