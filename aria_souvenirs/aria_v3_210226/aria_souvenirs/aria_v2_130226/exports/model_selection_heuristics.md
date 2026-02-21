# Model Selection Heuristics

Reference document for automated model routing logic.

## Routing Priority Chain

```
local (MLX/Ollama) → free cloud (OpenRouter) → paid (Moonshot)
```

## Selection Criteria

### 1. Task Complexity
| Complexity | Indicators | Preferred Models |
|------------|------------|------------------|
| Simple | <100 tokens, single turn, classification | phi4-mini-local, gpt-oss-small-free |
| Medium | 100-1000 tokens, multi-step, analysis | qwen3-mlx, qwen3-next-free |
| Complex | >1000 tokens, reasoning, code gen | qwen3-coder-free, deepseek-free, kimi |

### 2. Context Length
| Tokens | Action |
|--------|--------|
| <4K | Any model acceptable |
| 4K-32K | Prefer qwen3-mlx, phi4-mini-local |
| 32K-128K | qwen3-next-free, trinity-free |
| >128K | nemotron-free, kimi (256K) |

### 3. Task Type Mapping
| Task Type | Model Preference | Fallback |
|-----------|------------------|----------|
| `code_generation` | qwen3-coder-free | gpt-oss-free |
| `complex_reasoning` | chimera-free | deepseek-free |
| `creative_writing` | trinity-free | glm-free |
| `long_context` | qwen3-next-free | nemotron-free |
| `fast_simple` | gpt-oss-small-free | qwen3-mlx |
| `embedding` | nomic-embed-text | - |

### 4. Focus-Based Defaults
| Focus | Default Model |
|-------|---------------|
| orchestrator | kimi |
| devsecops | qwen3-coder-free |
| data | chimera-free |
| trader | deepseek-free |
| creative | trinity-free |
| social | trinity-free |
| journalist | qwen3-next-free |

## Cost-Aware Routing

Always prefer zero-cost tiers unless explicitly overridden:
1. **Local** (0 cost): qwen3-mlx, phi4-mini-local, qwen3-local
2. **Free Cloud** (0 cost): All OpenRouter free models
3. **Paid** (last resort): kimi only when needed

## Implementation Notes

- Router uses `models.yaml` as single source of truth
- Runtime selection via `select_model_for_task()`
- Async-compatible for future streaming support
- Caches catalog with 5-min TTL
