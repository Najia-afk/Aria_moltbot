"""
Social posts endpoints (Moltbook + other platforms).
"""

import json as json_lib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SocialPost
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Social"])


@router.get("/social")
async def get_social_posts(
    page: int = 1,
    limit: int = 25,
    platform: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    base = select(SocialPost).order_by(SocialPost.posted_at.desc())
    if platform:
        base = base.where(SocialPost.platform == platform)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [p.to_dict() for p in rows]
    return build_paginated_response(items, total, page, limit)


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
