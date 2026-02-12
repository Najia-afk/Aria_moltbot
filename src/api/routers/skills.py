"""
Skill Registry endpoints — read skill health status from the skill_status table.
Skill Invocation stats (S5-07) — observability dashboard data.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, case, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SkillStatusRecord, SkillInvocation, KnowledgeQueryLog
from deps import get_db

router = APIRouter(tags=["Skills"])

_SKILL_SUPPORT_DIRS = {"_template", "__pycache__", "pipelines"}


def _skills_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "aria_skills"
        if candidate.exists() and candidate.is_dir():
            return candidate
    return Path.cwd() / "aria_skills"


def _coherence_scan(include_support: bool = False) -> dict:
    root = _skills_root()
    rows: list[dict] = []
    if not root.exists():
        return {
            "root": str(root),
            "skills": [],
            "count": 0,
            "coherent_count": 0,
            "incoherent_count": 0,
            "coherent": True,
        }

    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if not include_support and entry.name in _SKILL_SUPPORT_DIRS:
            continue

        canonical = f"aria-{entry.name.replace('_', '-')}"
        init_path = entry / "__init__.py"
        json_path = entry / "skill.json"
        md_path = entry / "SKILL.md"

        row = {
            "skill": entry.name,
            "canonical": canonical,
            "is_support_dir": entry.name in _SKILL_SUPPORT_DIRS,
            "has_init": init_path.exists(),
            "has_skill_json": json_path.exists(),
            "has_skill_md": md_path.exists(),
            "name_matches": None,
            "errors": [],
            "warnings": [],
            "coherent": True,
        }

        if not row["has_init"]:
            row["errors"].append("Missing __init__.py")
        if not row["has_skill_json"]:
            row["errors"].append("Missing skill.json")
        if not row["has_skill_md"]:
            row["errors"].append("Missing SKILL.md")

        if row["has_skill_json"]:
            try:
                import json as _json

                manifest = _json.loads(json_path.read_text(encoding="utf-8"))
                actual_name = manifest.get("name")
                row["manifest_name"] = actual_name
                row["name_matches"] = actual_name == canonical
                if actual_name != canonical:
                    row["errors"].append(
                        f"skill.json name mismatch: expected '{canonical}', got '{actual_name}'"
                    )
            except Exception as exc:
                row["name_matches"] = False
                row["errors"].append(f"skill.json parse error: {exc}")

        row["coherent"] = len(row["errors"]) == 0
        rows.append(row)

    coherent_count = sum(1 for row in rows if row["coherent"])
    return {
        "root": str(root),
        "skills": rows,
        "count": len(rows),
        "coherent_count": coherent_count,
        "incoherent_count": len(rows) - coherent_count,
        "coherent": coherent_count == len(rows),
    }

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
    """List all registered skills with optional status filter. Auto-seeds if empty."""
    stmt = select(SkillStatusRecord).order_by(SkillStatusRecord.skill_name)
    if status:
        stmt = stmt.where(SkillStatusRecord.status == status)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Auto-seed if table is empty (first access)
    if not rows and not status:
        for name, layer in _KNOWN_SKILLS:
            seed_stmt = pg_insert(SkillStatusRecord).values(
                skill_name=name,
                canonical_name=name.replace("_", "-"),
                status="healthy",
                layer=layer,
            ).on_conflict_do_nothing(index_elements=["skill_name"])
            await db.execute(seed_stmt)
        await db.commit()
        result = await db.execute(
            select(SkillStatusRecord).order_by(SkillStatusRecord.skill_name)
        )
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


@router.get("/skills/coherence")
async def get_skills_coherence(include_support: bool = False):
    """Report skill-system coherence (init + manifest + docs) for adaptation tooling."""
    data = _coherence_scan(include_support=include_support)
    data["generated_at"] = datetime.now(timezone.utc).isoformat()
    return data


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


@router.get("/skills/insights")
async def skills_insights(
    hours: int = 24,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Rich skill observability payload for the dashboard (stats + timeline + graph activity)."""
    safe_hours = max(1, min(hours, 24 * 30))
    safe_limit = max(10, min(limit, 500))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=safe_hours)

    # Headline metrics
    totals_row = (
        await db.execute(
            select(
                func.count().label("total"),
                func.sum(case((SkillInvocation.success == True, 1), else_=0)).label("successes"),
                func.sum(case((SkillInvocation.success == False, 1), else_=0)).label("failures"),
                func.avg(SkillInvocation.duration_ms).label("avg_duration_ms"),
                func.coalesce(func.sum(SkillInvocation.tokens_used), 0).label("total_tokens"),
                func.count(func.distinct(SkillInvocation.skill_name)).label("unique_skills"),
                func.count(func.distinct(SkillInvocation.tool_name)).label("unique_tools"),
            ).where(SkillInvocation.created_at >= cutoff)
        )
    ).one()

    total_invocations = int(totals_row.total or 0)
    failures = int(totals_row.failures or 0)
    successes = int(totals_row.successes or 0)
    success_rate = round((successes / max(total_invocations, 1)) * 100, 1)

    # Skill-level breakdown
    skill_rows = (
        await db.execute(
            select(
                SkillInvocation.skill_name,
                func.count().label("invocations"),
                func.avg(SkillInvocation.duration_ms).label("avg_duration_ms"),
                func.sum(case((SkillInvocation.success == True, 1), else_=0)).label("successes"),
                func.sum(case((SkillInvocation.success == False, 1), else_=0)).label("failures"),
                func.coalesce(func.sum(SkillInvocation.tokens_used), 0).label("tokens"),
            )
            .where(SkillInvocation.created_at >= cutoff)
            .group_by(SkillInvocation.skill_name)
            .order_by(func.count().desc())
        )
    ).all()

    by_skill = []
    for row in skill_rows:
        invocations = int(row.invocations or 0)
        row_failures = int(row.failures or 0)
        by_skill.append({
            "skill_name": row.skill_name,
            "invocations": invocations,
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "successes": int(row.successes or 0),
            "failures": row_failures,
            "error_rate": round((row_failures / max(invocations, 1)) * 100, 1),
            "total_tokens": int(row.tokens or 0),
        })

    # Tool-level breakdown
    tool_rows = (
        await db.execute(
            select(
                SkillInvocation.tool_name,
                func.count().label("invocations"),
                func.avg(SkillInvocation.duration_ms).label("avg_duration_ms"),
                func.sum(case((SkillInvocation.success == False, 1), else_=0)).label("failures"),
            )
            .where(SkillInvocation.created_at >= cutoff)
            .group_by(SkillInvocation.tool_name)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()

    by_tool = [
        {
            "tool_name": row.tool_name,
            "invocations": int(row.invocations or 0),
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "error_rate": round((int(row.failures or 0) / max(int(row.invocations or 0), 1)) * 100, 1),
        }
        for row in tool_rows
    ]

    # Timeline (hourly)
    timeline_bucket = func.date_trunc("hour", SkillInvocation.created_at)
    timeline_rows = (
        await db.execute(
            select(
                timeline_bucket.label("bucket"),
                func.count().label("invocations"),
                func.avg(SkillInvocation.duration_ms).label("avg_duration_ms"),
                func.sum(case((SkillInvocation.success == False, 1), else_=0)).label("failures"),
            )
            .where(SkillInvocation.created_at >= cutoff)
            .group_by(timeline_bucket)
            .order_by(text("1"))
        )
    ).all()

    timeline = [
        {
            "hour": row.bucket.isoformat() if row.bucket else None,
            "invocations": int(row.invocations or 0),
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "error_rate": round((int(row.failures or 0) / max(int(row.invocations or 0), 1)) * 100, 1),
        }
        for row in timeline_rows
    ]

    # Recent skill executions
    recent_rows = (
        await db.execute(
            select(SkillInvocation)
            .where(SkillInvocation.created_at >= cutoff)
            .order_by(SkillInvocation.created_at.desc())
            .limit(safe_limit)
        )
    ).scalars().all()

    recent_invocations = [
        {
            "id": str(item.id),
            "skill_name": item.skill_name,
            "tool_name": item.tool_name,
            "duration_ms": item.duration_ms,
            "success": item.success,
            "error_type": item.error_type,
            "tokens_used": item.tokens_used,
            "model_used": item.model_used,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in recent_rows
    ]

    # GraphQL / graph interrogation activity from knowledge query log
    query_rows = (
        await db.execute(
            select(KnowledgeQueryLog)
            .where(KnowledgeQueryLog.created_at >= cutoff)
            .order_by(KnowledgeQueryLog.created_at.desc())
            .limit(safe_limit)
        )
    ).scalars().all()

    recent_graph_queries = [
        {
            "id": str(log.id),
            "query_type": log.query_type,
            "source": log.source,
            "params": log.params or {},
            "result_count": log.result_count,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in query_rows
    ]

    return {
        "hours": safe_hours,
        "summary": {
            "total_invocations": total_invocations,
            "success_rate": success_rate,
            "avg_duration_ms": round(float(totals_row.avg_duration_ms or 0), 1),
            "total_tokens": int(totals_row.total_tokens or 0),
            "unique_skills": int(totals_row.unique_skills or 0),
            "unique_tools": int(totals_row.unique_tools or 0),
            "failures": failures,
        },
        "by_skill": by_skill,
        "by_tool": by_tool,
        "timeline": timeline,
        "recent_invocations": recent_invocations,
        "recent_graph_queries": recent_graph_queries,
    }
