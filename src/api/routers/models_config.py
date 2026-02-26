"""
Model catalog endpoint — serves models.yaml as the single source of truth.

- GET /models/config → full model catalog (pricing, tiers, providers, routing)
- GET /models/pricing → pricing-only view (for lightweight frontend cost calc)

The catalog is read from models.yaml at startup and cached.
To add a new model (Gemini, Claude, etc.) → edit models.yaml only.
"""

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger("aria.api.models_config")
router = APIRouter(tags=["Models"])

# ── Catalog loader ───────────────────────────────────────────────────────────

# models.yaml location: mounted at /models/models.yaml in Docker,
# or fallback to ../../aria_models/models.yaml for local dev.
_CATALOG_PATHS = [
    Path("/models/models.yaml"),                          # Docker mount
    Path(__file__).resolve().parent.parent.parent.parent / "aria_models" / "models.yaml",  # local dev
]

_catalog_cache: dict[str, Any] | None = None


def _load_catalog() -> dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    for p in _CATALOG_PATHS:
        if p.exists():
            content = p.read_text(encoding="utf-8")
            try:
                _catalog_cache = json.loads(content)
            except json.JSONDecodeError:
                try:
                    import yaml
                    _catalog_cache = yaml.safe_load(content) or {}
                except Exception as e:
                    logger.warning("Model catalog YAML parse error: %s", e)
                    _catalog_cache = {}
            return _catalog_cache
    _catalog_cache = {}
    return _catalog_cache


def reload_catalog():
    """Force re-read of models.yaml (e.g. after admin update)."""
    global _catalog_cache
    _catalog_cache = None
    return _load_catalog()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/models/config")
async def api_models_config():
    """Full model catalog — providers, routing, models with pricing & tiers.

    Frontend caches this and derives all pricing/provider info dynamically.
    Adding a new model to models.yaml auto-exposes it here.
    """
    catalog = _load_catalog()
    models_raw = catalog.get("models", {})

    # Build a clean per-model response
    models = {}
    for model_id, entry in models_raw.items():
        litellm_cfg = entry.get("litellm", {})
        models[model_id] = {
            "id": model_id,
            "name": entry.get("name", model_id),
            "tier": entry.get("tier", "unknown"),
            "reasoning": entry.get("reasoning", False),
            "input_types": entry.get("input", ["text"]),
            "cost": entry.get("cost", {"input": 0, "output": 0}),
            "contextWindow": entry.get("contextWindow", 0),
            "maxTokens": entry.get("maxTokens", 0),
            "litellm_model": litellm_cfg.get("model", ""),
            "aliases": entry.get("aliases", []),
        }

    return {
        "schema_version": catalog.get("schema_version", 1),
        "routing": catalog.get("routing", {}),
        "agent_aliases": catalog.get("agent_aliases", {}),
        "criteria": catalog.get("criteria", {}),
        "models": models,
    }


@router.get("/models/available")
async def api_models_available():
    """Available models as a flat list — used by the chat UI model selector.

    Tries DB (``llm_models`` table) first, falls back to models.yaml.
    Returns ``{"models": [...]}``, each entry carrying ``provider``,
    ``id``, ``name``, ``tier``, context info and capability flags so
    the frontend can group by provider without extra transformation.
    """
    # ── Try DB first ─────────────────────────────────────────────
    try:
        from db.models import LlmModelEntry
        from db import AsyncSessionLocal
        from sqlalchemy import select as sa_select

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                sa_select(LlmModelEntry)
                .where(LlmModelEntry.enabled == True)  # noqa: E712
                .order_by(LlmModelEntry.sort_order.asc(), LlmModelEntry.name.asc())
            )
            rows = result.scalars().all()
            if rows:
                models_list = [
                    {
                        "id": r.id,
                        "model_id": r.id,
                        "name": r.name,
                        "provider": r.provider,
                        "tier": r.tier,
                        "reasoning": r.reasoning,
                        "input_types": r.input_types or ["text"],
                        "context_length": r.context_window,
                        "max_tokens": r.max_tokens,
                        "litellm_model": r.litellm_model or "",
                        "tool_calling": r.tool_calling,
                        "thinking": r.reasoning,
                        "vision": r.vision,
                        "display_name": r.name,
                        "cost_input": float(r.cost_input or 0),
                        "cost_output": float(r.cost_output or 0),
                    }
                    for r in rows
                ]
                return {"models": models_list, "source": "db"}
    except Exception as e:
        logger.debug("DB model query failed, falling through to YAML: %s", e)

    # ── Fallback: models.yaml ────────────────────────────────────
    catalog = _load_catalog()
    models_raw = catalog.get("models", {})

    models_list: list[dict[str, Any]] = []
    for model_id, entry in models_raw.items():
        litellm_cfg = entry.get("litellm", {})
        models_list.append({
            "id": model_id,
            "model_id": model_id,
            "name": entry.get("name", model_id),
            "provider": entry.get("provider", "other"),
            "tier": entry.get("tier", "unknown"),
            "reasoning": entry.get("reasoning", False),
            "input_types": entry.get("input", ["text"]),
            "context_length": entry.get("contextWindow", 0),
            "max_tokens": entry.get("maxTokens", 0),
            "litellm_model": litellm_cfg.get("model", ""),
            "tool_calling": entry.get("tool_calling", False),
            "thinking": entry.get("reasoning", False),
            "vision": "image" in entry.get("input", []),
            "display_name": entry.get("name", model_id),
        })

    return {"models": models_list, "source": "yaml"}


@router.get("/models/pricing")
async def api_models_pricing():
    """Lightweight pricing-only view for frontend cost calculations.

    Returns {model_id: {input, output, tier}} for every model + aliases.
    """
    catalog = _load_catalog()
    models_raw = catalog.get("models", {})
    pricing: dict[str, Any] = {}

    for model_id, entry in models_raw.items():
        cost = entry.get("cost", {"input": 0, "output": 0})
        litellm_model = entry.get("litellm", {}).get("model", "")
        record = {
            "model_id": model_id,
            "input": cost.get("input", 0),
            "output": cost.get("output", 0),
            "cacheRead": cost.get("cacheRead", 0),
            "tier": entry.get("tier", "unknown"),
            "litellm_model": litellm_model,
        }
        pricing[model_id] = record
        # Also index by litellm model name for spend log matching
        if litellm_model:
            pricing[litellm_model] = record
        # Also index by aliases
        for alias in entry.get("aliases", []):
            pricing[alias] = record

    return pricing


@router.post("/models/reload")
async def api_models_reload():
    """Force reload models.yaml (admin use)."""
    catalog = reload_catalog()
    count = len(catalog.get("models", {}))
    return {"status": "reloaded", "models_count": count}
