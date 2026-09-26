# Aria Model Catalog

Single source of truth for model definitions and routing.

> Last updated: 2026-09-26
> User-facing routing guide: [MODELS.md](../MODELS.md)

- Catalog: `aria_models/models.yaml` (YAML, JSON-compatible)
- Loader: `aria_models/loader.py`
- Generated LiteLLM config: `stacks/brain/litellm-config.yaml`

## Active catalog

The repo keeps a small curated set of active models:

- `qwen3.5_mlx` — local MLX sentiment classifier only
- `embedding` — local Ollama embedding model
- `trinity` — OpenRouter Free Models Router, selects a compatible free model per request
- `trinity_backup` — Qwen 3.8 27B free fallback
- `kimi` — paid Moonshot K2.5 for explicit Moonshot skill calls only

## Quick read (Python)

```python
from aria_models.loader import load_catalog

catalog = load_catalog()
models = catalog["models"].keys()
```

## Shape (derived views)

```yaml
schema_version: 5
routing:
  primary: litellm/trinity
criteria:
  tiers:
    local: [qwen3.5_mlx, embedding]
    free: [trinity, trinity_backup]
    paid: [kimi]
tasks:
  primary: trinity
  embedding: embedding
```
