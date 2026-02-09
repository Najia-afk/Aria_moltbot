from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


CATALOG_PATH = Path(__file__).resolve().parent / "models.yaml"

# TTL-based cache (replaces @lru_cache to avoid staleness)
_CACHE_TTL_SECONDS = 300  # 5 minutes
_cache: Dict[str, Any] = {}
_cache_timestamp: float = 0.0


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


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the model catalog with 5-minute TTL cache.

    The cache is invalidated after ``_CACHE_TTL_SECONDS`` or when
    ``reload_models()`` is called.
    """
    global _cache, _cache_timestamp

    now = time.monotonic()
    cache_key = str(path or CATALOG_PATH)

    if _cache and (now - _cache_timestamp) < _CACHE_TTL_SECONDS:
        if cache_key in _cache:
            return _cache[cache_key]

    catalog_path = path or CATALOG_PATH
    if not catalog_path.exists():
        return {}
    result = _load_yaml_or_json(catalog_path)
    _cache[cache_key] = result
    _cache_timestamp = now
    return result


def reload_models() -> Dict[str, Any]:
    """Clear the TTL cache and reload models.yaml from disk."""
    global _cache, _cache_timestamp
    _cache = {}
    _cache_timestamp = 0.0
    return load_catalog()


def validate_models(path: Optional[Path] = None) -> List[str]:
    """Validate models.yaml structure. Returns list of error strings (empty = valid).

    Checks:
    - File exists and is valid JSON
    - Has ``schema_version`` and ``models`` keys
    - Each model entry has required fields (provider, litellm, contextWindow)
    - litellm sub-dict has ``model`` key
    """
    errors: List[str] = []
    catalog_path = path or CATALOG_PATH

    if not catalog_path.exists():
        errors.append(f"models.yaml not found at {catalog_path}")
        return errors

    try:
        catalog = _load_yaml_or_json(catalog_path)
    except (json.JSONDecodeError, RuntimeError) as exc:
        errors.append(f"Failed to parse models.yaml: {exc}")
        return errors
    except Exception as exc:
        errors.append(f"Failed to parse models.yaml: {exc}")
        return errors

    if "schema_version" not in catalog:
        errors.append("Missing 'schema_version' key")
    if "models" not in catalog:
        errors.append("Missing 'models' key")
        return errors

    models = catalog["models"]
    if not isinstance(models, dict):
        errors.append("'models' must be a dict")
        return errors

    required_fields = {"provider", "contextWindow"}
    for model_id, entry in models.items():
        if not isinstance(entry, dict):
            errors.append(f"Model '{model_id}': entry must be a dict")
            continue
        for field in required_fields:
            if field not in entry:
                errors.append(f"Model '{model_id}': missing required field '{field}'")
        litellm_block = entry.get("litellm")
        if litellm_block is not None:
            if not isinstance(litellm_block, dict):
                errors.append(f"Model '{model_id}': 'litellm' must be a dict")
            elif "model" not in litellm_block:
                errors.append(f"Model '{model_id}': litellm block missing 'model' key")

    return errors


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
