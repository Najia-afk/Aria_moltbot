# S2-04: YAML-Driven Model Routing — Follow the Order, No Hardcoded Names
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Model routing is **almost** config-driven but not quite:
1. `models.yaml` already defines `routing.primary`, `routing.fallbacks`, `criteria.priority`, `criteria.focus_defaults`, and `profiles` — **good**
2. But the actual Python code doesn't fully leverage this. The coordinator resolves `self.config.model` per agent, and `_fallback_process()` just calls litellm's router without explicitly following the YAML order
3. There's no **bypass flag** — if Shiva wants to force kimi-only (because local models aren't working on their machine), there's no clean way without editing code
4. The `criteria.use_cases.default` currently hardcodes `["kimi"]` — that's a model name baked into config intent

**The goal: Aria reads the YAML, follows the order top-to-bottom, done. Zero model names in Python. One config flag to bypass everything and force a single model.**

## Current State (What Already Works)
```yaml
# models.yaml already has:
"routing": {
  "primary": "litellm/kimi",               # ← this IS the order
  "fallbacks": ["litellm/qwen3-next-free", "litellm/deepseek-free", ...]
},
"criteria": {
  "priority": ["kimi", "qwen3-next-free", "deepseek-free", ...],  # ← fallback chain
  "focus_defaults": {
    "orchestrator": "kimi",
    "devsecops": "qwen3-coder-free",
    ...
  }
},
"profiles": {
  "routing":  { "model": "kimi",  "temperature": 0.3 },
  ...
}
```

This is already well-structured. The fix is ensuring the Python code **reads and follows this**, and adding the bypass.

## Fix

### 1. Add `routing.bypass` to models.yaml
```yaml
"routing": {
  "primary": "litellm/kimi",
  "timeout": 300,
  "retries": 2,
  "bypass": null,
  "fallbacks": ["litellm/qwen3-next-free", "litellm/deepseek-free", ...]
}
```

**When `bypass` is set to a model ID**, ALL routing decisions are skipped — every request goes to that model. When `null` (default), normal routing applies.

Usage:
```yaml
# Normal mode — follow the order:
"bypass": null

# Force kimi for everything (local is broken):
"bypass": "litellm/kimi"

# Force a free model for cost testing:
"bypass": "litellm/qwen3-next-free"
```

This is a **config change only** — Shiva edits one line in YAML, no Python modifications needed.

### 2. Add `routing.tier_order` to make tier preference explicit
```yaml
"routing": {
  "primary": "litellm/kimi",
  "timeout": 300,
  "retries": 2,
  "bypass": null,
  "tier_order": ["paid", "free"],
  "fallbacks": ["litellm/qwen3-next-free", "litellm/deepseek-free", ...]
}
```

**`tier_order`** defines the priority: `["paid", "free"]` means try paid first, then free. When local models work again, Shiva adds `"local"` back: `["local", "free", "paid"]`. This replaces the implicit "local → free → paid" comment that only existed in code comments.

### 3. Python reads the YAML — zero hardcoded model names
The model loader (`aria_models/loader.py`) should expose a function:

```python
def get_routing_config() -> dict:
    """Return routing config from models.yaml."""
    catalog = load_models()
    return catalog.get("routing", {})

def get_model_for_task(task_type: str = "default") -> str:
    """
    Get model ID for a task, respecting bypass and YAML order.
    
    Returns the model ID string — caller passes it to litellm.
    Zero hardcoded model names in this function.
    """
    routing = get_routing_config()
    
    # Bypass overrides everything
    bypass = routing.get("bypass")
    if bypass:
        return bypass
    
    # Otherwise, return primary (the YAML decides, not Python)
    return routing.get("primary", "")
```

The key principle: **Python never contains model name strings.** It reads whatever `models.yaml` says.

### 4. Profiles already work — just document the pattern
The existing `profiles` section is already correct:
```yaml
"profiles": {
  "routing":  { "model": "kimi",             "temperature": 0.3, "max_tokens": 512 },
  "analysis": { "model": "kimi",             "temperature": 0.7, "max_tokens": 4096 },
  "creative": { "model": "trinity-free",     "temperature": 0.9, "max_tokens": 2048 },
  "code":     { "model": "qwen3-coder-free", "temperature": 0.2, "max_tokens": 8192 },
  "social":   { "model": "trinity-free",     "temperature": 0.8, "max_tokens": 1024 }
}
```

If Shiva wants to change which model handles creative tasks, they edit the YAML. If bypass is set, it overrides profiles too.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Config + loader change only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ✅ | This IS the SSOT — all routing lives here |
| 4 | Docker-first | ✅ | Verify models.yaml loads correctly in containers |
| 5 | aria_memories writable | ❌ | Config only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone enhancement.

## Verification
```bash
# 1. models.yaml is valid YAML/JSON:
python3 -c "import yaml; d=yaml.safe_load(open('aria_models/models.yaml')); print('OK')"
# EXPECTED: OK

# 2. bypass field exists:
python3 -c "
import yaml
d = yaml.safe_load(open('aria_models/models.yaml'))
r = d.get('routing', {})
print(f'primary: {r.get(\"primary\")}')
print(f'bypass: {r.get(\"bypass\")}')
print(f'tier_order: {r.get(\"tier_order\")}')
print(f'fallbacks: {len(r.get(\"fallbacks\", []))} models')
"
# EXPECTED: primary: litellm/kimi, bypass: None, tier_order: [...], fallbacks: N models

# 3. No hardcoded model names in Python skills:
grep -rn '"kimi"\|"qwen3"\|"trinity"\|"chimera"\|"deepseek"' aria_skills/ aria_agents/ aria_mind/ --include="*.py" | grep -v __pycache__ | grep -v "\.yaml\|\.md\|#\|comment\|test" | wc -l
# EXPECTED: 0 (zero hardcoded model names in Python)

# 4. loader exposes routing config:
python3 -c "from aria_models.loader import load_models; r=load_models().get('routing',{}); print(f'bypass={r.get(\"bypass\")}')"
# EXPECTED: bypass=None

# 5. Profiles intact:
python3 -c "
import yaml
d = yaml.safe_load(open('aria_models/models.yaml'))
for name, p in d.get('profiles', {}).items():
    print(f'  {name}: model={p[\"model\"]}, temp={p[\"temperature\"]}')
"
# EXPECTED: 5 profiles listed with their models
```

## Prompt for Agent
```
Make model routing fully YAML-driven with a bypass config flag.

**Principle: Zero model names in Python. The YAML is law. Python reads and follows.**

**Files to read:**
- aria_models/models.yaml (FULL — understand existing routing/profiles/criteria structure)
- aria_models/loader.py (FULL — this is where get_routing_config() goes)
- aria_mind/cognition.py (lines 295-330 — _fallback_process, verify it uses litellm router)
- aria_agents/coordinator.py (lines 60-90 — how model is resolved per agent)

**Steps:**
1. Add to models.yaml `routing` section:
   - `"bypass": null` — when set to a model ID, overrides ALL routing
   - `"tier_order": ["paid", "free"]` — explicit tier preference
2. Add to aria_models/loader.py:
   - `get_routing_config()` — returns routing dict from YAML
   - `get_model_for_task()` — respects bypass, returns primary model ID
3. Verify no Python file contains hardcoded model name strings
4. Test: set bypass to "litellm/kimi", verify it's picked up
5. Test: set bypass to null, verify normal routing works

**Critical:** Do NOT hardcode model names in Python. Read them from models.yaml only.
**Critical:** The bypass flag is for Shiva — when local models are broken, set bypass to force kimi-only.
```
