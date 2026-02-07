"""
Thoughts endpoints — CRUD for reasoning logs.
"""

import json as json_lib
import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Thought
from deps import get_db

router = APIRouter(tags=["Thoughts"])


@router.get("/thoughts")
async def api_thoughts(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Thought).order_by(Thought.created_at.desc()).limit(limit)
    )
    rows = result.scalars().all()
    return {
        "thoughts": [
            {
                "id": str(t.id),
                "category": t.category,
                "content": t.content,
                "timestamp": t.created_at.isoformat() if t.created_at else None,
            }
            for t in rows
        ]
    }


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
