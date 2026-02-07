"""
LiteLLM proxy endpoints — models, health, spend, global-spend.
"""

import httpx
from fastapi import APIRouter

from config import LITELLM_MASTER_KEY, SERVICE_URLS

router = APIRouter(tags=["LiteLLM"])


def _litellm_base() -> str:
    return SERVICE_URLS.get("litellm", ("http://litellm:4000",))[0]


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
async def api_litellm_spend(limit: int = 20, lite: bool = False):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_litellm_base()}/spend/logs", headers=_auth_headers())
            logs = resp.json()
            if isinstance(logs, list):
                logs = logs[:limit]
                if lite:
                    return [
                        {
                            "model": log.get("model", ""),
                            "prompt_tokens": log.get("prompt_tokens", 0),
                            "completion_tokens": log.get("completion_tokens", 0),
                            "total_tokens": log.get("total_tokens", 0),
                            "spend": log.get("spend", 0),
                            "startTime": log.get("startTime"),
                            "status": log.get("status", "success"),
                        }
                        for log in logs
                    ]
            return logs
    except Exception as e:
        return {"logs": [], "error": str(e)}


@router.get("/litellm/global-spend")
async def api_litellm_global_spend():
    try:
        headers = _auth_headers()
        async with httpx.AsyncClient(timeout=10.0) as client:
            global_resp = await client.get(f"{_litellm_base()}/global/spend", headers=headers)
            global_data = global_resp.json() if global_resp.status_code == 200 else {}

            logs_resp = await client.get(f"{_litellm_base()}/spend/logs", headers=headers)
            logs = logs_resp.json() if logs_resp.status_code == 200 else []

            total_tokens = input_tokens = output_tokens = 0
            api_requests = len(logs) if isinstance(logs, list) else 0
            if isinstance(logs, list):
                for log in logs:
                    total_tokens += log.get("total_tokens", 0) or 0
                    input_tokens += log.get("prompt_tokens", 0) or 0
                    output_tokens += log.get("completion_tokens", 0) or 0

            return {
                "spend": global_data.get("spend", 0) or 0,
                "max_budget": global_data.get("max_budget", 0) or 0,
                "total_tokens": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "api_requests": api_requests,
            }
    except Exception as e:
        return {
            "spend": 0, "total_tokens": 0, "input_tokens": 0,
            "output_tokens": 0, "api_requests": 0, "error": str(e),
        }
