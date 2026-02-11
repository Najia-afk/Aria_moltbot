"""
Lessons Learned endpoints — error recovery system (S5-02).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import LessonLearned
from deps import get_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Lessons"])


# ── Known error patterns — seeded on first POST /lessons/seed ──────────────

_KNOWN_PATTERNS = [
    {"error_pattern": "api_429_rate_limit", "error_type": "rate_limit",
     "resolution": "Wait 60s, retry with different model via model_switcher"},
    {"error_pattern": "litellm_timeout", "error_type": "timeout",
     "resolution": "Downgrade to faster model (qwen3-mlx), reduce max_tokens"},
    {"error_pattern": "tool_hallucinated_function", "error_type": "validation",
     "resolution": "Re-read TOOLS.md, use only documented tool names"},
    {"error_pattern": "db_connection_refused", "error_type": "connection",
     "resolution": "Check aria-db container health, wait 10s and retry"},
    {"error_pattern": "embedding_model_unavailable", "error_type": "model",
     "resolution": "Fallback to keyword search instead of semantic search"},
]


@router.post("/lessons")
async def record_lesson(request: Request, db: AsyncSession = Depends(get_db)):
    """Record a new lesson or increment occurrence of existing one."""
    data = await request.json()
    error_pattern = data.get("error_pattern")
    error_type = data.get("error_type")
    resolution = data.get("resolution")

    if not error_pattern or not error_type:
        raise HTTPException(status_code=400, detail="error_pattern and error_type are required")

    existing = await db.execute(
        select(LessonLearned).where(LessonLearned.error_pattern == error_pattern)
    )
    found = existing.scalar_one_or_none()

    if found:
        found.occurrences += 1
        found.last_occurred = func.now()
        if resolution:
            found.resolution = resolution
        await db.commit()
        return {"updated": True, "occurrences": found.occurrences, "id": str(found.id)}

    new_lesson = LessonLearned(
        error_pattern=error_pattern,
        error_type=error_type,
        resolution=resolution or "unresolved — needs investigation",
        skill_name=data.get("skill_name"),
        context=data.get("context", {}),
        resolution_code=data.get("resolution_code"),
        effectiveness=float(data.get("effectiveness", 1.0)),
    )
    db.add(new_lesson)
    await db.commit()
    await db.refresh(new_lesson)
    return {"created": True, "id": str(new_lesson.id)}


@router.get("/lessons/check")
async def check_known_errors(
    error_type: str = None,
    skill_name: str = None,
    error_message: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Check if there's a known resolution for this error type."""
    stmt = select(LessonLearned)
    if error_type:
        stmt = stmt.where(LessonLearned.error_type == error_type)
    if skill_name:
        stmt = stmt.where(LessonLearned.skill_name == skill_name)
    stmt = stmt.order_by(LessonLearned.effectiveness.desc()).limit(5)

    result = await db.execute(stmt)
    lessons = result.scalars().all()
    return {
        "lessons": [l.to_dict() for l in lessons],
        "has_resolution": len(lessons) > 0,
    }


@router.get("/lessons")
async def list_lessons(
    page: int = 1,
    per_page: int = 25,
    db: AsyncSession = Depends(get_db),
):
    """List all lessons learned, most recent first."""
    base = select(LessonLearned).order_by(LessonLearned.last_occurred.desc())
    total = (await db.execute(select(func.count(LessonLearned.id)))).scalar() or 0
    stmt, _ = paginate_query(base, page, per_page)
    result = await db.execute(stmt)
    items = [l.to_dict() for l in result.scalars().all()]
    return build_paginated_response(items, total, page, per_page)


@router.post("/lessons/seed")
async def seed_lessons(db: AsyncSession = Depends(get_db)):
    """Seed known error patterns (idempotent)."""
    created = 0
    for pattern in _KNOWN_PATTERNS:
        stmt = pg_insert(LessonLearned).values(**pattern).on_conflict_do_nothing(
            constraint="uq_lesson_pattern"
        )
        result = await db.execute(stmt)
        created += max(0, result.rowcount)
    await db.commit()
    return {"seeded": created, "total": len(_KNOWN_PATTERNS)}
