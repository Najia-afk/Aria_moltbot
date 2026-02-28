# S-74: Token Budget Enforcement — Focus Hard Ceiling on max_tokens

**Epic:** E7 — Focus System v2 | **Priority:** P1 | **Points:** 2 | **Phase:** 2

---

## Problem

`aria_engine/agent_pool.py` line 123:
```python
max_tokens=kwargs.get("max_tokens", self.max_tokens),
```

This gives callers unlimited ability to push `max_tokens` as high as they want.
`FocusProfileEntry.token_budget_hint` (added in S-70) was designed to be a
**hard per-focus ceiling** — keeping creative agents at 800 tokens and
orchestrator agents at 3000 tokens. Without enforcement, the token budget column
is decorative data with zero operational impact.

---

## Design Decision

```
effective_max_tokens = min(
    caller_explicit_max_tokens_OR_agent_default,
    focus.token_budget_hint   ← hard ceiling (cannot be exceeded by callers)
)
```

The ceiling is **non-negotiable** unless: (a) no focus profile is loaded, or
(b) `token_budget_hint` is 0 / null (disabled). If no focus profile, fall back
to existing behavior.

---

## Fix

### Step 1 — Patch `process()` max_tokens line

**File:** `aria_engine/agent_pool.py`

**BEFORE (from S-73 AFTER block — line that sets max_tokens):**
```python
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
```

**AFTER:**
```python
                max_tokens=_budget_cap(
                    caller=kwargs.get("max_tokens", self.max_tokens),
                    fp=fp,
                ),
```

### Step 2 — Add module-level `_budget_cap()` helper

Add this function near the top of `agent_pool.py` (before class definitions,
after imports):

```python
def _budget_cap(caller: int | None, fp: dict | None) -> int | None:
    """
    Apply focus token_budget_hint as a hard ceiling on max_tokens.

    - If no focus profile or token_budget_hint == 0: caller value passes through.
    - Otherwise: min(caller, token_budget_hint) so focus budget can never be
      exceeded, even by explicit caller overrides.

    Args:
        caller:  Caller-requested max_tokens (int or None means "use model default").
        fp:      Resolved FocusProfileEntry dict (or None).

    Returns:
        Capped int, or None if both caller and budget are unset.
    """
    budget: int | None = fp.get("token_budget_hint") if fp else None
    if not budget:           # 0, None, or no focus profile → pass through as-is
        return caller
    if caller is None:       # no explicit caller value → respect budget ceiling
        return budget
    return min(caller, budget)
```

---

## Token Budget Reference (from S-71 seed profiles)

| Focus ID     | Tier | token_budget_hint | Rationale |
|-------------|------|-------------------|-----------|
| orchestrator | L1   | 3000              | High-level strategy; needs full context |
| devsecops    | L2   | 2000              | Technical depth; medium budget |
| data         | L2   | 2500              | Long analytical responses |
| research     | L2   | 2500              | Paper-style depth |
| journalist   | L2   | 1500              | Polished articles; bounded |
| social       | L3   | 800               | Short-form posts only |
| creative     | L3   | 1200              | Crisp creative copy |
| rpg_master   | L3   | 1000              | Scene narration; vivid but bounded |

---

## Constraints

| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | Hard ceiling | ✅ | min(caller, budget) — caller can never exceed focus budget |
| 2 | Graceful degradation | ✅ | `budget = 0 or None` → pass through |
| 3 | No soul modification | ✅ | None |
| 4 | Helper is pure function | ✅ | No DB calls; side-effect free |

---

## Dependencies

- **S-73 must complete first** — S-73 sets up `fp = self._focus_profile` in `process()`; S-74 reuses that same `fp` variable
- **S-70** — `token_budget_hint` column must exist on `focus_profiles` table

---

## Verification

```bash
# 1. Syntax clean
docker exec aria-engine python3 -c "
import ast, pathlib
ast.parse(pathlib.Path('aria_engine/agent_pool.py').read_text())
print('syntax OK')
"
# EXPECTED: syntax OK

# 2. Budget cap logic
docker exec aria-engine python3 -c "
from aria_engine.agent_pool import _budget_cap

# No focus → pass through
print(_budget_cap(500, None))          # 500
print(_budget_cap(None, None))         # None

# Focus budget = 800, caller wants 2000 → capped at 800
fp = {'token_budget_hint': 800}
print(_budget_cap(2000, fp))           # 800
print(_budget_cap(500, fp))            # 500  (caller is under budget)
print(_budget_cap(None, fp))           # 800  (no caller → use budget)

# budget = 0 → disabled, pass through
fp0 = {'token_budget_hint': 0}
print(_budget_cap(2000, fp0))          # 2000
"
# EXPECTED:
# 500
# None
# 800
# 500
# 800
# 2000

# 3. Social agent hard-capped to 800
docker exec aria-engine python3 -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from aria_engine.agent_pool import EngineAgent

async def test():
    db = create_async_engine(os.environ['DATABASE_URL'])
    agent = EngineAgent(
        agent_id='test-social',
        system_prompt='You are a social media manager.',
        focus_type='social',
        model='claude-3-5-haiku-20241022',
        max_tokens=4096,        # agent default; must be overridden by focus
    )
    await agent.load_focus_profile(db)
    fp = agent._focus_profile
    from aria_engine.agent_pool import _budget_cap
    result = _budget_cap(4096, fp)
    print('social max_tokens capped to:', result)
    assert result == 800, f'Expected 800, got {result}'
    print('PASS')

asyncio.run(test())
"
# EXPECTED: social max_tokens capped to: 800 / PASS
```

---

## Prompt for Agent

You are executing ticket S-74 for the Aria project.

**Constraint:** This is a two-line change after S-73 is applied. Do NOT touch S-73 changes. Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `aria_engine/agent_pool.py` — find the `_budget_cap` insertion point (top of file, after imports), and the `max_tokens=` line inside `process()` (search for `kwargs.get("max_tokens")`).

**Steps:**
1. Add the `_budget_cap()` pure function at module level (after imports, before class definitions).
2. Replace the single `max_tokens=kwargs.get("max_tokens", self.max_tokens)` line with `max_tokens=_budget_cap(caller=kwargs.get("max_tokens", self.max_tokens), fp=fp)`.
3. Run all 3 verification commands and confirm outputs match EXPECTED.
4. Report: "S-74 DONE — Focus token budget enforced as hard ceiling, degradation verified, social capped at 800."
