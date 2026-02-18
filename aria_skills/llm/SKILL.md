---
name: aria-llm
description: Access LLM providers via LiteLLM routing (MLX local, OpenRouter FREE, Kimi paid).
metadata: {"aria": {"emoji": "ðŸ§ ", "requires": {"anyEnv": ["MOONSHOT_KIMI_KEY", "OLLAMA_URL", "OPEN_ROUTER_KEY"]}}}
---

# aria-llm

Access multiple LLM providers via LiteLLM routing for text generation and chat.

## Model Priority

**Source of truth**: `aria_models/models.yaml` â†’ `criteria.priority` and `criteria.tiers`.

Order: **Local â†’ Free Cloud â†’ Paid**. Never hardcode model names outside `models.yaml`.

## Usage

```bash
exec python3 /app/skills/run_skill.py llm <function> '<json_args>'
```

## Functions

### generate
Generate text from a prompt using specified model.

```bash
exec python3 /app/skills/run_skill.py llm generate '{"prompt": "Explain quantum computing simply", "model": "qwen3-mlx", "temperature": 0.7}'
```

### chat
Multi-turn conversation with message history.

```bash
exec python3 /app/skills/run_skill.py llm chat '{"messages": [{"role": "user", "content": "Hello!"}], "model": "qwen3-mlx"}'
```

### analyze
Analyze text for sentiment, topics, or custom analysis.

```bash
exec python3 /app/skills/run_skill.py llm analyze '{"text": "I had a great day today!", "analysis_type": "sentiment"}'
```

## Model Selection

See `aria_models/models.yaml` â†’ `criteria.use_cases` for model-to-task mapping.

When in doubt, use the `routing.primary` model defined in `models.yaml`.

## API Configuration

Required environment variables:
- `OPEN_ROUTER_KEY` - OpenRouter API key (for FREE models)
- `MOONSHOT_KIMI_KEY` - Moonshot API key (paid fallback)
- `OLLAMA_URL` - Ollama endpoint (backup local)

## Python Module

This skill wraps `/app/skills/aria_skills/llm.py`
