"""
Model usage endpoints — single source of truth: aria_data.model_usage.

All LLM calls are logged here by the engine's telemetry module
(aria_engine.telemetry.log_model_usage).  No direct LiteLLM DB queries.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ModelUsage
from deps import get_db
from pagination import build_paginated_response

router = APIRouter(tags=["Model Usage"])


_TEST_MODEL_NAMES = {"test-model", "test_model"}
_TEST_PROVIDERS = {"pytest", "test"}


def _is_test_usage_entry(model: str | None, provider: str | None) -> bool:
    import re
    provider_l = (provider or "").strip().lower()
    model_l = (model or "").strip().lower()
    if provider_l in _TEST_PROVIDERS or model_l in _TEST_MODEL_NAMES:
        return True
    if re.search(r"-[a-f0-9]{8}$", model_l):
        return True
    return False


def _db_non_test_usage_filter():
    model_l = func.lower(func.coalesce(ModelUsage.model, ""))
    provider_l = func.lower(func.coalesce(ModelUsage.provider, ""))
    return and_(
        ~provider_l.in_(list(_TEST_PROVIDERS)),
        ~model_l.in_(list(_TEST_MODEL_NAMES)),
        ~model_l.op("~")(r"-[a-f0-9]{8}$"),
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/model-usage")
async def get_model_usage(
    page: int = 1,
    limit: int = 50,
    hours: int | None = None,
    model: str | None = None,
    provider: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Model usage from aria_data.model_usage (single source of truth)."""
    cutoff: datetime | None = None
    if hours is not None and int(hours) > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=int(hours))

    stmt = (
        select(ModelUsage)
        .where(_db_non_test_usage_filter())
        .order_by(ModelUsage.created_at.desc())
    )
    if cutoff is not None:
        stmt = stmt.where(ModelUsage.created_at > cutoff)
    if model:
        stmt = stmt.where(func.lower(ModelUsage.model) == model.lower())
    if provider:
        stmt = stmt.where(func.lower(ModelUsage.provider) == provider.lower())

    # Count total for pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    offset = (max(1, page) - 1) * limit
    page_stmt = stmt.offset(offset).limit(limit)
    rows = (await db.execute(page_stmt)).scalars().all()

    items = []
    for r in rows:
        if _is_test_usage_entry(r.model, r.provider):
            continue
        items.append({
            "id": str(r.id),
            "model": r.model,
            "provider": r.provider,
            "input_tokens": r.input_tokens or 0,
            "output_tokens": r.output_tokens or 0,
            "total_tokens": (r.input_tokens or 0) + (r.output_tokens or 0),
            "cost_usd": float(r.cost_usd) if r.cost_usd else 0,
            "latency_ms": r.latency_ms,
            "success": r.success,
            "error_message": r.error_message,
            "session_id": str(r.session_id) if r.session_id else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "source": "engine",
        })

    return build_paginated_response(items, total, page, limit)


@router.post("/model-usage")
async def log_model_usage(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    session_id = data.get("session_id")
    usage = ModelUsage(
        id=uuid.uuid4(),
        model=data.get("model"),
        provider=data.get("provider"),
        input_tokens=data.get("input_tokens", 0),
        output_tokens=data.get("output_tokens", 0),
        cost_usd=data.get("cost_usd", 0),
        latency_ms=data.get("latency_ms"),
        success=data.get("success", True),
        error_message=data.get("error_message"),
        session_id=uuid.UUID(session_id) if session_id else None,
    )
    db.add(usage)
    await db.commit()
    return {"id": str(usage.id), "created": True}


@router.get("/model-usage/stats")
async def get_model_usage_stats(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Aggregate stats from aria_data.model_usage.  hours=0 → all time."""
    if hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        window_filter = and_(ModelUsage.created_at > cutoff, _db_non_test_usage_filter())
    else:
        window_filter = _db_non_test_usage_filter()

    # Aggregate totals
    agg_result = await db.execute(
        select(
            func.count(ModelUsage.id).label("total_requests"),
            func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(ModelUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(ModelUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(ModelUsage.cost_usd), 0).label("total_cost"),
            func.coalesce(func.avg(ModelUsage.latency_ms), 0).label("avg_latency"),
        ).where(window_filter)
    )
    agg = agg_result.one()

    total_requests = int(agg.total_requests)
    total_tokens = int(agg.total_tokens)
    total_cost = float(agg.total_cost)
    avg_latency = int(agg.avg_latency)

    # Success rate
    success_count = (
        await db.execute(
            select(func.count(ModelUsage.id))
            .where(window_filter)
            .where(ModelUsage.success.is_(True))
        )
    ).scalar() or 0
    success_rate = round(success_count / total_requests * 100, 1) if total_requests > 0 else 100

    # Per-model breakdown
    by_model_result = await db.execute(
        select(
            ModelUsage.model,
            ModelUsage.provider,
            func.count(ModelUsage.id).label("requests"),
            func.coalesce(func.sum(ModelUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(ModelUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(ModelUsage.cost_usd), 0).label("cost"),
            func.coalesce(func.avg(ModelUsage.latency_ms), 0).label("avg_latency"),
        )
        .where(window_filter)
        .group_by(ModelUsage.model, ModelUsage.provider)
        .order_by(func.count(ModelUsage.id).desc())
    )
    by_model_list = [
        {
            "model": r[0],
            "provider": r[1],
            "requests": r[2],
            "input_tokens": r[3],
            "output_tokens": r[4],
            "cost": float(r[5]),
            "avg_latency": int(r[6]),
            "source": "engine",
        }
        for r in by_model_result.all()
    ]

    return {
        "period_hours": hours,
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "input_tokens": int(agg.input_tokens),
        "output_tokens": int(agg.output_tokens),
        "total_cost": total_cost,
        "avg_latency_ms": avg_latency,
        "success_rate": success_rate,
        "by_model": by_model_list,
        "sources": {
            "engine": {
                "requests": total_requests,
                "tokens": total_tokens,
                "cost": total_cost,
            },
        },
    }
