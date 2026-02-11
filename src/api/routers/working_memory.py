"""
Working Memory endpoints — persistent short-term memory that survives restarts.

Provides CRUD plus weighted-context retrieval and checkpoint/restore.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WorkingMemory
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Working Memory"])


# ── List / Filter ────────────────────────────────────────────────────────────

@router.get("/working-memory")
async def list_working_memory(
    page: int = 1,
    category: str = None,
    key: str = None,
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """List working memory items with optional category/key filters."""
    base = select(WorkingMemory).order_by(WorkingMemory.created_at.desc())
    if category:
        base = base.where(WorkingMemory.category == category)
    if key:
        base = base.where(WorkingMemory.key == key)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [r.to_dict() for r in rows]
    return build_paginated_response(items, total, page, limit)


# ── Weighted Context Retrieval ───────────────────────────────────────────────

@router.get("/working-memory/context")
async def get_working_memory_context(
    limit: int = 20,
    weight_recency: float = 0.4,
    weight_importance: float = 0.4,
    weight_access: float = 0.2,
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve working memory ranked by weighted relevance.

    relevance = (weight_recency * recency_score)
              + (weight_importance * importance)
              + (weight_access * access_score)

    where:
      recency_score = 1.0 / (1.0 + hours_since_accessed)
      access_score  = min(1.0, access_count / 10)
    """
    stmt = select(WorkingMemory)
    if category:
        stmt = stmt.where(WorkingMemory.category == category)
    # Exclude expired TTL items
    stmt = stmt.where(
        (WorkingMemory.ttl_hours.is_(None))
        | (
            WorkingMemory.created_at
            + func.make_interval(0, 0, 0, 0, WorkingMemory.ttl_hours)
            > func.now()
        )
    )
    # Cap SQL results to avoid loading entire table into memory
    stmt = stmt.order_by(WorkingMemory.importance.desc()).limit(200)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    now = datetime.now(timezone.utc)
    scored = []
    for row in rows:
        accessed = row.accessed_at or row.created_at
        if accessed.tzinfo is None:
            from datetime import timezone as tz
            accessed = accessed.replace(tzinfo=tz.utc)
        hours_since = max((now - accessed).total_seconds() / 3600.0, 0.0)
        recency_score = 1.0 / (1.0 + hours_since)
        access_score = min(1.0, (row.access_count or 0) / 10.0)
        importance = row.importance if row.importance is not None else 0.5

        relevance = (
            weight_recency * recency_score
            + weight_importance * importance
            + weight_access * access_score
        )
        scored.append((relevance, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    # Bump access counts for returned items
    for _, row in top:
        row.access_count = (row.access_count or 0) + 1
        row.accessed_at = now
    await db.commit()

    return {
        "context": [
            {**r.to_dict(), "relevance": round(score, 4)}
            for score, r in top
        ],
        "count": len(top),
    }


# ── Store ────────────────────────────────────────────────────────────────────

@router.post("/working-memory")
async def store_working_memory(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Store or upsert a working memory item."""
    data = await request.json()
    key = data.get("key")
    value = data.get("value")
    category = data.get("category", "general")
    importance = data.get("importance", 0.5)
    ttl_hours = data.get("ttl_hours")
    source = data.get("source")

    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    if value is None:
        raise HTTPException(status_code=400, detail="value is required")

    # Upsert by (category, key)
    result = await db.execute(
        select(WorkingMemory).where(
            WorkingMemory.category == category,
            WorkingMemory.key == key,
        )
    )
    existing = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.value = value
        existing.importance = importance
        existing.ttl_hours = ttl_hours
        existing.source = source
        existing.updated_at = now
        existing.access_count = (existing.access_count or 0) + 1
        existing.accessed_at = now
        await db.commit()
        return {"id": str(existing.id), "key": key, "upserted": True}

    item = WorkingMemory(
        category=category,
        key=key,
        value=value,
        importance=importance,
        ttl_hours=ttl_hours,
        source=source,
        accessed_at=now,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"id": str(item.id), "key": key, "upserted": True}


# ── Update ───────────────────────────────────────────────────────────────────

@router.patch("/working-memory/{item_id}")
async def update_working_memory(
    item_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Partial update of a working memory item (value, importance)."""
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(
        select(WorkingMemory).where(WorkingMemory.id == uid)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Working memory item not found")

    data = await request.json()
    if "value" in data:
        item.value = data["value"]
    if "importance" in data:
        item.importance = data["importance"]
    item.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return item.to_dict()


# ── Delete ───────────────────────────────────────────────────────────────────

@router.delete("/working-memory/{item_id}")
async def delete_working_memory(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Remove a working memory item."""
    try:
        uid = uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    result = await db.execute(
        select(WorkingMemory).where(WorkingMemory.id == uid)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Working memory item not found")

    await db.delete(item)
    await db.commit()
    return {"deleted": True, "id": item_id}


# ── Checkpoint ───────────────────────────────────────────────────────────────

@router.post("/working-memory/checkpoint")
async def create_checkpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Snapshot the current working memory state.
    Stamps every existing item with a checkpoint_id.
    """
    now = datetime.now(timezone.utc)
    checkpoint_id = f"ckpt-{now.strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"

    result = await db.execute(
        select(WorkingMemory).where(
            (WorkingMemory.ttl_hours.is_(None))
            | (
                WorkingMemory.created_at
                + func.make_interval(0, 0, 0, 0, WorkingMemory.ttl_hours)
                > func.now()
            )
        )
    )
    rows = result.scalars().all()
    for row in rows:
        row.checkpoint_id = checkpoint_id
        row.updated_at = now
    await db.commit()

    return {
        "checkpoint_id": checkpoint_id,
        "items_checkpointed": len(rows),
        "created_at": now.isoformat(),
    }


@router.get("/working-memory/checkpoint")
async def get_latest_checkpoint(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve items from the latest checkpoint."""
    # Find latest checkpoint_id
    sub = (
        select(WorkingMemory.checkpoint_id)
        .where(WorkingMemory.checkpoint_id.isnot(None))
        .order_by(WorkingMemory.updated_at.desc())
        .limit(1)
    )
    result = await db.execute(sub)
    latest_id = result.scalar_one_or_none()

    if not latest_id:
        return {"checkpoint_id": None, "items": [], "count": 0}

    stmt = select(WorkingMemory).where(WorkingMemory.checkpoint_id == latest_id)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return {
        "checkpoint_id": latest_id,
        "items": [r.to_dict() for r in rows],
        "count": len(rows),
    }
