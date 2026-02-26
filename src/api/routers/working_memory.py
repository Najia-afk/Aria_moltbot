"""
Working Memory endpoints — persistent short-term memory that survives restarts.

Provides CRUD plus weighted-context retrieval and checkpoint/restore.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import WorkingMemory
from deps import get_db
from pagination import paginate_query, build_paginated_response
from schemas.requests import CreateWorkingMemory, UpdateWorkingMemory

router = APIRouter(tags=["Working Memory"])
logger = logging.getLogger("aria.api.working_memory")


def _not_expired_clause():
    return (
        (WorkingMemory.ttl_hours.is_(None))
        | (
            WorkingMemory.created_at
            + func.make_interval(0, 0, 0, 0, WorkingMemory.ttl_hours)
            > func.now()
        )
    )


class CleanupRequest(BaseModel):
    category: str | None = None
    source: str | None = None
    delete_expired: bool = True
    dry_run: bool = False


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
    touch_access: bool = True,
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve working memory ranked by weighted relevance.

    relevance = (weight_recency * recency_score)
              + (weight_importance * importance)
              + (weight_access * access_score)

    where:
            recency_score = 1.0 / (1.0 + hours_since_updated)
      access_score  = min(1.0, access_count / 10)
    """
    stmt = select(WorkingMemory)
    if category:
        stmt = stmt.where(WorkingMemory.category == category)
    # Exclude expired TTL items
    stmt = stmt.where(_not_expired_clause())
    # Cap SQL results to avoid loading entire table into memory
    stmt = stmt.order_by(WorkingMemory.importance.desc()).limit(200)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    now = datetime.now(timezone.utc)
    scored = []
    for row in rows:
        updated = row.updated_at or row.created_at
        if updated.tzinfo is None:
            from datetime import timezone as tz
            updated = updated.replace(tzinfo=tz.utc)
        hours_since = max((now - updated).total_seconds() / 3600.0, 0.0)
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

    # Optionally bump access stats for returned items.
    # UI polling should pass touch_access=false to avoid distorting relevance.
    if touch_access and top:
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
    body: CreateWorkingMemory,
    db: AsyncSession = Depends(get_db),
):
    """Store or upsert a working memory item."""
    key = body.key
    value = body.value
    category = body.category
    importance = body.importance
    ttl_hours = body.ttl_hours
    source = body.source

    if not key:
        raise HTTPException(status_code=400, detail="key is required")

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
    body: UpdateWorkingMemory,
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

    if body.value is not None:
        item.value = body.value
    if body.importance is not None:
        item.importance = body.importance
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


@router.get("/working-memory/stats")
async def get_working_memory_stats(db: AsyncSession = Depends(get_db)):
    """Reliable aggregate stats across all working memory rows."""
    total = (await db.execute(select(func.count()).select_from(WorkingMemory))).scalar() or 0

    category_rows = (
        await db.execute(
            select(WorkingMemory.category, func.count().label("count"))
            .group_by(WorkingMemory.category)
            .order_by(func.count().desc())
        )
    ).all()

    avg_importance = (
        await db.execute(select(func.avg(WorkingMemory.importance)))
    ).scalar()
    avg_importance = float(avg_importance) if avg_importance is not None else 0.0

    checkpoint_count = (
        await db.execute(
            select(func.count(func.distinct(WorkingMemory.checkpoint_id)))
            .where(WorkingMemory.checkpoint_id.isnot(None))
        )
    ).scalar() or 0

    expired_count = (
        await db.execute(
            select(func.count())
            .select_from(WorkingMemory)
            .where(~_not_expired_clause())
        )
    ).scalar() or 0

    return {
        "total_items": total,
        "categories": len(category_rows),
        "avg_importance": round(avg_importance, 2),
        "checkpoint_count": checkpoint_count,
        "expired_count": expired_count,
        "by_category": [
            {"category": row[0], "count": row[1]}
            for row in category_rows
        ],
    }


