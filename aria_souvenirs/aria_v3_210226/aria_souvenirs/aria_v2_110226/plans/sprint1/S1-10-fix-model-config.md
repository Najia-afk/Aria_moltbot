# S1-10: Fix Model Config (qwen3-coder-free + chimera-free)

**Priority:** High | **Estimate:** 2 pts | **Status:** TODO

---

## Problem

Two model configurations in `aria_models/models.yaml` are broken, discovered during the agent swarm test (see `aria_memories/research/swarm_test_report_2026-02-11.md`):

### Issue 1: qwen3-coder-free — invalid model ID

At `aria_models/models.yaml:94`, the model ID is:
```yaml
"model": "openrouter/qwen/qwen3-coder-480b-a35b:free"
```

This returns errors from OpenRouter. The correct OpenRouter model slug should match the actual model available on the platform. The swarm test report confirms: "qwen3-coder-free misconfigured — Invalid model ID in OpenRouter."

### Issue 2: chimera-free — no tool calling support, but assigned to tool-use tasks

At `aria_models/models.yaml:76-82`, chimera-free is defined without any `tool_calling` flag:
```yaml
"chimera-free": {
    "provider": "litellm",
    "name": "Chimera 671B (OpenRouter FREE)",
    "reasoning": true,
    "input": ["text"],
    ...
}
```

The swarm test confirms: "Chimera-free lacks tool support — Returns 404 on tool calls."

The ARIA.md model table at `aria_mind/ARIA.md:64` already documents this:
```
| chimera-free | OpenRouter | NO ⚠️ | 164K | Free |
```

And line 68 states: `⚠️ NEVER assign tool-calling tasks to trinity-free or chimera-free.`

**But** chimera-free is still configured as a fallback for the `analyst` agent at `aria_mind/AGENTS.md:118`:
```yaml
fallback: chimera-free
```

The analyst agent uses skills `[database, knowledge_graph, performance, llm]` — all require tool calling.

Additionally, chimera-free is in the global fallback chain at `aria_models/models.yaml:23`:
```yaml
"fallbacks": ["litellm/qwen3-next-free", "litellm/trinity-free", "litellm/chimera-free", "litellm/deepseek-free", "litellm/gpt-oss-free"]
```

And in `criteria.priority` at `aria_models/models.yaml:268`:
```yaml
"priority": ["kimi", "trinity-free", "chimera-free", "qwen3-next-free", "deepseek-free"]
```

---

## Root Cause

1. **qwen3-coder-free**: Model slug `qwen/qwen3-coder-480b-a35b:free` is incorrect — likely a typo or the model was renamed on OpenRouter.
2. **chimera-free**: No `tool_calling` field in the schema, so the coordinator has no way to know it can't do tool calls. It gets assigned to tool-needing agents via fallback chains.

---

## Fix

### Fix 1: Correct qwen3-coder-free model ID

**Before** (`aria_models/models.yaml:94`):
```yaml
        "model": "openrouter/qwen/qwen3-coder-480b-a35b:free",
```

**After**:
```yaml
        "model": "openrouter/qwen/qwen3-coder:free",
```

> **Note:** Verify the correct slug on OpenRouter before applying. The slug `qwen/qwen3-coder:free` is the most likely correct form. Check with: `curl -s https://openrouter.ai/api/v1/models | jq '.data[] | select(.id | contains("qwen3-coder")) | .id'`

### Fix 2: Add tool_calling field to chimera-free

**Before** (`aria_models/models.yaml:76-78`):
```yaml
    "chimera-free": {
      "provider": "litellm",
      "name": "Chimera 671B (OpenRouter FREE)",
      "reasoning": true,
      "input": ["text"],
```

**After**:
```yaml
    "chimera-free": {
      "provider": "litellm",
      "name": "Chimera 671B (OpenRouter FREE)",
      "reasoning": true,
      "tool_calling": false,
      "input": ["text"],
```

Also add `tool_calling: false` to `trinity-free` (`aria_models/models.yaml:63`):

**Before**:
```yaml
    "trinity-free": {
      "provider": "litellm",
      "name": "Trinity 400B MoE (OpenRouter FREE)",
      "reasoning": true,
      "input": ["text"],
```

**After**:
```yaml
    "trinity-free": {
      "provider": "litellm",
      "name": "Trinity 400B MoE (OpenRouter FREE)",
      "reasoning": true,
      "tool_calling": false,
      "input": ["text"],
```

### Fix 3: Remove chimera-free as analyst fallback

**Before** (`aria_mind/AGENTS.md:118`):
```yaml
fallback: chimera-free
```

