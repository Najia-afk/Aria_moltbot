# S-10: Agent Delegation with Model Parameter
**Epic:** E6 — Agent Delegation | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
The `agent_manager` skill has `spawn_agent()` (L101) and `spawn_focused_agent()` (L329), but neither accepts a `model` parameter. The POST body at L124-L128 sends no model key. Meanwhile, the underlying engine layer **already supports model selection**:
- `aria_engine/agent_pool.py` L293: `spawn_agent()` accepts `model` param
- `aria_engine/chat_engine.py` L134: `create_session()` accepts `model` param

The plumbing exists at the engine layer but the skill layer doesn't pass it through. This means Aria cannot delegate a task to a specific model — she always gets the default.

## Root Cause
The `agent_manager` skill was written before multi-model support was added to the engine. The engine was updated but the skill layer was not.

## Fix

### Fix 1: Add model param to spawn_agent()
**File:** `aria_skills/agent_manager/__init__.py` L101-L136

**BEFORE:**
```python
async def spawn_agent(self, name: str, role: str, instructions: str, ...) -> dict:
    """Spawn a new agent in the pool."""
    payload = {
        "name": name,
        "role": role,
        "instructions": instructions,
        ...
    }
    response = await self.api_client.post("/engine/agents/spawn", json=payload)
```

**AFTER:**
```python
async def spawn_agent(self, name: str, role: str, instructions: str, ..., model: str | None = None) -> dict:
    """Spawn a new agent in the pool.
    
    Args:
        model: Optional model ID (e.g. 'kimi', 'deepseek-chat'). 
               If None, uses the session's default model.
    """
    payload = {
        "name": name,
        "role": role,
        "instructions": instructions,
        ...,
    }
    if model is not None:
        payload["model"] = model
    response = await self.api_client.post("/engine/agents/spawn", json=payload)
```

### Fix 2: Add model param to spawn_focused_agent()
**File:** `aria_skills/agent_manager/__init__.py` L329-L357
Same pattern — add `model: str | None = None` param and include in payload if set.

### Fix 3: Verify API accepts model in spawn payload
**File:** `src/api/` — find the `/engine/agents/spawn` endpoint handler
Ensure it reads `model` from the JSON body and passes to `agent_pool.spawn_agent()`.

### Fix 4: Verify agent_pool passes model to engine
**File:** `aria_engine/agent_pool.py` L293
Confirm `spawn_agent(model=...)` correctly passes to `create_session(model=...)`.
This is likely already working — verify, don't change unnecessarily.

### Fix 5: Update skill catalog entry
**File:** `aria_skills/agent_manager/` — update the skill's schema/docs to list `model` as an optional parameter so Aria's routing layer knows it's available.

### Fix 6: Add model validation
In `spawn_agent()`, before passing model to API, validate it exists:
```python
if model is not None:
    # Validate via api_client
    models = await self.api_client.get("/models")
    valid_ids = {m["model_id"] for m in models.get("items", [])}
    if model not in valid_ids:
        return {"error": f"Unknown model: {model}. Available: {valid_ids}"}
    payload["model"] = model
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | skill → api_client → API → engine → DB |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ✅ | Model validation should check against known models |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-03 (model pruning) — so validation checks against clean model list

## Verification
```bash
# 1. Verify spawn_agent accepts model:
grep -n 'def spawn_agent' aria_skills/agent_manager/__init__.py
# EXPECTED: model param in signature

# 2. Verify payload includes model:
grep -A5 'payload.*=' aria_skills/agent_manager/__init__.py | grep 'model'
# EXPECTED: model key in payload

# 3. Integration test — spawn agent with specific model:
curl -X POST http://localhost:8000/engine/agents/spawn \
  -H 'Content-Type: application/json' \
  -d '{"name": "test-agent", "role": "tester", "instructions": "hello", "model": "kimi"}'
# EXPECTED: 200 with agent using kimi model

# 4. Verify spawn with invalid model returns error:
curl -X POST http://localhost:8000/engine/agents/spawn \
  -H 'Content-Type: application/json' \
  -d '{"name": "test", "role": "test", "instructions": "hello", "model": "nonexistent"}'
# EXPECTED: Error response mentioning unknown model

# 5. Verify spawn_focused_agent also has model:
grep -n 'def spawn_focused_agent' aria_skills/agent_manager/__init__.py
# EXPECTED: model param in signature
```

## Prompt for Agent
```
Read these files FIRST:
- aria_skills/agent_manager/__init__.py (full)
- aria_engine/agent_pool.py (L280-L320 — spawn_agent method)
- aria_engine/chat_engine.py (L120-L150 — create_session method)
- src/api/ — find /engine/agents/spawn handler
- aria_skills/catalog.py or registry.py — how skills advertise their parameters

CONSTRAINTS: #1 (5-layer), #3 (validate model exists).

STEPS:
1. Add model: str | None = None to spawn_agent() in agent_manager skill
2. Add model to the payload dict, conditional on not-None
3. Add model param to spawn_focused_agent() same way
4. Verify the API endpoint handler accepts model from JSON body
5. Verify agent_pool.spawn_agent() passes model to create_session()
6. Add model validation using api_client to check against known models
7. Update skill's parameter schema/docs to include model
8. Write a quick smoke test or script in tests/ that spawns an agent with model="kimi"
9. Run verification commands
```
