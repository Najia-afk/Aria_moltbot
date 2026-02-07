"""
Model catalog endpoint — serves models.yaml as the single source of truth.

- GET /models/config → full model catalog (pricing, tiers, providers, routing)
- GET /models/pricing → pricing-only view (for lightweight frontend cost calc)

The catalog is read from models.yaml at startup and cached.
To add a new model (Gemini, Claude, etc.) → edit models.yaml only.
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(tags=["Models"])

# ── Catalog loader ───────────────────────────────────────────────────────────

# models.yaml location: mounted at /models/models.yaml in Docker,
# or fallback to ../../aria_models/models.yaml for local dev.
_CATALOG_PATHS = [
    Path("/models/models.yaml"),                          # Docker mount
    Path(__file__).resolve().parent.parent.parent.parent / "aria_models" / "models.yaml",  # local dev
]

_catalog_cache: Dict[str, Any] | None = None


def _load_catalog() -> Dict[str, Any]:
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
                except Exception:
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


@router.get("/models/pricing")
async def api_models_pricing():
    """Lightweight pricing-only view for frontend cost calculations.

    Returns {model_id: {input, output, tier}} for every model + aliases.
    """
    catalog = _load_catalog()
    models_raw = catalog.get("models", {})
    pricing: Dict[str, Any] = {}

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
