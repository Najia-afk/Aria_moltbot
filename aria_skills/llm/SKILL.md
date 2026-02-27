# aria-llm — LLM Fallback Chain Skill

**Layer:** 2 (Infrastructure) | **Category:** LLM | **Status:** Active (S-45 Phase 3)

## Purpose

Provides resilient LLM completions with per-model circuit breakers and automatic fallback through the priority chain defined in `aria_models/models.yaml`. Never hardcodes model names — all routing comes from `routing.fallbacks` in models.yaml.

## Model Chain

Loaded dynamically at startup from `aria_models/models.yaml` (`routing.fallbacks`).  
Tier order: `local → free → paid`

| Priority | Tier | Model Source |
|----------|------|-------------|
| 1 | local | `qwen3-mlx` (MLX on Mac) |
| 2+ | free | OpenRouter free tier models |
| last | paid | `kimi` (Moonshot) |

## Circuit Breaker

Each model has an independent circuit breaker:
- Opens after `circuit_failure_threshold` consecutive failures (default: 3)
- Resets after `circuit_reset_seconds` (default: 60s)
- When a model is tripped, the skill automatically tries the next in chain

## Configuration (env vars)

| Variable | Default | Description |
|----------|---------|-------------|
| `LITELLM_URL` | `http://litellm:4000/v1` | LiteLLM proxy base URL |
| `LITELLM_MASTER_KEY` | `sk-aria` | API key for LiteLLM |

## Tools

| Tool | Description |
|------|-------------|
| `complete(messages, model?, temperature?, max_tokens?)` | Completion via fallback chain |
| `complete_with_model(model, messages, ...)` | Bypass chain — use specific model |
| `get_fallback_chain()` | Inspect current chain (from models.yaml) |
| `reset_circuit_breakers()` | Reset all circuit breakers to closed |

## Usage

```python
# Via run_skill.py
python3 aria_mind/skills/run_skill.py llm complete '{"messages": [{"role": "user", "content": "Hello"}]}'

# Via api_client (preferred)
aria-llm.complete({"messages": [{"role": "user", "content": "Summarise this text"}]})
```

## Dependencies

- `httpx` — HTTP client for LiteLLM proxy
- `aria_models.loader` — reads `models.yaml` for fallback chain
- LiteLLM proxy service running at `LITELLM_URL`
