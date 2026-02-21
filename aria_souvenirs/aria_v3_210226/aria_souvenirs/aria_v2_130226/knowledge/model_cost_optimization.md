# Model Cost Optimization Analysis

**Date:** 2026-02-12  
**Goal:** Optimize Model Selection for Cost Efficiency  
**Progress:** Audit complete, recommendations documented

## Current State

### Model Tiers
| Tier | Models | Cost |
|------|--------|------|
| Local | qwen3-mlx, qwen-cpu-fallback, phi4-mini-local, qwen3-local | $0 |
| Free | trinity-free, qwen3-coder-free, chimera-free, qwen3-next-free, glm-free, deepseek-free, nemotron-free, gpt-oss-free, gpt-oss-small-free | $0 |
| Paid | kimi ($0.56/$2.94), kimi-k2-thinking ($0.56/$2.24) | $$ |

### Routing Configuration
```yaml
primary: litellm/kimi  # PAID - primary for reliability
fallbacks:
  - litellm/qwen3-next-free  # FREE
  - litellm/deepseek-free    # FREE
  - litellm/gpt-oss-free     # FREE
  - litellm/trinity-free     # FREE
  - litellm/chimera-free     # FREE
```

### Focus Defaults (✅ Already Optimized)
| Focus | Default Model | Tier | Rationale |
|-------|--------------|------|-----------|
| orchestrator | kimi | paid | Reliability for coordination |
| devsecops | qwen3-coder-free | free | Code-optimized, free |
| data | chimera-free | free | Reasoning-capable, free |
| trader | deepseek-free | free | Analytical, free |
| creative | trinity-free | free | Creative writing, free |
| social | trinity-free | free | Engaging, free |
| journalist | qwen3-next-free | free | Long context, free |

## Cost-Saving Heuristics

### 1. Use Local First for Simple Tasks
- **qwen3-mlx** (4B, 2.1GB): Fast classification, simple Q&A
- **phi4-mini-local** (3.8B): Routing, categorization
- **qwen3-local** (8B): General code tasks (if RAM permits)

### 2. Use Free Cloud for Specialized Work
- **Code generation:** qwen3-coder-free (480B MoE)
- **Complex reasoning:** chimera-free, deepseek-free
- **Creative writing:** trinity-free
- **Long context:** qwen3-next-free (262K), nemotron-free (256K)

### 3. Reserve Paid Models for Critical Paths
- **kimi**: Orchestrator coordination, final validation
- **kimi-k2-thinking**: Complex multi-step reasoning when free models fail

### 4. Profile-Based Selection
```yaml
routing:   { model: kimi,           temp: 0.3, tokens: 512 }   # Fast decisions
analysis:  { model: kimi,           temp: 0.7, tokens: 4096 }  # Deep analysis
creative:  { model: trinity-free,   temp: 0.9, tokens: 2048 }  # Creative work
code:      { model: qwen3-coder-free, temp: 0.2, tokens: 8192 } # Code gen
social:    { model: trinity-free,   temp: 0.8, tokens: 1024 }  # Posts
```

## Recommendations

1. **Keep current focus defaults** — they're well-optimized
2. **Consider local MLX for heartbeat tasks** — zero cost, sufficient for simple operations
3. **Monitor token usage** — implement spend tracking via aria-litellm metrics
4. **Cache embeddings locally** — nomic-embed-text (Ollama) for semantic search

## Next Steps
- [ ] Verify MLX local model availability in deployment environment
- [ ] Implement token usage logging to database
- [ ] Create cost dashboard in aria-performance

