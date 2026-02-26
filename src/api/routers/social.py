"""
Social posts endpoints (Moltbook + other platforms).
"""

import json as json_lib
import logging
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SocialPost
from deps import get_db
from pagination import paginate_query, build_paginated_response
from schemas.requests import CreateSocialPost, SocialCleanup, SocialDedupe, ImportMoltbook, UpdateSocialPost

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None

router = APIRouter(tags=["Social"])
logger = logging.getLogger("aria.api.social")

_DEFAULT_MOLTBOOK_API = "https://www.moltbook.com/api/v1"


def _is_test_social_payload(platform: str | None, content: str | None, metadata: dict | None) -> bool:
    markers = ["live test", "test post", "moltbook test", "goal_test", "[test]"]
    parts = [platform or "", content or ""]
    if isinstance(metadata, dict):
        if bool(metadata.get("test")) or bool(metadata.get("is_test")) or bool(metadata.get("dry_run")):
            return True
        try:
            parts.append(json_lib.dumps(metadata, ensure_ascii=False))
        except Exception as e:
            logger.warning("Social metadata parse error: %s", e)
            parts.append(str(metadata))
    haystack = " ".join(parts).lower()
    return any(marker in haystack for marker in markers)


def _extract_items(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "posts", "comments", "results", "data"):
            val = payload.get(key)
            if isinstance(val, list):
                return val
    return []


def _guess_post_id(item: dict) -> str | None:
    for key in ("id", "post_id", "uuid"):
        val = item.get(key)
        if val:
            return str(val)
    return None


def _guess_content(item: dict) -> str:
    for key in ("content", "body", "text", "message", "title"):
        val = item.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return json_lib.dumps(item, ensure_ascii=False)


def _to_social_row(item: dict, platform: str, visibility: str = "public", reply_to: str | None = None) -> dict:
    return {
        "post_id": _guess_post_id(item),
        "content": _guess_content(item),
        "visibility": visibility,
        "reply_to": reply_to,
        "url": item.get("url") or item.get("link"),
        "metadata": item,
        "platform": platform,
    }


async def _fetch_paginated_items(client, endpoint_templates: list[str], max_items: int) -> list[dict]:
    """Fetch up to max_items across possible endpoint templates with page/offset support."""
    collected: list[dict] = []

    for template in endpoint_templates:
        items_for_template: list[dict] = []
        page = 1

        while len(items_for_template) < max_items:
            remaining = max_items - len(items_for_template)
            page_size = min(100, remaining)
            endpoint = template.format(limit=page_size, page=page, offset=(page - 1) * page_size)

            try:
                resp = await client.get(endpoint)
            except Exception as e:
                logger.warning("Social template item parse error: %s", e)
                items_for_template = []
                break

            if resp.status_code != 200:
                items_for_template = []
                break

            payload = resp.json()
            items = _extract_items(payload)
            if not items:
                break

            items_for_template.extend(items)

            if len(items) < page_size:
                break

            page += 1

        if items_for_template:
            collected = items_for_template[:max_items]
            break

    return collected


