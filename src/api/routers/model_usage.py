"""
Model usage endpoints — merged skill tracking (DB) + LiteLLM spend logs.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import LITELLM_MASTER_KEY, SERVICE_URLS
from db.models import ModelUsage
from deps import get_db

router = APIRouter(tags=["Model Usage"])


# ── LiteLLM helper ──────────────────────────────────────────────────────────

async def _fetch_litellm_spend_logs(limit: int = 200) -> list[dict]:
    """Fetch spend logs from LiteLLM proxy. Returns normalized records."""
    litellm_base = SERVICE_URLS.get("litellm", ("http://litellm:4000",))[0]
    try:
        headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{litellm_base}/spend/logs", headers=headers)
            if resp.status_code != 200:
                return []
            logs = resp.json()
            if not isinstance(logs, list):
                return []
            results = []
            for log in logs[:limit]:
                meta = log.get("metadata", {}) or {}
                model_raw = log.get("model", "") or ""
                model_group = log.get("model_group", "") or ""
                display_model = model_group or (model_raw.split("/")[-1] if "/" in model_raw else model_raw)
                provider = log.get("custom_llm_provider", "") or (
                    model_raw.split("/")[0] if "/" in model_raw else "litellm"
                )
                status = meta.get("status", "success")
                results.append({
                    "id": log.get("request_id", ""),
                    "model": display_model,
                    "provider": provider,
                    "input_tokens": log.get("prompt_tokens", 0) or 0,
                    "output_tokens": log.get("completion_tokens", 0) or 0,
                    "total_tokens": log.get("total_tokens", 0) or 0,
                    "cost_usd": float(log.get("spend", 0) or 0),
                    "latency_ms": None,
                    "success": status == "success",
                    "error_message": None if status == "success" else status,
                    "session_id": log.get("session_id"),
                    "created_at": log.get("startTime"),
                    "source": "litellm",
                })
            return results
    except Exception as e:
        print(f"⚠️ Failed to fetch LiteLLM spend: {e}")
        return []


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/model-usage")
async def get_model_usage(
    limit: int = 100,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    source: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Merged model usage from skill executions (DB) + LLM calls (LiteLLM)."""
    results: list[dict] = []

    # 1. DB skill executions
    if source in (None, "", "skills", "all"):
        stmt = select(ModelUsage).order_by(ModelUsage.created_at.desc()).limit(limit)
        if model:
            stmt = stmt.where(ModelUsage.model == model)
        if provider:
            stmt = stmt.where(ModelUsage.provider == provider)
        rows = (await db.execute(stmt)).scalars().all()
        for r in rows:
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

    # 2. LiteLLM logs
    if source in (None, "", "litellm", "all"):
        litellm_logs = await _fetch_litellm_spend_logs(limit=limit)
        if model:
            litellm_logs = [l for l in litellm_logs if model.lower() in (l.get("model") or "").lower()]
        if provider:
            litellm_logs = [l for l in litellm_logs if provider.lower() in (l.get("provider") or "").lower()]
        results.extend(litellm_logs)

    results.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return {"usage": results[:limit], "count": min(len(results), limit)}


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
    hours: int = 24, db: AsyncSession = Depends(get_db)
):
    """Stats merging skill executions (DB) + LLM calls (LiteLLM)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()

    # 1. DB stats
    window_filter = ModelUsage.created_at > cutoff
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

    # 2. LiteLLM stats
    litellm_logs = await _fetch_litellm_spend_logs(limit=5000)
    llm_in_window = [l for l in litellm_logs if (l.get("created_at") or "") >= cutoff_iso]
    llm_total = len(llm_in_window)
    llm_tokens = sum(l.get("total_tokens", 0) for l in llm_in_window)
    llm_cost = sum(l.get("cost_usd", 0) for l in llm_in_window)

    for l in llm_in_window:
        model_name = l.get("model") or "unknown"
        if model_name in by_model_map:
            entry = by_model_map[model_name]
            entry["requests"] += 1
            entry["input_tokens"] += l.get("input_tokens", 0)
            entry["output_tokens"] += l.get("output_tokens", 0)
            entry["cost"] += l.get("cost_usd", 0)
            entry["source"] = "merged"
        else:
            by_model_map[model_name] = {
                "model": model_name, "provider": l.get("provider", "litellm"),
                "requests": 1, "input_tokens": l.get("input_tokens", 0),
                "output_tokens": l.get("output_tokens", 0),
                "cost": l.get("cost_usd", 0), "avg_latency": 0, "source": "litellm",
            }

    by_model_list = sorted(by_model_map.values(), key=lambda x: x["requests"], reverse=True)

    return {
        "period_hours": hours,
        "total_requests": db_total + llm_total,
        "total_tokens": db_tokens + llm_tokens,
        "total_cost": float(db_cost) + llm_cost,
        "avg_latency_ms": int(db_latency),
        "success_rate": 100,
        "by_model": by_model_list,
        "sources": {
            "skills": {"requests": db_total, "tokens": db_tokens, "cost": float(db_cost)},
            "litellm": {"requests": llm_total, "tokens": llm_tokens, "cost": llm_cost},
        },
    }
