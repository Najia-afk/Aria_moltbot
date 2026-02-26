# S-03: Prune LiteLLM Models to Essential Set
**Epic:** E2 — Model Pruning | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
27 models are registered in the DB (`aria_engine.llm_models`) and 19+ in `stacks/brain/litellm-config.yaml`, but only **2** have ever been used in production:
- `kimi` — 4458 calls, $18.26 total
- `qwen3-mlx` — 663 calls, $0

The other 25 models have 0 usage, 0 tokens. Free OpenRouter models go stale (rate-limited, deprecated). External users cloning Aria face broken model references from day one.

## Root Cause
Models were added during experimentation and never pruned. No governance on which models are "active". `models.yaml` is supposed to be the source of truth (Constraint #3) but `litellm-config.yaml` and the DB diverge.

## Fix

### Fix 1: Reduce litellm-config.yaml to 7 essential models
**File:** `stacks/brain/litellm-config.yaml` (232 lines → ~80 lines)

**KEEP these 7 models:**
| Model ID | Provider | Purpose |
|----------|----------|---------|
| `kimi` | Moonshot (paid) | Primary — proven reliable |
| `qwen3-mlx` | Ollama local | Local fallback — macOS |
| `deepseek-chat` | OpenRouter free | Best free reasoning |
| `gemma-3-27b` | OpenRouter free | Backup general-purpose |
| `qwen-2.5-72b` | OpenRouter free | Large context window |
| `mistral-small` | OpenRouter free | Fast lightweight |
| `llama-4-maverick` | OpenRouter free | Meta latest |

**REMOVE these models entirely:**
- `deepseek-r1`, `deepseek-r1-0528`, `deepseek-prover-v2` (duplicative with deepseek-chat)
- `gemma-3-12b`, `gemma-3-4b` (smaller variants — keep 27b only)
- `qwen3-235b-a22b`, `qwen3-30b-a3b`, `qwen2.5-vl-72b` (too many qwen variants)
- `phi-4-reasoning-plus` (niche)
- `olympiccoder-32b`, `devstral-small-2505` (niche coding)
- `llama-4-scout` (keep maverick only)
- `kimi-k2` (experimental — keep kimi stable only)
- `thinkany-ai-model` (unknown provider)
- All commented-out ollama entries except `qwen3-mlx`

### Fix 2: Align aria_models/models.yaml
**File:** `aria_models/models.yaml`
Remove stanzas for pruned models. Ensure remaining 7 match litellm-config exactly.

### Fix 3: Clean DB table
**Method:** Via aria-api GraphQL (Constraint #1 — NO direct SQL)
```graphql
mutation {
  deleteModel(modelId: "deepseek-r1") { success }
  deleteModel(modelId: "deepseek-r1-0528") { success }
  # ... repeat for each pruned model
}
```
If no `deleteModel` mutation exists, create one in the API layer first.

### Fix 4: Update .env.example default model
**File:** `stacks/brain/.env.example`
```env
DEFAULT_MODEL=kimi
FALLBACK_MODEL=qwen3-mlx
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | DB cleanup via API/GraphQL — no direct SQL |
| 2 | .env for secrets | ✅ | Default model in .env |
| 3 | models.yaml truth | ✅ | models.yaml must match litellm-config |
| 4 | Docker-first testing | ✅ | Test via docker compose up |
| 5 | aria_memories writable | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None (standalone)

## Verification
```bash
# 1. Count models in litellm-config:
grep -c 'model_name:' stacks/brain/litellm-config.yaml
# EXPECTED: 7

# 2. Count models in models.yaml:
grep -c 'model_id:' aria_models/models.yaml
# EXPECTED: 7

# 3. After Docker up, verify LiteLLM models:
curl -s http://localhost:4000/v1/models | python -m json.tool | grep '"id"' | wc -l
# EXPECTED: 7

# 4. Verify DB matches:
curl -s http://localhost:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query": "{ models { totalCount } }"}' | python -m json.tool
# EXPECTED: totalCount = 7
```

## Prompt for Agent
```
Read these files FIRST:
- stacks/brain/litellm-config.yaml (full)
- aria_models/models.yaml (full)
- stacks/brain/.env.example (find model-related vars)

CONSTRAINTS: #1 (no direct SQL), #3 (models.yaml = source of truth).

STEPS:
1. In litellm-config.yaml: Remove all model entries EXCEPT kimi, qwen3-mlx, deepseek-chat, gemma-3-27b, qwen-2.5-72b, mistral-small, llama-4-maverick
2. In models.yaml: Match exactly — remove stanzas for pruned models
3. Check if a deleteModel mutation exists in src/api/ — if not, create one following existing patterns
4. Create a one-shot script in scripts/ to call deleteModel for each pruned model
5. Update .env.example: ensure DEFAULT_MODEL and FALLBACK_MODEL are documented
6. Run verification commands
7. Do NOT modify aria_engine/llm_gateway.py behavior — only config and data
```