@router.get("/social")
async def get_social_posts(
    page: int = 1,
    limit: int = 25,
    platform: str | None = None,
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
async def create_social_post(body: CreateSocialPost, db: AsyncSession = Depends(get_db)):
    platform = body.platform
    content = body.content
    metadata = body.metadata

    if _is_test_social_payload(platform, content, metadata):
        return {"created": False, "skipped": True, "reason": "test_payload"}

    post = SocialPost(
        id=uuid.uuid4(),
        platform=platform,
        post_id=body.post_id,
        content=content,
        visibility=body.visibility,
        reply_to=body.reply_to,
        url=body.url,
        metadata_json=metadata,
    )
    db.add(post)
    await db.commit()
    return {"id": str(post.id), "created": True}


@router.post("/social/cleanup")
async def cleanup_social_posts(body: SocialCleanup, db: AsyncSession = Depends(get_db)):
    """Remove test/noise social rows by pattern/platform; supports dry-run."""
    patterns = body.patterns or ["test", "live test post", "abc123", "post 42"]
    platform = body.platform
    dry_run = body.dry_run

    clauses = []
    for pat in patterns:
        if isinstance(pat, str) and pat.strip():
            clauses.append(SocialPost.content.ilike(f"%{pat.strip()}%"))

    if not clauses:
        raise HTTPException(status_code=400, detail="No cleanup patterns provided")

    stmt = select(SocialPost).where(or_(*clauses))
    if platform:
        stmt = stmt.where(SocialPost.platform == platform)

    matched = (await db.execute(stmt)).scalars().all()
    if dry_run:
        return {
            "matched": len(matched),
            "deleted": 0,
            "dry_run": True,
            "samples": [m.to_dict() for m in matched[:5]],
        }

    del_stmt = delete(SocialPost).where(or_(*clauses))
    if platform:
        del_stmt = del_stmt.where(SocialPost.platform == platform)
    result = await db.execute(del_stmt)
    await db.commit()
    return {"matched": len(matched), "deleted": int(result.rowcount or 0), "dry_run": False}


@router.post("/social/dedupe")
async def dedupe_social_posts(body: SocialDedupe, db: AsyncSession = Depends(get_db)):
    """Remove duplicates by (platform, post_id), keeping the newest row."""
    dry_run = body.dry_run
    platform = body.platform

    stmt = select(SocialPost).where(SocialPost.post_id.isnot(None)).order_by(SocialPost.posted_at.desc())
    if platform:
        stmt = stmt.where(SocialPost.platform == platform)

    rows = (await db.execute(stmt)).scalars().all()

    kept_keys: set[tuple[str, str]] = set()
    duplicate_ids: list[uuid.UUID] = []
    duplicate_samples: list[dict] = []

    for row in rows:
        key = (row.platform or "", row.post_id or "")
        if key in kept_keys:
            duplicate_ids.append(row.id)
            if len(duplicate_samples) < 10:
                duplicate_samples.append(
                    {
                        "id": str(row.id),
                        "platform": row.platform,
                        "post_id": row.post_id,
                        "posted_at": row.posted_at.isoformat() if row.posted_at else None,
                    }
                )
            continue
        kept_keys.add(key)

    if dry_run:
        return {
            "dry_run": True,
            "duplicates_found": len(duplicate_ids),
            "deleted": 0,
            "samples": duplicate_samples,
        }

    if duplicate_ids:
        await db.execute(delete(SocialPost).where(SocialPost.id.in_(duplicate_ids)))
        await db.commit()

    return {
        "dry_run": False,
        "duplicates_found": len(duplicate_ids),
        "deleted": len(duplicate_ids),
        "samples": duplicate_samples,
    }


@router.post("/social/import-moltbook")
async def import_moltbook(body: ImportMoltbook, db: AsyncSession = Depends(get_db)):
    """Backfill Aria Moltbook posts/comments into social_posts; optional test cleanup."""
    if httpx is None:
        raise HTTPException(status_code=500, detail="httpx is required for import")

    include_comments = body.include_comments
    cleanup_test = body.cleanup_test
    dry_run = body.dry_run
    max_items = body.max_items

    api_url = str(body.api_url or os.getenv("MOLTBOOK_API_URL", _DEFAULT_MOLTBOOK_API)).rstrip("/")
    api_key = body.api_key or os.getenv("MOLTBOOK_API_KEY") or os.getenv("MOLTBOOK_TOKEN")
    if not api_key:
        raise HTTPException(status_code=400, detail="MOLTBOOK_API_KEY/TOKEN not configured")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    imported = 0
    skipped_existing = 0
    fetched_posts = []
    fetched_comments = []

    async with httpx.AsyncClient(base_url=api_url, timeout=30, headers=headers) as client:
        post_endpoints = [
            "/posts?sort=new&limit={limit}&page={page}",
            "/posts?sort=new&limit={limit}&offset={offset}",
            "/feed?sort=new&limit={limit}&page={page}",
            "/feed?sort=new&limit={limit}&offset={offset}",
            "/agents/me/posts?limit={limit}&page={page}",
            "/agents/me/posts?limit={limit}&offset={offset}",
            "/agents/me/posts",
        ]
        fetched_posts = await _fetch_paginated_items(client, post_endpoints, max_items)

        if include_comments:
            comment_endpoints = [
                "/agents/me/comments?limit={limit}&page={page}",
                "/agents/me/comments?limit={limit}&offset={offset}",
                "/agents/me/comments",
                "/comments?sort=new&limit={limit}&page={page}",
                "/comments?sort=new&limit={limit}&offset={offset}",
            ]
            fetched_comments = await _fetch_paginated_items(client, comment_endpoints, max_items)

    rows = []
    for post in fetched_posts:
        rows.append(_to_social_row(post, platform="moltbook", visibility="public"))
    for comment in fetched_comments:
        reply_to = str(comment.get("post_id") or comment.get("parent_post_id") or "") or None
        rows.append(_to_social_row(comment, platform="moltbook_comment", visibility="public", reply_to=reply_to))

    # Deduplicate by post_id where available
    post_ids = [r["post_id"] for r in rows if r.get("post_id")]
    existing_ids = set()
    if post_ids:
        existing = (await db.execute(select(SocialPost.post_id).where(SocialPost.post_id.in_(post_ids)))).all()
        existing_ids = {row[0] for row in existing if row[0]}

    to_insert = []
    for row in rows:
        if row.get("post_id") and row["post_id"] in existing_ids:
            skipped_existing += 1
            continue
        to_insert.append(row)

    cleanup_result = None
    if cleanup_test:
        patterns = ["test", "live test post", "abc123", "post 42"]
        clauses = [SocialPost.content.ilike(f"%{p}%") for p in patterns]
        if dry_run:
            matched = (await db.execute(select(func.count()).select_from(SocialPost).where(or_(*clauses)))).scalar() or 0
            cleanup_result = {"matched": int(matched), "deleted": 0, "dry_run": True}
        else:
            del_result = await db.execute(delete(SocialPost).where(or_(*clauses)))
            cleanup_result = {"matched": int(del_result.rowcount or 0), "deleted": int(del_result.rowcount or 0), "dry_run": False}

    if not dry_run:
        for row in to_insert:
            db.add(
                SocialPost(
                    id=uuid.uuid4(),
                    platform=row["platform"],
                    post_id=row.get("post_id"),
                    content=row["content"],
                    visibility=row["visibility"],
                    reply_to=row.get("reply_to"),
                    url=row.get("url"),
                    metadata_json=row.get("metadata") or {},
                )
            )
            imported += 1
        await db.commit()
    else:
        imported = len(to_insert)

    return {
        "fetched_posts": len(fetched_posts),
        "fetched_comments": len(fetched_comments),
        "prepared": len(rows),
        "imported": imported,
        "skipped_existing": skipped_existing,
        "cleanup": cleanup_result,
        "dry_run": dry_run,
    }


@router.delete("/social/{post_id}")
async def delete_social_post(post_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Social post not found")
    await db.delete(row)
    await db.commit()
    return {"deleted": True, "id": post_id}


@router.patch("/social/{post_id}")
async def update_social_post(post_id: str, body: UpdateSocialPost, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SocialPost).where(SocialPost.id == post_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Social post not found")
    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return row.to_dict()
