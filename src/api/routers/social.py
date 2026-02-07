"""
Social posts endpoints (Moltbook + other platforms).
"""

import json as json_lib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SocialPost
from deps import get_db

router = APIRouter(tags=["Social"])


@router.get("/social")
async def get_social_posts(
    limit: int = 50,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SocialPost).order_by(SocialPost.posted_at.desc()).limit(limit)
    if platform:
        stmt = stmt.where(SocialPost.platform == platform)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {"posts": [p.to_dict() for p in rows], "count": len(rows)}


@router.post("/social")
async def create_social_post(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    post = SocialPost(
        id=uuid.uuid4(),
        platform=data.get("platform", "moltbook"),
        post_id=data.get("post_id"),
        content=data.get("content"),
        visibility=data.get("visibility", "public"),
        reply_to=data.get("reply_to"),
        url=data.get("url"),
        metadata_json=data.get("metadata", {}),
    )
    db.add(post)
    await db.commit()
    return {"id": str(post.id), "created": True}
