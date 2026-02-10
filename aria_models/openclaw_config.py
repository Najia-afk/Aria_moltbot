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


def render_openclaw_config(template_path: Path, models_path: Path, output_path: Path) -> None:
    template = json.loads(template_path.read_text(encoding="utf-8"))
    catalog = load_catalog(models_path)

    # Agents routing + aliases
    agents_defaults = template.setdefault("agents", {}).setdefault("defaults", {})
    agents_defaults["model"] = build_agent_routing(catalog)
    agents_defaults["models"] = build_agent_aliases(catalog)
    
    # Set timeoutSeconds at agents.defaults level (not in model object)
    agents_defaults["timeoutSeconds"] = get_timeout_seconds(catalog)

    # Inject custom system prompt if configured
    import os as _os
    prompt_file = _os.environ.get("OPENCLAW_SYSTEM_PROMPT_FILE")
    if prompt_file:
        prompt_path = Path(prompt_file)
        if prompt_path.exists():
            agents_defaults["systemPrompt"] = prompt_path.read_text(encoding="utf-8").strip()

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
