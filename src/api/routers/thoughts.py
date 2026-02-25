"""
Thoughts endpoints — CRUD for reasoning logs.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Thought
from deps import get_db
from pagination import paginate_query, build_paginated_response
from schemas.requests import CreateThought as CreateThoughtBody, UpdateThought

router = APIRouter(tags=["Thoughts"])


@router.get("/thoughts")
async def api_thoughts(page: int = 1, limit: int = 25, db: AsyncSession = Depends(get_db)):
    base = select(Thought).order_by(Thought.created_at.desc())

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": str(t.id),
            "category": t.category,
            "content": t.content,
            "timestamp": t.created_at.isoformat() if t.created_at else None,
        }
        for t in rows
    ]
    return build_paginated_response(items, total, page, limit)


@router.post("/thoughts")
async def create_thought(body: CreateThoughtBody, db: AsyncSession = Depends(get_db)):
    thought = Thought(
        id=uuid.uuid4(),
        content=body.content,
        category=body.category,
        metadata_json=body.metadata,
    )
    db.add(thought)
    await db.commit()
    return {"id": str(thought.id), "created": True}


@router.delete("/thoughts/{thought_id}")
async def delete_thought(thought_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Thought).where(Thought.id == thought_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thought not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": thought_id}


@router.patch("/thoughts/{thought_id}")
async def update_thought(thought_id: str, body: UpdateThought, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Thought).where(Thought.id == thought_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Thought not found")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row.to_dict()
