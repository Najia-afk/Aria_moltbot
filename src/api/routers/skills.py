"""
Skill Registry endpoints — read skill health status from the skill_status table.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SkillStatusRecord
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
