"""
Provider balance endpoints — Moonshot/Kimi, OpenRouter, local models.
"""

import httpx
from fastapi import APIRouter

from config import MOONSHOT_KIMI_KEY, OPEN_ROUTER_KEY

router = APIRouter(tags=["Providers"])


@router.get("/providers/balances")
async def api_provider_balances():
    balances: dict = {}

    # Moonshot / Kimi
    if MOONSHOT_KIMI_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {MOONSHOT_KIMI_KEY}"}
                resp = await client.get("https://api.moonshot.ai/v1/users/me/balance", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    balances["kimi"] = {
                        "provider": "Moonshot/Kimi",
                        "available": data.get("data", {}).get("available_balance", 0),
                        "voucher": data.get("data", {}).get("voucher_balance", 0),
                        "cash": data.get("data", {}).get("cash_balance", 0),
                        "currency": "CNY",
                        "status": "ok",
                    }
                else:
                    balances["kimi"] = {"provider": "Moonshot/Kimi", "status": "error", "code": resp.status_code}
        except Exception as e:
            balances["kimi"] = {"provider": "Moonshot/Kimi", "status": "error", "error": str(e)}

    # OpenRouter
    if OPEN_ROUTER_KEY:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {"Authorization": f"Bearer {OPEN_ROUTER_KEY}"}
                resp = await client.get("https://openrouter.ai/api/v1/auth/key", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    limit_val = data.get("data", {}).get("limit")
                    usage_val = data.get("data", {}).get("usage") or 0
                    remaining = (limit_val - usage_val) if limit_val is not None else (-usage_val if usage_val > 0 else 0)
                    balances["openrouter"] = {
                        "provider": "OpenRouter",
                        "limit": limit_val,
                        "usage": usage_val,
                        "remaining": remaining,
                        "is_free_tier": limit_val is None,
                        "currency": "USD",
                        "status": "ok",
                    }
                else:
                    balances["openrouter"] = {"provider": "OpenRouter", "status": "error", "code": resp.status_code}
        except Exception as e:
            balances["openrouter"] = {"provider": "OpenRouter", "status": "error", "error": str(e)}
    else:
        balances["openrouter"] = {"provider": "OpenRouter", "status": "free_tier", "note": "Using free models only"}

    # Local models (free)
    balances["local"] = {
        "provider": "Local (MLX/Ollama)",
        "status": "free",
        "note": "No cost - runs on local hardware",
    }
    return balances
