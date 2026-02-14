"""
Model usage endpoints — merged skill tracking (DB) + LiteLLM spend logs.

LiteLLM spend is queried directly from its PostgreSQL database (same PG
instance, separate 'litellm' database) instead of the HTTP proxy which
OOMs/times out with 15K+ rows.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config import LITELLM_MASTER_KEY, SERVICE_URLS
from db.models import ModelUsage
from deps import get_db, get_litellm_db
from pagination import build_paginated_response

router = APIRouter(tags=["Model Usage"])


_TEST_MODEL_NAMES = {"test-model", "test_model"}


def _is_test_usage_entry(model: Optional[str], provider: Optional[str]) -> bool:
    provider_l = (provider or "").strip().lower()
    model_l = (model or "").strip().lower()
    return provider_l == "pytest" or model_l in _TEST_MODEL_NAMES


def _db_non_test_usage_filter():
    model_l = func.lower(func.coalesce(ModelUsage.model, ""))
    provider_l = func.lower(func.coalesce(ModelUsage.provider, ""))
    return and_(provider_l != "pytest", ~model_l.in_(list(_TEST_MODEL_NAMES)))


# ── LiteLLM helper (direct DB) ──────────────────────────────────────────────

async def _fetch_litellm_spend_logs(
    db: AsyncSession,
    limit: int = 200,
    since: Optional[datetime] = None,
) -> list[dict]:
    """Fetch spend logs directly from the LiteLLM PostgreSQL database."""
    try:
        params: dict = {"limit": limit}
        where_clause = ""
        if since:
            where_clause = 'WHERE "startTime" >= :since'
            params["since"] = since

        result = await db.execute(
            text(f"""
                SELECT request_id, model, model_group, custom_llm_provider,
                       prompt_tokens, completion_tokens, total_tokens,
                       spend, "startTime", status, session_id, metadata
                FROM "LiteLLM_SpendLogs"
                {where_clause}
                ORDER BY "startTime" DESC
                LIMIT :limit
            """),
            params,
        )
        rows = result.mappings().all()

        results = []
        for log in rows:
            model_raw = log.get("model") or ""
            model_group = log.get("model_group") or ""
            display_model = model_group or (model_raw.split("/")[-1] if "/" in model_raw else model_raw)
            provider = log.get("custom_llm_provider") or (
                model_raw.split("/")[0] if "/" in model_raw else "litellm"
            )
            meta = log.get("metadata") or {}
            status = meta.get("status", "success") if isinstance(meta, dict) else "success"
            start_time = log.get("startTime")

            results.append({
                "id": log.get("request_id") or "",
                "model": display_model,
                "provider": provider,
                "input_tokens": log.get("prompt_tokens") or 0,
                "output_tokens": log.get("completion_tokens") or 0,
                "total_tokens": log.get("total_tokens") or 0,
                "cost_usd": float(log.get("spend") or 0),
                "latency_ms": None,
                "success": status == "success",
                "error_message": None if status == "success" else status,
                "session_id": log.get("session_id"),
                "created_at": start_time.isoformat() if start_time else None,
                "source": "litellm",
            })
        return results
    except Exception as e:
        print(f"⚠️ Failed to fetch LiteLLM spend from DB: {e}")
        return []


async def _litellm_aggregate_stats(
    db: AsyncSession,
    since: Optional[datetime] = None,
) -> dict:
    """Aggregate LiteLLM stats directly from the DB."""
    try:
        params: dict = {}
        where_clause = ""
        if since:
            where_clause = 'WHERE "startTime" >= :since'
            params["since"] = since

        result = await db.execute(
            text(f"""
                SELECT
                    COUNT(*)                            AS total_requests,
                    COALESCE(SUM(total_tokens), 0)      AS total_tokens,
                    COALESCE(SUM(prompt_tokens), 0)     AS input_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS output_tokens,
                    COALESCE(SUM(spend), 0)             AS total_cost
                FROM "LiteLLM_SpendLogs"
                {where_clause}
            """),
            params,
        )
        row = result.mappings().one()
        return {
            "requests": int(row["total_requests"]),
            "tokens": int(row["total_tokens"]),
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
            "cost": float(row["total_cost"]),
        }
    except Exception as e:
        print(f"⚠️ Failed to aggregate LiteLLM stats: {e}")
        return {"requests": 0, "tokens": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0}


async def _litellm_by_model_stats(
    db: AsyncSession,
    since: Optional[datetime] = None,
) -> list[dict]:
    """Per-model aggregation from LiteLLM DB."""
    try:
        params: dict = {}
        where_clause = ""
        if since:
            where_clause = 'WHERE "startTime" >= :since'
            params["since"] = since

        result = await db.execute(
            text(f"""
                SELECT
                    COALESCE(NULLIF(model_group, ''), model) AS display_model,
                    COALESCE(NULLIF(custom_llm_provider, ''), 'litellm') AS provider,
                    COUNT(*)                                AS requests,
                    COALESCE(SUM(prompt_tokens), 0)         AS input_tokens,
                    COALESCE(SUM(completion_tokens), 0)     AS output_tokens,
                    COALESCE(SUM(spend), 0)                 AS cost
                FROM "LiteLLM_SpendLogs"
                {where_clause}
                GROUP BY display_model, provider
                ORDER BY requests DESC
            """),
            params,
        )
        return [dict(r) for r in result.mappings().all()]
    except Exception as e:
        print(f"⚠️ Failed to get LiteLLM by-model stats: {e}")
        return []


def _litellm_fallback_from_logs(logs: list[dict]) -> tuple[dict, list[dict]]:
    """Build aggregate + per-model stats from raw LiteLLM logs as a safe fallback."""
    agg = {
        "requests": 0,
        "tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cost": 0.0,
    }
    by_model: dict[tuple[str, str], dict] = {}

    for log in logs:
        model_name = (log.get("model") or "unknown").strip() or "unknown"
        provider = (log.get("provider") or "litellm").strip() or "litellm"
        input_tokens = int(log.get("input_tokens") or 0)
        output_tokens = int(log.get("output_tokens") or 0)
        total_tokens = int(log.get("total_tokens") or (input_tokens + output_tokens))
        cost = float(log.get("cost_usd") or 0)

        agg["requests"] += 1
        agg["tokens"] += total_tokens
        agg["input_tokens"] += input_tokens
        agg["output_tokens"] += output_tokens
        agg["cost"] += cost

        key = (model_name, provider)
        if key not in by_model:
            by_model[key] = {
                "model": model_name,
                "provider": provider,
                "requests": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost": 0.0,
                "avg_latency": 0,
                "source": "litellm",
            }

        bucket = by_model[key]
        bucket["requests"] += 1
        bucket["input_tokens"] += input_tokens
        bucket["output_tokens"] += output_tokens
        bucket["cost"] += cost

    return agg, sorted(by_model.values(), key=lambda x: x["requests"], reverse=True)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/model-usage")
async def get_model_usage(
    page: int = 1,
    limit: int = 50,
    hours: Optional[int] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    litellm_db: AsyncSession = Depends(get_litellm_db),
):
    """Merged model usage from skill executions (DB) + LLM calls (LiteLLM)."""
    results: list[dict] = []
    cutoff: Optional[datetime] = None
    if hours is not None and int(hours) > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=int(hours))

    # 1. DB skill executions
    if source in (None, "", "skills", "all"):
        stmt = select(ModelUsage).where(_db_non_test_usage_filter()).order_by(ModelUsage.created_at.desc()).limit(limit)
        if cutoff is not None:
            stmt = stmt.where(ModelUsage.created_at > cutoff)
        if model:
            stmt = stmt.where(ModelUsage.model == model)
        if provider:
            stmt = stmt.where(ModelUsage.provider == provider)
        rows = (await db.execute(stmt)).scalars().all()
        for r in rows:
            if _is_test_usage_entry(r.model, r.provider):
                continue
            results.append({
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
                "source": "skills",
            })

    # 2. LiteLLM logs (direct DB query)
    if source in (None, "", "litellm", "all"):
        litellm_logs = await _fetch_litellm_spend_logs(litellm_db, limit=limit, since=cutoff)
        if model:
            litellm_logs = [l for l in litellm_logs if model.lower() in (l.get("model") or "").lower()]
        if provider:
            litellm_logs = [l for l in litellm_logs if provider.lower() in (l.get("provider") or "").lower()]
        results.extend(litellm_logs)

    results.sort(key=lambda x: x.get("created_at") or "", reverse=True)

    # Paginate the merged results
    total = len(results)
    offset = (max(1, page) - 1) * limit
    page_items = results[offset:offset + limit]
    return build_paginated_response(page_items, total, page, limit)


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
    litellm_db: AsyncSession = Depends(get_litellm_db),
):
    """Stats merging skill executions (DB) + LLM calls (LiteLLM)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # 1. DB stats
    window_filter = and_(ModelUsage.created_at > cutoff, _db_non_test_usage_filter())
    db_total = (
        await db.execute(select(func.count(ModelUsage.id)).where(window_filter))
    ).scalar() or 0
    db_tokens = (
        await db.execute(
            select(func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0))
            .where(window_filter)
        )
    ).scalar() or 0
    db_cost = (
        await db.execute(
            select(func.coalesce(func.sum(ModelUsage.cost_usd), 0)).where(window_filter)
        )
    ).scalar() or 0
    db_latency = (
        await db.execute(
            select(func.coalesce(func.avg(ModelUsage.latency_ms), 0))
            .where(window_filter)
            .where(ModelUsage.latency_ms.isnot(None))
        )
    ).scalar() or 0

    db_by_model_result = await db.execute(
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
    by_model_map: dict[str, dict] = {}
    for r in db_by_model_result.all():
        by_model_map[r[0]] = {
            "model": r[0], "provider": r[1], "requests": r[2],
            "input_tokens": r[3], "output_tokens": r[4],
            "cost": float(r[5]), "avg_latency": int(r[6]), "source": "skills",
        }

    # 2. LiteLLM stats (direct DB aggregation — no more HTTP proxy)
    llm_agg = await _litellm_aggregate_stats(litellm_db, since=cutoff)
    llm_by_model = await _litellm_by_model_stats(litellm_db, since=cutoff)

    # Fallback path: derive stats from raw logs when aggregate/group queries fail
    # or return empty due schema drift/permission issues.
    if not llm_by_model or int(llm_agg.get("requests", 0)) == 0:
        fallback_logs = await _fetch_litellm_spend_logs(litellm_db, limit=5000, since=cutoff)
        if fallback_logs:
            fallback_agg, fallback_by_model = _litellm_fallback_from_logs(fallback_logs)
            if int(llm_agg.get("requests", 0)) == 0:
                llm_agg = fallback_agg
            if not llm_by_model:
                llm_by_model = [
                    {
                        "display_model": item["model"],
                        "provider": item["provider"],
                        "requests": item["requests"],
                        "input_tokens": item["input_tokens"],
                        "output_tokens": item["output_tokens"],
                        "cost": item["cost"],
                    }
                    for item in fallback_by_model
                ]

    for entry in llm_by_model:
        model_name = entry.get("display_model") or "unknown"
        if model_name in by_model_map:
            existing = by_model_map[model_name]
            existing["requests"] += entry.get("requests", 0)
            existing["input_tokens"] += entry.get("input_tokens", 0)
            existing["output_tokens"] += entry.get("output_tokens", 0)
            existing["cost"] += float(entry.get("cost", 0))
            existing["source"] = "merged"
        else:
            by_model_map[model_name] = {
                "model": model_name, "provider": entry.get("provider", "litellm"),
                "requests": entry.get("requests", 0),
                "input_tokens": entry.get("input_tokens", 0),
                "output_tokens": entry.get("output_tokens", 0),
                "cost": float(entry.get("cost", 0)), "avg_latency": 0, "source": "litellm",
            }

    by_model_list = sorted(by_model_map.values(), key=lambda x: x["requests"], reverse=True)

    return {
        "period_hours": hours,
        "total_requests": db_total + llm_agg["requests"],
        "total_tokens": db_tokens + llm_agg["tokens"],
        "total_cost": float(db_cost) + llm_agg["cost"],
        "avg_latency_ms": int(db_latency),
        "success_rate": 100,
        "by_model": by_model_list,
        "sources": {
            "skills": {"requests": db_total, "tokens": db_tokens, "cost": float(db_cost)},
            "litellm": {"requests": llm_agg["requests"], "tokens": llm_agg["tokens"], "cost": llm_agg["cost"]},
        },
    }
