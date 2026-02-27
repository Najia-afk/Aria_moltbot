"""
LiteLLM proxy endpoints — models, health, spend, global-spend.

Spend endpoints query the LiteLLM PostgreSQL database directly instead of
the HTTP proxy, which OOMs / times out with 15K+ spend rows.
"""

import logging
import os

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import LITELLM_MASTER_KEY, SERVICE_URLS
from deps import get_litellm_db

logger = logging.getLogger("aria.api.litellm")
router = APIRouter(tags=["LiteLLM"])


def _litellm_base() -> str:
    return SERVICE_URLS.get("litellm", (os.getenv("LITELLM_URL", "http://litellm:4000"),))[0]


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}


@router.get("/litellm/models")
async def api_litellm_models():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_litellm_base()}/models", headers=_auth_headers())
            return resp.json()
    except Exception as e:
        return {"data": [], "error": str(e)}


@router.get("/litellm/health")
async def api_litellm_health():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_litellm_base()}/health/liveliness", headers=_auth_headers())
            return {"status": "healthy"} if resp.status_code == 200 else {"status": "unhealthy"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.get("/litellm/spend")
async def api_litellm_spend(
    limit: int = 50,
    offset: int = 0,
    lite: bool = False,
    db: AsyncSession = Depends(get_litellm_db),
):
    """Fetch spend logs directly from the LiteLLM PostgreSQL database."""
    try:
        count_result = await db.execute(
            text('SELECT COUNT(*) FROM "LiteLLM_SpendLogs"')
        )
        total = count_result.scalar() or 0

        if lite:
            cols = """model, model_group, prompt_tokens, completion_tokens, total_tokens,
                      spend, "startTime", "endTime", status"""
        else:
            cols = """request_id, call_type, model, model_group,
                      custom_llm_provider, prompt_tokens, completion_tokens,
                      total_tokens, spend, "startTime", "endTime", status,
                      api_base, cache_hit, session_id"""

        result = await db.execute(
            text(f"""
                SELECT {cols}
                FROM "LiteLLM_SpendLogs"
                ORDER BY "startTime" DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset},
        )
        rows = result.mappings().all()
        logs = [dict(r) for r in rows]

        return {"logs": logs, "total": total, "offset": offset, "limit": limit}
    except Exception as e:
        return {"logs": [], "total": 0, "error": str(e)}


@router.get("/litellm/global-spend")
async def api_litellm_global_spend(db: AsyncSession = Depends(get_litellm_db)):
    """Aggregate spend stats directly from the LiteLLM PostgreSQL database."""
    try:
        result = await db.execute(text("""
            SELECT
                COALESCE(SUM(spend), 0)             AS total_spend,
                COALESCE(SUM(total_tokens), 0)      AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0)     AS input_tokens,
                COALESCE(SUM(completion_tokens), 0) AS output_tokens,
                COUNT(*)                            AS api_requests
            FROM "LiteLLM_SpendLogs"
        """))
        row = result.mappings().one()

        # Try LiteLLM proxy for max_budget (lightweight call)
        max_budget = 0
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{_litellm_base()}/global/spend", headers=_auth_headers()
                )
                if resp.status_code == 200:
                    max_budget = resp.json().get("max_budget", 0) or 0
        except Exception as e:
            logger.debug("Failed to fetch max_budget from LiteLLM proxy: %s", e)

        return {
            "spend": float(row["total_spend"]),
            "max_budget": max_budget,
            "total_tokens": int(row["total_tokens"]),
            "input_tokens": int(row["input_tokens"]),
            "output_tokens": int(row["output_tokens"]),
            "api_requests": int(row["api_requests"]),
        }
    except Exception as e:
        return {
            "spend": 0, "total_tokens": 0, "input_tokens": 0,
            "output_tokens": 0, "api_requests": 0, "error": str(e),
        }
