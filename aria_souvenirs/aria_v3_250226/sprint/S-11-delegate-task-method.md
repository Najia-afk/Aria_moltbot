# S-11: End-to-End delegate_task() Method
**Epic:** E6 — Agent Delegation | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
After S-10 adds model selection to `spawn_agent()`, the delegation flow is still multi-step and manual:
1. Spawn an agent (with model)
2. Send it a message
3. Poll for completion
4. Collect the result

There is no single `delegate_task()` method that does all of this atomically. Aria's coordinator has to orchestrate these steps itself, which is error-prone and verbose.

## Root Cause
The agent_manager skill only has spawn primitives. No high-level delegation abstraction exists.

## Fix

### Fix 1: Add delegate_task() to agent_manager skill
**File:** `aria_skills/agent_manager/__init__.py`

```python
async def delegate_task(
    self,
    task: str,
    role: str = "assistant",
    model: str | None = None,
    context: str | None = None,
    timeout_seconds: int = 120,
    cleanup: bool = True,
) -> dict:
    """Delegate a task to a new agent and wait for the result.
    
    Spawns a focused agent, sends the task, waits for completion,
    and optionally cleans up the agent.
    
    Args:
        task: The task description / prompt to send
        role: Agent role (e.g. 'analyst', 'coder', 'reviewer')
        model: Optional model ID. None = session default.
        context: Optional context string to prepend to the task
        timeout_seconds: Max wait time before returning partial result
        cleanup: Whether to terminate the agent after task completion
        
    Returns:
        {
            "agent_id": str,
            "model": str,
            "status": "completed" | "timeout" | "error",
            "result": str,
            "tokens_used": int,
            "duration_ms": int
        }
    """
    # 1. Spawn
    agent = await self.spawn_focused_agent(
        name=f"delegate-{role}-{uuid4().hex[:8]}",
        role=role,
        instructions=f"Complete this task: {task}",
        model=model,
    )
    if "error" in agent:
        return {"status": "error", "result": agent["error"], **agent}
    
    agent_id = agent["agent_id"]
    session_id = agent["session_id"]
    
    # 2. Send task with context
    prompt = f"{context}\n\n{task}" if context else task
    message = await self.api_client.post(
        f"/engine/chat/sessions/{session_id}/messages",
        json={"content": prompt}
    )
    
    # 3. Poll for completion
    start = time.monotonic()
    while time.monotonic() - start < timeout_seconds:
        status = await self.api_client.get(f"/engine/agents/{agent_id}/status")
        if status.get("state") in ("completed", "idle"):
            break
        await asyncio.sleep(2)
    
    # 4. Collect result
    result = await self.api_client.get(f"/engine/chat/sessions/{session_id}/messages?last=1")
    
    # 5. Cleanup
    if cleanup:
        await self.api_client.delete(f"/engine/agents/{agent_id}")
    
    return {
        "agent_id": agent_id,
        "model": model or "default",
        "status": "completed" if status.get("state") in ("completed", "idle") else "timeout",
        "result": result.get("content", ""),
        "tokens_used": result.get("tokens_used", 0),
        "duration_ms": int((time.monotonic() - start) * 1000),
    }
```

### Fix 2: Expose via API
**File:** `src/api/` — add endpoint:
```
POST /engine/agents/delegate
{
    "task": "Analyze this code for bugs",
    "role": "reviewer",
    "model": "kimi",
    "context": "File: main.py ...",
    "timeout_seconds": 120
}
```

### Fix 3: Add to roundtable.py
**File:** `aria_engine/roundtable.py` L142
Use `delegate_task()` in `discuss()` so each roundtable participant can be assigned a specific model:
```python
for agent_config in agents:
    result = await agent_manager.delegate_task(
        task=discussion_prompt,
        role=agent_config["role"],
        model=agent_config.get("model"),  # NEW
    )
```

### Fix 4: Add to swarm.py
**File:** `aria_engine/swarm.py` L139
Same pattern — `execute()` uses `delegate_task()` for each swarm worker with model override.

### Fix 5: Register skill parameter schema
Update agent_manager's skill registration to advertise `delegate_task` as a callable action with its full parameter schema.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | skill → api_client → API → engine |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml truth | ✅ | Model validation inherited from S-10 |
| 4 | Docker-first testing | ✅ | Test via Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- **Requires:** S-10 (model param in spawn)
- Enables: S-12 (cron model selection)

## Verification
```bash
# 1. Verify delegate_task exists:
grep -n 'def delegate_task' aria_skills/agent_manager/__init__.py
# EXPECTED: Method definition

# 2. Verify API endpoint:
curl -X POST http://localhost:8000/engine/agents/delegate \
  -H 'Content-Type: application/json' \
  -d '{"task": "Say hello", "role": "test", "model": "kimi", "timeout_seconds": 30}'
# EXPECTED: 200 with result

# 3. Verify roundtable accepts model per agent:
grep 'model' aria_engine/roundtable.py | head -5
# EXPECTED: model= in agent delegation call

# 4. Verify swarm accepts model per worker:
grep 'model' aria_engine/swarm.py | head -5
# EXPECTED: model= in worker delegation call

# 5. Integration test — delegate with timeout:
curl -X POST http://localhost:8000/engine/agents/delegate \
  -H 'Content-Type: application/json' \
  -d '{"task": "Count to 100", "role": "tester", "timeout_seconds": 5}'
# EXPECTED: status="timeout" after 5s
```

## Prompt for Agent
```
Read these files FIRST:
- aria_skills/agent_manager/__init__.py (full — especially spawn_agent and spawn_focused_agent)
- aria_engine/agent_pool.py (full)
- aria_engine/roundtable.py (L130-L200 — discuss method)
- aria_engine/swarm.py (L130-L180 — execute method)
- src/api/ — find agent-related endpoints

CONSTRAINTS: #1 (5-layer), #3 (model validation from S-10).

STEPS:
1. Add delegate_task() method to agent_manager skill (as specified above)
2. Add proper imports (time, asyncio, uuid4)
3. Create API endpoint POST /engine/agents/delegate
4. Wire into roundtable.py discuss() — add model param to agent configs
5. Wire into swarm.py execute() — add model param to worker configs
6. Update skill schema registration
7. Add error handling: agent spawn failure, timeout, API errors
8. Add logging for delegation lifecycle (spawn → send → poll → result → cleanup)
9. Write test in tests/ for delegate_task()
10. Run verification commands
```
