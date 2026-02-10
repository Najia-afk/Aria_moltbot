"""
Records, export, and search endpoints — generic table access.

Uses ORM queries via MODEL_MAP to resolve dynamic table names to
their corresponding SQLAlchemy model classes.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ActivityLog, AgentSession, ApiKeyRotation, Goal, HeartbeatLog, HourlyGoal,
    KnowledgeEntity, KnowledgeRelation, Memory, ModelUsage, PendingComplexTask,
    PerformanceLog, RateLimit, ScheduleTick, ScheduledJob, SecurityEvent,
    SocialPost, Thought,
)
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

MODEL_MAP = {
    "activity_log": ActivityLog,
    "thoughts": Thought,
    "memories": Memory,
    "goals": Goal,
    "social_posts": SocialPost,
    "heartbeat_log": HeartbeatLog,
    "knowledge_entities": KnowledgeEntity,
    "knowledge_relations": KnowledgeRelation,
    "hourly_goals": HourlyGoal,
    "performance_log": PerformanceLog,
    "pending_complex_tasks": PendingComplexTask,
    "security_events": SecurityEvent,
    "agent_sessions": AgentSession,
    "model_usage": ModelUsage,
    "rate_limits": RateLimit,
    "api_key_rotations": ApiKeyRotation,
    "scheduled_jobs": ScheduledJob,
    "schedule_tick": ScheduleTick,
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

MAX_EXPORT_ROWS = 10_000


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
    model = MODEL_MAP[db_table]
    order_col = getattr(model, ORDER_COL_MAP[db_table])
    offset = (page - 1) * limit

    total = (await db.execute(select(func.count()).select_from(model))).scalar() or 0
    result = await db.execute(
        select(model).order_by(order_col.desc()).limit(limit).offset(offset)
    )
    records = [r.to_dict() for r in result.scalars().all()]
    return {"records": records, "total": total, "page": page, "limit": limit}


@router.get("/export")
async def api_export(table: str = "activities", db: AsyncSession = Depends(get_db)):
    if table not in TABLE_MAP:
        raise HTTPException(status_code=400, detail="Invalid table")
    db_table = TABLE_MAP[table]
    model = MODEL_MAP[db_table]
    order_col = getattr(model, ORDER_COL_MAP[db_table])

    result = await db.execute(
        select(model).order_by(order_col.desc()).limit(MAX_EXPORT_ROWS)
    )
    records = [r.to_dict() for r in result.scalars().all()]
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
                select(ActivityLog)
                .where(
                    ActivityLog.details.cast(Text).ilike(like)
                    | ActivityLog.action.ilike(like)
                )
                .order_by(ActivityLog.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        for r in rows:
            details = r.details or {}
            content = (
                (details.get("message") or details.get("description") or str(details))
                if isinstance(details, dict) else str(details)
            )
            results["activities"].append({
                "id": str(r.id),
                "type": r.action,
                "content": content,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            })

    if thoughts:
        rows = (
            await db.execute(
                select(Thought)
                .where(
                    Thought.content.ilike(like)
                    | Thought.category.ilike(like)
                )
                .order_by(Thought.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        for r in rows:
            results["thoughts"].append({
                "id": str(r.id),
                "type": r.category,
                "content": r.content,
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            })

    if memories:
        rows = (
            await db.execute(
                select(Memory)
                .where(
                    Memory.value.cast(Text).ilike(like)
                    | Memory.category.ilike(like)
                )
                .order_by(Memory.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        for r in rows:
            results["memories"].append({
                "id": str(r.id),
                "type": r.category,
                "content": str(r.value),
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            })

    return results
