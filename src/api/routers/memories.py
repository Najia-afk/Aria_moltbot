"""
Memories endpoints — CRUD with upsert by key.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Memory
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Memories"])


@router.get("/memories")
async def get_memories(
    page: int = 1,
    limit: int = 25,
    category: str = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(Memory).order_by(Memory.updated_at.desc())
    if category:
        base = base.where(Memory.category == category)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [m.to_dict() for m in rows]
    return build_paginated_response(items, total, page, limit)


@router.post("/memories")
async def create_or_update_memory(
    request: Request, db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    key = data.get("key")
    value = data.get("value")
    category = data.get("category", "general")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")

    # Try update first
    result = await db.execute(select(Memory).where(Memory.key == key))
    existing = result.scalar_one_or_none()

    if existing:
        existing.value = value
        existing.category = category
        await db.commit()
        return {"id": str(existing.id), "key": key, "upserted": True}

    memory = Memory(key=key, value=value, category=category)
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    return {"id": str(memory.id), "key": key, "upserted": True}


@router.get("/memories/{key}")
async def get_memory_by_key(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Memory).where(Memory.key == key))
    memory = result.scalar_one_or_none()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory.to_dict()


@router.delete("/memories/{key}")
async def delete_memory(key: str, db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Memory).where(Memory.key == key))
    await db.commit()
    return {"deleted": True, "key": key}
