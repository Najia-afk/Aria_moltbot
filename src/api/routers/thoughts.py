"""
Thoughts endpoints — CRUD for reasoning logs.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Thought
from deps import get_db
from pagination import paginate_query, build_paginated_response

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
async def create_thought(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    thought = Thought(
        id=uuid.uuid4(),
        content=data.get("content"),
        category=data.get("category", "general"),
        metadata_json=data.get("metadata", {}),
    )
    db.add(thought)
    await db.commit()
    return {"id": str(thought.id), "created": True}
