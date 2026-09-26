# Aria Blue ⚡️ — Model Routing

## Strategy

Aria uses a **free-first** strategy: MLX is reserved for sentiment classification; general work goes through OpenRouter's Free Models Router, with a static free-model fallback. Paid Moonshot calls are explicit only.

All routing goes through [LiteLLM](https://github.com/BerriAI/litellm) with automatic failover and spend tracking.

---

## Tier Priority

| Tier | Strategy | Cost |
|------|----------|------|
| **Local** | MLX sentiment + Ollama embeddings on Apple Silicon | Free |
| **Free** | OpenRouter Free Models Router + Qwen 3.8 fallback | Free — rate-limited |
| **Paid** | Explicit Moonshot/Kimi skill only | Per-token billing |

The routing priority, fallback chain, and all model definitions are in a single source of truth:

**→ [`aria_models/models.yaml`](aria_models/models.yaml)**

This file defines every model id, provider, tier, context window, and pricing. Nothing else should duplicate this information.

---

## Active Models

- `qwen3.5_mlx` — local MLX sentiment classifier only
- `embedding` — local Ollama embedding model for semantic memory
- `trinity` — OpenRouter Free Models Router; selects an available compatible free model per request
- `trinity_backup` — Qwen 3.8 27B free fallback
- `kimi` — Moonshot K2.5, available only for explicit Moonshot calls

## How It Works

```
Aria (or Agent)
     │
     ▼
LiteLLM Router
     ├─► Sentiment: MLX (host:8080)
     └─► General: OpenRouter Free Models Router
             └─► Qwen 3.8 free fallback
```

- LiteLLM receives a model alias (e.g., `litellm/qwen3.5_mlx`)
- Routes to the correct provider based on `models.yaml` configuration
- OpenRouter chooses a currently available free model compatible with request features
- Automatic fallback stays on free models; the daily account quota is not bypassed by model rotation
- Kimi is not part of automatic routing
- All usage is tracked for cost monitoring

---

## Focus-to-Model Mapping

Each focus persona has a model hint for optimal routing. These mappings are defined in `aria_mind/soul/focus.py` with the canonical model names from `models.yaml`.

---

## Configuration

- Model catalog and routing: [`aria_models/models.yaml`](aria_models/models.yaml)
- Model loader: [`aria_models/loader.py`](aria_models/loader.py)
- LiteLLM proxy config: [`stacks/brain/litellm-config.yaml`](stacks/brain/litellm-config.yaml)
- Model documentation: [`aria_models/README.md`](aria_models/README.md)

To regenerate LiteLLM config from models.yaml:

```bash
python scripts/generate_litellm_config.py
```

To benchmark local models:

```bash
python tests/load/benchmark_models.py
```

---

## Related

- [ARCHITECTURE.md](ARCHITECTURE.md) — System design overview
- [DEPLOYMENT.md](DEPLOYMENT.md) — How to set up MLX server and configure API keys
