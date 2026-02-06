"""Quick test for model centralization changes."""
import sys
sys.path.insert(0, ".")

from aria_models.loader import list_all_model_ids, list_models_with_reasoning, build_litellm_config_entries

ids = list_all_model_ids()
print(f"All model IDs ({len(ids)}): {ids}")

reasoning = list_models_with_reasoning()
print(f"Reasoning models ({len(reasoning)}): {reasoning}")

entries = build_litellm_config_entries()
print(f"LiteLLM entries ({len(entries)}):")
for e in entries:
    print(f"  - {e['model_name']} -> {e['litellm_params']['model']}")

print("\nAll tests passed!")
