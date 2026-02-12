from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from aria_models.loader import (
    build_agent_aliases,
    build_agent_routing,
    build_litellm_models,
    get_timeout_seconds,
    load_catalog,
)


def _non_tool_model_refs(catalog: Dict[str, Any]) -> set[str]:
    models = catalog.get("models", {}) if isinstance(catalog, dict) else {}
    refs: set[str] = set()
    for model_id, cfg in models.items():
        if cfg.get("tool_calling") is False:
            refs.add(f"litellm/{model_id}")
    return refs


def _filter_fallbacks(model_cfg: Dict[str, Any], blocked_refs: set[str]) -> None:
    if not isinstance(model_cfg, dict):
        return
    fallbacks = model_cfg.get("fallbacks")
    if not isinstance(fallbacks, list):
        return
    model_cfg["fallbacks"] = [ref for ref in fallbacks if ref not in blocked_refs]


def render_openclaw_config(template_path: Path, models_path: Path, output_path: Path) -> None:
    template = json.loads(template_path.read_text(encoding="utf-8"))
    catalog = load_catalog(models_path)
    blocked_non_tool_refs = _non_tool_model_refs(catalog)

    # Agents routing + aliases
    agents_defaults = template.setdefault("agents", {}).setdefault("defaults", {})
    agents_defaults["model"] = build_agent_routing(catalog)
    _filter_fallbacks(agents_defaults.get("model", {}), blocked_non_tool_refs)
    agents_defaults["models"] = build_agent_aliases(catalog)
    
    # Set timeoutSeconds at agents.defaults level (not in model object)
    agents_defaults["timeoutSeconds"] = get_timeout_seconds(catalog)

    for agent in template.setdefault("agents", {}).get("list", []) or []:
        _filter_fallbacks(agent.get("model", {}), blocked_non_tool_refs)

    # NOTE: Do NOT inject systemPrompt into agents.defaults — OpenClaw 2026.2.6+
    # rejects it as an unrecognized key and crashes. The system identity is
    # already in agents.list[].identity.theme (the supported config path).
    # The BOOTSTRAP.md content is read by Aria at runtime via the theme directive.

    # Providers config
    providers = template.setdefault("models", {}).setdefault("providers", {})
    litellm = providers.setdefault("litellm", {})
    provider_cfg = catalog.get("providers", {}).get("litellm", {}) if catalog else {}
    if provider_cfg:
        litellm["baseUrl"] = provider_cfg.get("baseUrl", litellm.get("baseUrl"))
        litellm["apiKey"] = provider_cfg.get("apiKey", litellm.get("apiKey"))
        litellm["api"] = provider_cfg.get("api", litellm.get("api"))

    litellm["models"] = build_litellm_models(catalog)

    output_path.write_text(json.dumps(template, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    render_openclaw_config(Path(args.template), Path(args.models), Path(args.output))


if __name__ == "__main__":
    main()
