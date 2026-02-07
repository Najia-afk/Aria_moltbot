from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


CATALOG_PATH = Path(__file__).resolve().parent / "models.yaml"


def _load_yaml_or_json(path: Path) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    # JSON is valid YAML; parse JSON first for zero dependencies.
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyYAML not installed and JSON parse failed") from exc
        return yaml.safe_load(content) or {}


@lru_cache(maxsize=1)
def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    catalog_path = path or CATALOG_PATH
    if not catalog_path.exists():
        return {}
    return _load_yaml_or_json(catalog_path)


def normalize_model_id(model_id: str) -> str:
    if not model_id:
        return model_id
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def get_model_entry(model_id: str, catalog: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    catalog = catalog or load_catalog()
    models = catalog.get("models", {}) if catalog else {}
    normalized = normalize_model_id(model_id)
    return models.get(normalized)


def get_route_skill(model_id: str, catalog: Optional[Dict[str, Any]] = None) -> Optional[str]:
    entry = get_model_entry(model_id, catalog=catalog)
    if not entry:
        return None
    return entry.get("routeSkill")


def get_focus_default(focus_type: str, catalog: Optional[Dict[str, Any]] = None) -> Optional[str]:
    catalog = catalog or load_catalog()
    criteria = catalog.get("criteria", {}) if catalog else {}
    focus_defaults = criteria.get("focus_defaults", {}) if criteria else {}
    return focus_defaults.get(focus_type)


def build_litellm_models(catalog: Optional[Dict[str, Any]] = None) -> list[dict[str, Any]]:
    catalog = catalog or load_catalog()
    models = catalog.get("models", {}) if catalog else {}
    result: list[dict[str, Any]] = []
    for model_id, entry in models.items():
        if entry.get("provider") != "litellm":
            continue
        # maxTokens MUST be a positive integer — OpenClaw UI sends NaN for
        # empty fields, and Zod's z.coerce.number().positive() rejects NaN
        # which blocks config.set entirely (breaking cron display + model save).
        # Providing an explicit value prevents NaN round-trips.
        ctx = entry.get("contextWindow", 8192)
        max_tok = entry.get("maxTokens") or min(8192, ctx)
        result.append({
            "id": model_id,
            "name": entry.get("name", model_id),
            "reasoning": entry.get("reasoning", False),
            "input": entry.get("input", ["text"]),
            "cost": entry.get("cost", {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}),
            "contextWindow": ctx,
            "maxTokens": max_tok,
        })
    return result


def build_agent_aliases(catalog: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    catalog = catalog or load_catalog()
    aliases = catalog.get("agent_aliases", {}) if catalog else {}
    return {key: {"alias": value} for key, value in aliases.items()}


def build_agent_routing(catalog: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build agent model routing (primary + fallbacks only).
    
    Note: OpenClaw expects model object to contain ONLY primary and fallbacks.
    Timeout should be set at agents.defaults.timeoutSeconds level, not in model object.
    """
    catalog = catalog or load_catalog()
    routing = catalog.get("routing", {}) if catalog else {}
    return {
        "primary": routing.get("primary"),
        "fallbacks": routing.get("fallbacks", []),
    }


def list_all_model_ids(catalog: Optional[Dict[str, Any]] = None) -> list[str]:
    """Return all model IDs from the catalog (including aliases)."""
    catalog = catalog or load_catalog()
    models = catalog.get("models", {}) if catalog else {}
    ids: list[str] = []
    for model_id, entry in models.items():
        ids.append(model_id)
        for alias in entry.get("aliases", []):
            ids.append(alias)
    return ids


def list_models_with_reasoning(catalog: Optional[Dict[str, Any]] = None) -> list[str]:
    """Return model IDs that support reasoning/thinking mode."""
    catalog = catalog or load_catalog()
    models = catalog.get("models", {}) if catalog else {}
    return [mid for mid, entry in models.items() if entry.get("reasoning")]


def build_litellm_config_entries(catalog: Optional[Dict[str, Any]] = None) -> list[dict[str, Any]]:
    """Generate litellm model_list entries from models.yaml.
    
    Each model with a 'litellm' key produces one entry (plus one per alias).
    This is the bridge that means you only need to edit models.yaml to add a model.
    """
    catalog = catalog or load_catalog()
    models = catalog.get("models", {}) if catalog else {}
    entries: list[dict[str, Any]] = []
    
    for model_id, entry in models.items():
        litellm_params = entry.get("litellm")
        if not litellm_params:
            continue
        
        item: dict[str, Any] = {
            "model_name": model_id,
            "litellm_params": dict(litellm_params),  # copy
            "model_info": {
                # max_tokens = output token cap, NOT context window
                "max_tokens": entry.get("maxTokens") or min(8192, entry.get("contextWindow", 8192)),
            },
        }
        cost = entry.get("cost", {})
        if cost.get("input", 0) == 0 and cost.get("output", 0) == 0:
            item["model_info"]["input_cost_per_token"] = 0
            item["model_info"]["output_cost_per_token"] = 0
        entries.append(item)
        
        # Also emit alias entries (e.g. kimi-k2.5 → same litellm_params)
        for alias in entry.get("aliases", []):
            alias_item = {
                "model_name": alias,
                "litellm_params": dict(litellm_params),
                "model_info": dict(item["model_info"]),
            }
            entries.append(alias_item)
    
    return entries


def get_timeout_seconds(catalog: Optional[Dict[str, Any]] = None) -> int:
    """Get timeout from routing config (for agents.defaults.timeoutSeconds)."""
    catalog = catalog or load_catalog()
    routing = catalog.get("routing", {}) if catalog else {}
    return routing.get("timeout", 600)  # Default 600s per OpenClaw docs
