---
name: aria-model-switcher
description: Switch between Ollama models at runtime - GLM for smart text, Qwen3-VL for vision.
metadata: {"openclaw": {"emoji": "🔄", "requires": {"env": []}, "primaryEnv": "OLLAMA_URL"}}
---

# aria-model-switcher

Switch between Ollama models at runtime without restarting containers or reconfiguring LiteLLM/OpenClaw.

## Why?

- **GLM-4.7-Flash-REAP** - Smarter for complex text reasoning
- **Qwen3-VL** - Has vision capabilities for image tasks
- Both run locally on Mac Metal GPU via Ollama

## Model Aliases

| Alias | Full Model Name | Use Case |
|-------|----------------|----------|
| `glm` | `hf.co/unsloth/GLM-4.7-Flash-REAP-23B-A3B-GGUF:Q3_K_S` | Default. Smart text reasoning |
| `qwen3-vl` | `qwen3-vl:8b` | Vision/image tasks |
| `qwen2.5` | `qwen2.5:7b` | Backup text model |

## Usage

```bash
# List available models
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher list_models '{}'

# Switch to GLM for text tasks (default)
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher switch_model '{"model": "glm"}'

# Switch to Qwen3-VL for vision/image analysis
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher switch_model '{"model": "qwen3-vl"}'

# Check current model
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher get_current_model '{}'

# Pull a model if not available
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher pull_model '{"model": "qwen3-vl"}'
```

## How It Works

1. Model preference is stored in `/root/.openclaw/workspace/memory/model_preference.json`
2. `OllamaSkill` reads this file on each request to determine which model to use
3. No container restart needed - changes take effect immediately
4. LiteLLM/OpenClaw are unaware - they just see "Ollama" as the provider

## Recommended Workflow

1. Use **GLM** as default for most tasks (smarter, better reasoning)
2. Switch to **Qwen3-VL** when you need to analyze images
3. Switch back to **GLM** after vision tasks complete

## Troubleshooting

### Model not found
```bash
# Pull the model first
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher pull_model '{"model": "glm"}'
```

### Ollama not reachable
Check that Ollama is running natively on Mac (not in Docker) for Metal GPU acceleration:
```bash
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```
