#!/usr/bin/env python3
"""Generate derivative config files from models.yaml (single source of truth)."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aria_models.loader import load_catalog, build_litellm_config_yaml, validate_catalog


def main():
    errors = validate_catalog()
    if errors:
        print("Validation errors in models.yaml:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    # Generate litellm config
    litellm_yaml = build_litellm_config_yaml()
    out_path = Path("stacks/brain/litellm-config.yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(litellm_yaml, encoding="utf-8")

    catalog = load_catalog()
    print(f"Generated litellm-config.yaml ({len(catalog['models'])} models)")
    print("All validations passed.")


if __name__ == "__main__":
    main()