@router.get("/working-memory/file-snapshot")
async def get_working_memory_file_snapshot():
    """Read file-based working memory snapshot from aria_memories/memory/context.json."""
    here = Path(__file__).resolve()
    canonical_candidates: list[Path] = []
    legacy_candidates: list[Path] = []

    for parent in [here.parent, *here.parents, Path.cwd()]:
        canonical_candidates.append(parent / "aria_memories" / "memory" / "context.json")
        legacy_candidates.append(
            parent / "aria_mind" / "skills" / "aria_memories" / "memory" / "context.json"
        )

    def _dedupe(paths: list[Path]) -> list[Path]:
        out: list[Path] = []
        seen: set[str] = set()
        for cand in paths:
            key = str(cand.resolve()) if cand.exists() else str(cand)
            if key in seen:
                continue
            seen.add(key)
            out.append(cand)
        return out

    canonical_candidates = _dedupe(canonical_candidates)
    legacy_candidates = _dedupe(legacy_candidates)

    canonical_existing = [cand for cand in canonical_candidates if cand.exists()]
    legacy_existing = [cand for cand in legacy_candidates if cand.exists()]

    candidates_to_read = canonical_existing if canonical_existing else legacy_existing
    path_mode = "canonical" if canonical_existing else ("legacy-fallback" if legacy_existing else "missing")

    if not candidates_to_read:
        seed_path = canonical_candidates[0] if canonical_candidates else Path("aria_memories/memory/context.json")
        return {
            "exists": False,
            "path": str(seed_path),
            "sources": [],
            "path_mode": path_mode,
            "snapshot": None,
        }

    unique_candidates: list[Path] = candidates_to_read
    seen: set[str] = set()

    picked_path = None
    picked_payload = None
    picked_last_updated = None
    source_meta = []

    try:
        for cand in unique_candidates:
            raw = cand.read_text(encoding="utf-8")
            payload = json.loads(raw) if raw.strip() else {}
            last_updated = payload.get("last_updated") if isinstance(payload, dict) else None

            source_meta.append(
                {
                    "path": str(cand),
                    "last_updated": last_updated,
                    "size_bytes": cand.stat().st_size,
                }
            )

            if picked_path is None:
                picked_path = cand
                picked_payload = payload
                picked_last_updated = last_updated
                continue

            if isinstance(last_updated, str) and isinstance(picked_last_updated, str):
                if last_updated > picked_last_updated:
                    picked_path = cand
                    picked_payload = payload
                    picked_last_updated = last_updated
            elif isinstance(last_updated, str) and not isinstance(picked_last_updated, str):
                picked_path = cand
                picked_payload = payload
                picked_last_updated = last_updated

        return {
            "exists": True,
            "path": str(picked_path),
            "sources": source_meta,
            "path_mode": path_mode,
            "legacy_sources_detected": len(legacy_existing),
            "snapshot": picked_payload,
        }
    except Exception as exc:
        logger.warning("File snapshot read failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to read file snapshot: {exc}")


@router.post("/working-memory/cleanup")
async def cleanup_working_memory(
    payload: CleanupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Smart cleanup for noisy data (e.g. test rows, expired rows)."""
    filters = []
    if payload.category:
        filters.append(WorkingMemory.category == payload.category)
    if payload.source:
        filters.append(WorkingMemory.source == payload.source)

    if payload.delete_expired:
        filters.append(~_not_expired_clause())

    if not filters:
        raise HTTPException(status_code=400, detail="Provide category/source or enable delete_expired")

    count_stmt = select(func.count()).select_from(WorkingMemory)
    for cond in filters:
        count_stmt = count_stmt.where(cond)
    matched = (await db.execute(count_stmt)).scalar() or 0

    if payload.dry_run:
        return {"matched": matched, "deleted": 0, "dry_run": True}

    del_stmt = delete(WorkingMemory)
    for cond in filters:
        del_stmt = del_stmt.where(cond)
    result = await db.execute(del_stmt)
    await db.commit()

    return {
        "matched": matched,
        "deleted": result.rowcount or 0,
        "dry_run": False,
    }
