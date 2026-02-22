# RT-02: Only Kimi Model Responds — Agent Diversity Broken

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P0 🔴 | **Points:** 5 | **Phase:** 1

---

## Roundtable Exchange

**SM:** Shiva said "only kimi is responding". Aria has 22 models in models.yaml.
Why are they all silent?

**Aria (PO):** `models.yaml` routing section:
```yaml
routing:
  primary: "litellm/kimi"
  bypass: false
```
When `bypass: false` and `primary` is set, the `LLMGateway` sends EVERY request to kimi.
The `tier_order: ["local", "free", "paid"]` fallback chain is only consulted when the
primary model **fails** — not on every request. So unless kimi 404s, the free models
are never touched.

**SM:** What's the correct behaviour?

**Aria (PO):**
1. For **user chat sessions**: route based on task complexity + tier preference.
   - Short questions → local (qwen3-mlx) or free tier first
   - Complex coding → qwen3-coder-free or deepseek-free
   - General → round-robin across free tier, kimi as paid fallback
2. For **agent cron jobs**: specific agents already have model hints in cron_jobs.yaml
3. The Coordinator should pick the model from `models.yaml` agent_aliases, not always kimi

---

## Problem

`aria_engine/llm_gateway.py` resolves the model via `EngineConfig.default_model`.
`EngineConfig` reads from env / models.yaml `routing.primary`.
Since `routing.primary = "litellm/kimi"` is hard-set, every call → kimi.

**File evidence:**
- `aria_models/models.yaml` line 20: `"primary": "litellm/kimi"`
- `aria_engine/config.py`: `default_model` property sources from `routing.primary`
- `aria_engine/llm_gateway.py`: uses `config.default_model` unless caller overrides

---

## Root Cause

The routing config was set to kimi during a paid-tier test and never reverted.
`routing.primary` acts as a global override that bypasses the tier-priority logic.
The tier fallback (`local → free → paid`) only activates on failures, not by default.

---

## Fix Plan

### Option A — Change primary to a free model (quick fix)
```yaml
# aria_models/models.yaml — routing section
"routing": {
  "primary": "litellm/qwen3-coder-free",   # ← was "litellm/kimi"
  "bypass": false,
  "tier_order": ["local", "free", "paid"],
  "fallbacks": ["litellm/kimi", ...]
}
```

### Option B — Implement smart routing in LLMGateway (elegant)
Add a `pick_model(task_hint: str) -> str` method that:
1. Checks if local model is alive (ping mlx endpoint)
2. Selects by tier and load (round-robin free tier)
3. Falls back to kimi only when free models fail

```python
# aria_engine/llm_gateway.py — new method
async def pick_model(self, task_hint: str = "") -> str:
    """Select model by tier preference, falling back up the chain."""
    tier_order = self._config.routing_tier_order  # local, free, paid
    for tier in tier_order:
        candidates = [m for m in self._models if m.tier == tier]
        if candidates:
            return random.choice(candidates).id  # round-robin
    return self._config.default_model  # absolute fallback
```

**Recommendation:** Do Option A immediately (unblock in minutes), then Option B in Phase 2.

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Change in models.yaml + LLMGateway only |
| 2 | .env for secrets | ✅ | API keys stay in .env — only routing config changes |
| 3 | models.yaml single source of truth | ✅ | THIS IS THE FIX — models.yaml governs routing |
| 4 | Docker-first testing | ✅ | Restart litellm + aria-engine containers |
| 5 | aria_memories only writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. After changing primary — verify config loaded:
curl http://localhost:8000/api/engine/config | python3 -m json.tool | grep -i model
# EXPECTED: "default_model": "litellm/qwen3-coder-free"

# 2. Send a test message and check which model responded:
curl -X POST http://localhost:8000/api/engine/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is 2+2?", "session_id": "test-rt02"}' | python3 -m json.tool
# EXPECTED: response.model != "kimi" (should be a free model)

# 3. Verify kimi is NOT called for simple queries:
docker compose logs aria-engine 2>&1 | grep -i "model=" | tail -5
# EXPECTED: mix of models, not only kimi
```

---

## Prompt for Agent

Read: `aria_models/models.yaml` full, `aria_engine/config.py` full,
`aria_engine/llm_gateway.py` lines 1–100.

Steps:
1. In `models.yaml`, change `routing.primary` from `"litellm/kimi"` to `"litellm/qwen3-coder-free"`
2. Add kimi to `routing.fallbacks` array if not already present (it is — verified)
3. Restart aria-engine: `docker compose restart aria-engine`
4. Run verification commands

Constraints: 3 (models.yaml is source of truth), 4 (Docker test).
Dependencies: None.
