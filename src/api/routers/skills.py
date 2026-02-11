"""
Skill Registry endpoints — read skill health status from the skill_status table.
Skill Invocation stats (S5-07) — observability dashboard data.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SkillStatusRecord, SkillInvocation
from deps import get_db

router = APIRouter(tags=["Skills"])

# Well-known Aria skills (name, layer)
_KNOWN_SKILLS = [
    ("agent_manager", "L2"), ("api_client", "L1"), ("brainstorm", "L3"),
    ("ci_cd", "L2"), ("community", "L3"), ("data_pipeline", "L2"),
    ("database", "L1"), ("experiment", "L3"), ("fact_check", "L2"),
    ("goals", "L2"), ("health", "L1"), ("hourly_goals", "L2"),
    ("input_guard", "L1"), ("knowledge_graph", "L2"), ("litellm", "L1"),
    ("llm", "L1"), ("market_data", "L2"), ("memeothy", "L3"),
    ("model_switcher", "L2"), ("moltbook", "L3"), ("moonshot", "L2"),
    ("ollama", "L1"), ("performance", "L2"), ("pipeline_skill", "L2"),
    ("pipelines", "L2"), ("portfolio", "L3"), ("pytest_runner", "L2"),
    ("research", "L3"), ("sandbox", "L2"), ("schedule", "L2"),
    ("security_scan", "L2"), ("session_manager", "L2"), ("social", "L3"),
    ("telegram", "L2"), ("working_memory", "L1"),
]


# ── List / Filter ────────────────────────────────────────────────────────────

@router.get("/skills")
async def list_skills(
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    """List all registered skills with optional status filter."""
    stmt = select(SkillStatusRecord).order_by(SkillStatusRecord.skill_name)
    if status:
        stmt = stmt.where(SkillStatusRecord.status == status)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return {
        "skills": [r.to_dict() for r in rows],
        "count": len(rows),
        "healthy": sum(1 for r in rows if r.status == "healthy"),
        "degraded": sum(1 for r in rows if r.status == "degraded"),
        "unavailable": sum(1 for r in rows if r.status == "unavailable"),
    }


# ── Single Skill Health ─────────────────────────────────────────────────────

@router.get("/skills/{name}/health")
async def get_skill_health(name: str, db: AsyncSession = Depends(get_db)):
    """Return health details for a single skill by name."""
    result = await db.execute(
        select(SkillStatusRecord).where(SkillStatusRecord.skill_name == name)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found")
    return row.to_dict()


# ── Seed Skills ──────────────────────────────────────────────────────────────

@router.post("/skills/seed")
async def seed_skills(db: AsyncSession = Depends(get_db)):
    """Populate skill_status table with well-known Aria skills (idempotent)."""
    created = 0
    for name, layer in _KNOWN_SKILLS:
        stmt = pg_insert(SkillStatusRecord).values(
            skill_name=name,
            canonical_name=name.replace("_", "-"),
            status="healthy",
            layer=layer,
        ).on_conflict_do_nothing(index_elements=["skill_name"])
        result = await db.execute(stmt)
        created += max(0, result.rowcount)
    await db.commit()
    return {"seeded": created, "total": len(_KNOWN_SKILLS)}


# ── Skill Invocation Recording (S5-07) ──────────────────────────────────────

@router.post("/skills/invocations")
async def record_invocation(request: Request, db: AsyncSession = Depends(get_db)):
    """Record a skill invocation for observability."""
    data = await request.json()
    inv = SkillInvocation(
        skill_name=data.get("skill_name", "unknown"),
        tool_name=data.get("tool_name", "unknown"),
        duration_ms=data.get("duration_ms"),
        success=data.get("success", True),
        error_type=data.get("error_type"),
        tokens_used=data.get("tokens_used"),
        model_used=data.get("model_used"),
    )
    db.add(inv)
    await db.commit()
    return {"recorded": True}


@router.get("/skills/stats")
async def skill_stats(hours: int = 24, db: AsyncSession = Depends(get_db)):
    """Skill performance stats for the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = (
        select(
            SkillInvocation.skill_name,
            func.count().label("total"),
            func.avg(SkillInvocation.duration_ms).label("avg_duration_ms"),
            func.sum(case((SkillInvocation.success == True, 1), else_=0)).label("successes"),
            func.sum(case((SkillInvocation.success == False, 1), else_=0)).label("failures"),
            func.sum(SkillInvocation.tokens_used).label("total_tokens"),
        )
        .where(SkillInvocation.created_at >= cutoff)
        .group_by(SkillInvocation.skill_name)
        .order_by(func.count().desc())
    )
    result = await db.execute(stmt)
    stats = []
    for row in result.all():
        total = row.total or 1
        stats.append({
            "skill_name": row.skill_name,
            "total": row.total,
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "successes": row.successes or 0,
            "failures": row.failures or 0,
            "error_rate": round((row.failures or 0) / total, 3),
            "total_tokens": row.total_tokens or 0,
        })
    return {"stats": stats, "hours": hours}


@router.get("/skills/stats/{skill_name}")
async def skill_detail_stats(
    skill_name: str,
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Detailed stats for one skill with recent invocations."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = (
        select(SkillInvocation)
        .where(SkillInvocation.skill_name == skill_name)
        .where(SkillInvocation.created_at >= cutoff)
        .order_by(SkillInvocation.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    invocations = [i.to_dict() for i in result.scalars().all()]

    total = len(invocations)
    failures = sum(1 for i in invocations if not i.get("success", True))
    avg_duration = (
        sum(i.get("duration_ms", 0) or 0 for i in invocations) / max(total, 1)
    )
    return {
        "skill_name": skill_name,
        "total": total,
        "failures": failures,
        "error_rate": round(failures / max(total, 1), 3),
        "avg_duration_ms": round(avg_duration, 1),
        "invocations": invocations[:25],
    }
