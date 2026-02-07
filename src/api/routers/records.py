"""
Records, export, and search endpoints — generic table access.

Uses raw SQL via SQLAlchemy ``text()`` since these operate on dynamic
table names that can't be expressed as static ORM queries.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog, Thought, Memory
from deps import get_db

router = APIRouter(tags=["Records"])


# ── Table whitelist ──────────────────────────────────────────────────────────

TABLE_MAP = {
    "activities": "activity_log",
    "activity_log": "activity_log",
    "thoughts": "thoughts",
    "memories": "memories",
    "goals": "goals",
    "social_posts": "social_posts",
    "heartbeat_log": "heartbeat_log",
    "knowledge_entities": "knowledge_entities",
    "knowledge_relations": "knowledge_relations",
    "hourly_goals": "hourly_goals",
    "performance_log": "performance_log",
    "pending_complex_tasks": "pending_complex_tasks",
    "security_events": "security_events",
    "agent_sessions": "agent_sessions",
    "model_usage": "model_usage",
    "rate_limits": "rate_limits",
    "api_key_rotations": "api_key_rotations",
    "scheduled_jobs": "scheduled_jobs",
    "schedule_tick": "schedule_tick",
}

ORDER_COL_MAP = {
    "activity_log": "created_at",
    "thoughts": "created_at",
    "memories": "created_at",
    "goals": "created_at",
    "social_posts": "posted_at",
    "heartbeat_log": "created_at",
    "knowledge_entities": "created_at",
    "knowledge_relations": "created_at",
    "hourly_goals": "created_at",
    "performance_log": "created_at",
    "pending_complex_tasks": "created_at",
    "security_events": "created_at",
    "agent_sessions": "started_at",
    "model_usage": "created_at",
    "rate_limits": "updated_at",
    "api_key_rotations": "rotated_at",
    "scheduled_jobs": "synced_at",
    "schedule_tick": "updated_at",
}


def _serialize_row(mapping: dict) -> dict:
    result: dict[str, Any] = {}
    for key, val in mapping.items():
        if isinstance(val, datetime):
            result[key] = val.isoformat()
        elif isinstance(val, uuid_mod.UUID):
            result[key] = str(val)
        elif isinstance(val, Decimal):
            result[key] = float(val)
        else:
            result[key] = val
    return result


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/records")
async def api_records(
    table: str = "activities",
    limit: int = 25,
    page: int = 1,
    db: AsyncSession = Depends(get_db),
):
    if table not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid table")
    db_table = TABLE_MAP[table]
    order_col = ORDER_COL_MAP[db_table]
    offset = (page - 1) * limit

    total = (await db.execute(text(f"SELECT COUNT(*) FROM {db_table}"))).scalar() or 0
    result = await db.execute(
        text(f"SELECT * FROM {db_table} ORDER BY {order_col} DESC LIMIT :limit OFFSET :offset"),
        {"limit": limit, "offset": offset},
    )
    records = [_serialize_row(dict(r._mapping)) for r in result.all()]
    return {"records": records, "total": total, "page": page, "limit": limit}


@router.get("/export")
async def api_export(table: str = "activities", db: AsyncSession = Depends(get_db)):
    if table not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid table")
    db_table = TABLE_MAP[table]
    order_col = ORDER_COL_MAP[db_table]

    result = await db.execute(text(f"SELECT * FROM {db_table} ORDER BY {order_col} DESC"))
    records = [_serialize_row(dict(r._mapping)) for r in result.all()]
    return {"records": records}


@router.get("/search")
async def api_search(
    q: str = "",
    activities: bool = True,
    thoughts: bool = True,
    memories: bool = True,
    db: AsyncSession = Depends(get_db),
):
    if not q:
        return {"activities": [], "thoughts": [], "memories": []}
    results: dict[str, list] = {"activities": [], "thoughts": [], "memories": []}
    like = f"%{q}%"

    if activities:
        rows = (
            await db.execute(
                text(
                    "SELECT id, action, details, created_at FROM activity_log "
                    "WHERE details::text ILIKE :like OR action ILIKE :like "
                    "ORDER BY created_at DESC LIMIT 20"
                ),
                {"like": like},
            )
        ).all()
        for r in rows:
            d = dict(r._mapping)
            details = d.get("details", {})
            content = (
                (details.get("message") or details.get("description") or str(details))
                if isinstance(details, dict) else str(details)
            )
            results["activities"].append({
                "id": str(d["id"]),
                "type": d["action"],
                "content": content,
                "timestamp": d["created_at"].isoformat() if d.get("created_at") else None,
            })

    if thoughts:
        rows = (
            await db.execute(
                text(
                    "SELECT id, category, content, created_at FROM thoughts "
                    "WHERE content ILIKE :like OR category ILIKE :like "
                    "ORDER BY created_at DESC LIMIT 20"
                ),
                {"like": like},
            )
        ).all()
        for r in rows:
            d = dict(r._mapping)
            results["thoughts"].append({
                "id": str(d["id"]),
                "type": d["category"],
                "content": d["content"],
                "timestamp": d["created_at"].isoformat() if d.get("created_at") else None,
            })

    if memories:
        rows = (
            await db.execute(
                text(
                    "SELECT id, category, value, created_at FROM memories "
                    "WHERE value::text ILIKE :like OR category ILIKE :like "
                    "ORDER BY created_at DESC LIMIT 20"
                ),
                {"like": like},
            )
        ).all()
        for r in rows:
            d = dict(r._mapping)
            results["memories"].append({
                "id": str(d["id"]),
                "type": d["category"],
                "content": str(d["value"]),
                "timestamp": d["created_at"].isoformat() if d.get("created_at") else None,
            })

    return results
