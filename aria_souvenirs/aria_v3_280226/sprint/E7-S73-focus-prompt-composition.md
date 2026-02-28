# S-73: agent_pool.process() — Focus Prompt Composition + Temperature Delta

**Epic:** E7 — Focus System v2 | **Priority:** P1 | **Points:** 3 | **Phase:** 2

---

## Problem

`aria_engine/agent_pool.py` `process()` at line 85:

- Line 108: `if self.system_prompt:` injects only `self.system_prompt` (static, set at agent creation)
- Line 122: `temperature=kwargs.get("temperature", self.temperature)` — temperature is agent-fixed
- Line 123: `max_tokens=kwargs.get("max_tokens", self.max_tokens)` — max_tokens is agent-fixed
- `self.focus_type` (set from DB, e.g. `"devsecops"`) is stored on the agent but **never used** inside `process()`

Result: two agents with different `focus_type` values produce identical system prompts to the LLM, ignoring thousands of tokens of carefully crafted persona instructions in `FocusProfileEntry.system_prompt_addon`.

---

## Root Cause

`FocusProfileEntry` (created in S-70) has `system_prompt_addon`, `temperature_delta`, `model_override`, and `auto_skills` columns, but `process()` never looks them up. There is no DB query path from `EngineAgent.process()` to `focus_profiles`.

---

## Fix

### Step 1 — Add `_focus_cache` to `EngineAgent.__init__`

The agent must hold a cached copy of its resolved `FocusProfileEntry` to avoid a DB round-trip on every single token. Cache is populated once at startup or when `focus_type` is set/changed.

**File:** `aria_engine/agent_pool.py`

Find `class EngineAgent` `__init__` and add one line after `self.focus_type` is set:

```python
# Placed immediately after self.focus_type is assigned in __init__
self._focus_profile: dict | None = None   # populated by load_focus_profile()
```

### Step 2 — Add `load_focus_profile()` method to `EngineAgent`

```python
async def load_focus_profile(self, db_engine: AsyncEngine) -> None:
    """
    Fetch FocusProfileEntry for self.focus_type and cache it locally.
    Safe to call at any time (re-fetches if focus_type changed).
    No-op if focus_type is None or DB query fails.
    """
    if not self.focus_type:
        self._focus_profile = None
        return
    try:
        from db.models import FocusProfileEntry
        from sqlalchemy import select as _select
        async with db_engine.begin() as conn:
            result = await conn.execute(
                _select(FocusProfileEntry).where(
                    FocusProfileEntry.focus_id == self.focus_type,
                    FocusProfileEntry.enabled == True,  # noqa: E712
                )
            )
            row = result.scalars().first()
        self._focus_profile = row.to_dict() if row else None
        logger.debug("Agent %s loaded focus_profile: %s", self.agent_id, self.focus_type)
    except Exception as exc:
        logger.warning("Agent %s could not load focus profile %s: %s", self.agent_id, self.focus_type, exc)
        self._focus_profile = None
```

### Step 3 — Patch `process()` — compose system prompt + apply deltas

**File:** `aria_engine/agent_pool.py`

**BEFORE (lines 108–128):**
```python
        # Build messages for LLM
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        # Sliding window: keep last N context messages
        context_window = kwargs.get("context_window", 50)
        messages.extend(self._context[-context_window:])

        try:
            response = await self._llm_gateway.complete(
                messages=messages,
                model=kwargs.get("model", self.model),
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
```

**AFTER:**
```python
        # Build messages for LLM — compose system prompt with focus addon
        fp = self._focus_profile  # pre-loaded dict or None
        base_prompt = self.system_prompt or ""
        if fp and fp.get("system_prompt_addon"):
            effective_system = (
                base_prompt.rstrip()
                + "\n\n---\n"
                + fp["system_prompt_addon"]
            )
        else:
            effective_system = base_prompt

        messages = []
        if effective_system:
            messages.append({"role": "system", "content": effective_system})
        # Sliding window: keep last N context messages
        context_window = kwargs.get("context_window", 50)
        messages.extend(self._context[-context_window:])

        # Apply focus temperature delta (additive, clamped 0.0–1.0)
        base_temp = kwargs.get("temperature", self.temperature)
        temp_delta = float(fp.get("temperature_delta", 0.0)) if fp else 0.0
        effective_temp = max(0.0, min(1.0, base_temp + temp_delta))

        # Apply focus model override (only if caller doesn't force a model)
        effective_model = (
            kwargs.get("model")
            or (fp.get("model_override") if fp else None)
            or self.model
        )

        try:
            response = await self._llm_gateway.complete(
                messages=messages,
                model=effective_model,
                temperature=effective_temp,
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
```

**Note:** `max_tokens` enforcement by focus budget is handled in S-74.
`effective_system` additive — never replaces `base_prompt`, just appends.

---

## Constraints

| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer architecture | ✅ | `agent_pool.py` is engine layer — permitted to read DB directly |
| 2 | Additive prompts only | ✅ | `base_prompt + "\n\n---\n" + addon` pattern enforced |
| 3 | Temperature clamped | ✅ | `max(0.0, min(1.0, ...))` |
| 4 | Cache per-agent | ✅ | `self._focus_profile` dict; refreshed via `load_focus_profile()` |
| 5 | No soul files touched | ✅ | None |

---

## Dependencies

- **S-70 must complete first** — `FocusProfileEntry` ORM class and `to_dict()` method must exist
- **S-71 must complete first** — 8 seed profiles must be in DB so `load_focus_profile()` can fetch

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

# 2. Focus profile is composed in prompt
docker exec aria-engine python3 -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from aria_engine.agent_pool import EngineAgent

async def test():
    db = create_async_engine(os.environ['DATABASE_URL'])
    agent = EngineAgent(
        agent_id='test-devsecops',
        system_prompt='You are a DevSecOps engineer.',
        focus_type='devsecops',
        model='claude-3-5-haiku-20241022',
    )
    await agent.load_focus_profile(db)
    fp = agent._focus_profile
    print('focus loaded:', fp is not None)
    if fp:
        print('addon preview:', (fp.get('system_prompt_addon') or '')[:100])
        print('temp_delta:', fp.get('temperature_delta'))

asyncio.run(test())
"
# EXPECTED: focus loaded: True
#           addon preview: (first 100 chars of devsecops addon)
#           temp_delta:  (some float value)

# 3. Effective system prompt is additive
docker exec aria-engine python3 -c "
base = 'You are a DevSecOps engineer.'
addon = 'Focus on security vulnerabilities.'
effective = base.rstrip() + '\n\n---\n' + addon
print('separator present:', '---' in effective)
print(repr(effective))
"
# EXPECTED: separator present: True
```

---

## Prompt for Agent

You are executing ticket S-73 for the Aria project.

**Constraint:** `agent_pool.py` is engine layer. DB access permitted. Additive prompt composition only — never replace `self.system_prompt`. Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `aria_engine/agent_pool.py` — full `EngineAgent.__init__` block and `process()` (lines 1–160)

**Steps:**
1. Add `self._focus_profile: dict | None = None` to `EngineAgent.__init__` after `focus_type` assignment.
2. Add `load_focus_profile(db_engine)` async method to `EngineAgent` class.
3. Patch `process()` lines 108–128 with the BEFORE/AFTER block shown above.
4. Run all 3 verification commands and confirm outputs.
5. Report: "S-73 DONE — Focus prompt composition live, temperature delta applied, model override wired."