**After**:
```yaml
fallback: qwen3-next-free
```

### Fix 4: Remove chimera-free from global fallback chain (non-tool tasks only)

**Before** (`aria_models/models.yaml:23`):
```yaml
"fallbacks": ["litellm/qwen3-next-free", "litellm/trinity-free", "litellm/chimera-free", "litellm/deepseek-free", "litellm/gpt-oss-free"]
```

**After**:
```yaml
"fallbacks": ["litellm/qwen3-next-free", "litellm/deepseek-free", "litellm/gpt-oss-free", "litellm/trinity-free", "litellm/chimera-free"]
```

Move non-tool-calling models to the end of the fallback chain so they're only tried as a last resort.

### Fix 5: Update criteria.priority

**Before** (`aria_models/models.yaml:268`):
```yaml
"priority": ["kimi", "trinity-free", "chimera-free", "qwen3-next-free", "deepseek-free"]
```

**After**:
```yaml
"priority": ["kimi", "qwen3-next-free", "deepseek-free", "trinity-free", "chimera-free"]
```

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | models.yaml remains valid JSON | ✅ Only value changes |
| 2 | No breaking changes to LiteLLM proxy | ✅ Model ID correction only |
| 3 | Regenerate litellm-config.yaml after change | ⚠️ Run `scripts/generate_configs.py` |
| 4 | AGENTS.md stays consistent with models.yaml | ✅ Both updated together |
| 5 | ARIA.md model table already correct | ✅ Already marks chimera as NO tools |
| 6 | No Python code changes needed | ✅ Config-only fix |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| `scripts/generate_configs.py` | Post-fix | Must run after models.yaml edits to regenerate litellm-config.yaml |
| OpenRouter API | Runtime | Verify qwen3-coder-free model slug is valid |
| S1-13 (Docker verify) | Downstream | Rebuild containers to pick up new config |

---

## Verification

```bash
# 1. Verify qwen3-coder-free model ID is corrected
grep "qwen3-coder" aria_models/models.yaml | grep "model"
# Expected: "model": "openrouter/qwen/qwen3-coder:free"
# (Should NOT contain "480b-a35b")

# 2. Verify chimera-free has tool_calling: false
grep -A5 '"chimera-free"' aria_models/models.yaml | grep "tool_calling"
# Expected: "tool_calling": false

# 3. Verify trinity-free has tool_calling: false
grep -A5 '"trinity-free"' aria_models/models.yaml | grep "tool_calling"
# Expected: "tool_calling": false

# 4. Verify analyst fallback is no longer chimera-free
grep "fallback:" aria_mind/AGENTS.md
# Expected: fallback: qwen3-next-free (NOT chimera-free)

# 5. Verify chimera-free is at end of fallback chain
grep "fallbacks" aria_models/models.yaml
# Expected: chimera-free should be last or second-to-last

# 6. Regenerate litellm config and verify
python scripts/generate_configs.py
# Expected: Success, no errors

# 7. Test qwen3-coder-free model (after Docker restart)
curl -s http://localhost:18793/v1/models | jq '.data[] | select(.id | contains("qwen3-coder"))'
# Expected: Valid model entry (no 404)
```

---

## Prompt for Agent

```
Read aria_models/models.yaml, aria_mind/AGENTS.md, and aria_mind/ARIA.md.

Two model configs are broken per the swarm test report:

1. qwen3-coder-free at models.yaml line 94 has invalid model ID "openrouter/qwen/qwen3-coder-480b-a35b:free".
   Fix: Change to "openrouter/qwen/qwen3-coder:free" (verify slug on OpenRouter first).

2. chimera-free at models.yaml line 76 lacks a tool_calling field. It returns 404 on tool calls.
   Fix: Add "tool_calling": false to chimera-free AND trinity-free entries.

3. In AGENTS.md line 118, analyst agent has `fallback: chimera-free` but analyst needs tool calling.
   Fix: Change to `fallback: qwen3-next-free`.

4. In models.yaml line 23, chimera-free and trinity-free are in the global fallback chain ahead of tool-capable models.
   Fix: Move them to the end of the fallbacks array.

5. In models.yaml line 268, criteria.priority has chimera-free before tool-capable models.
   Fix: Reorder to ["kimi", "qwen3-next-free", "deepseek-free", "trinity-free", "chimera-free"].

After all edits, run: python scripts/generate_configs.py to regenerate litellm-config.yaml.

Verify: grep "tool_calling" aria_models/models.yaml should show false for chimera-free and trinity-free.
```
