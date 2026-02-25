# S-22: LLM Gateway Timeout & Skill Circuit Breakers
**Epic:** E12 — Engine Resilience | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
### Problem A: No timeout on LLM calls
`aria_engine/llm_gateway.py` L155-250: `complete()` calls `acompletion(**kwargs)` with no `asyncio.wait_for()` timeout. If a provider hangs (Moonshot outage, OpenRouter rate-limited without response), the coroutine blocks indefinitely. The streaming path at L260-315 has the same issue. Only the scheduler wraps calls in `asyncio.wait_for(timeout)` at `scheduler.py` L336.

### Problem B: No skill-level circuit breaker
A circuit breaker exists for the LLM gateway only (`_circuit_failures`, `_circuit_threshold=5`, `_circuit_reset_after=30s` at `llm_gateway.py` L139-154). Individual skills (Moltbook, Telegram, Ollama, knowledge_graph, etc.) have NO circuit breaker. A consistently failing external API will be hammered on every invocation.

### Problem C: Inconsistent safe_execute usage
`BaseSkill` provides `safe_execute()` at `base.py` L363-408 with retry + metrics, but most skills call APIs directly with manual `try/except`, bypassing retry logic and Prometheus metrics.

## Fix

### Fix 1: Add timeout to LLM complete()
**File:** `aria_engine/llm_gateway.py` L155-250
```python
async def complete(self, messages, model=None, timeout: int = 120, **kwargs):
    # ... existing circuit breaker check ...
    try:
        result = await asyncio.wait_for(
            acompletion(model=model, messages=messages, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"LLM call timed out after {timeout}s for model={model}")
        self._record_circuit_failure(model)
        raise LLMTimeoutError(f"Model {model} timed out after {timeout}s")
```

### Fix 2: Add timeout to LLM stream()
**File:** `aria_engine/llm_gateway.py` L260-315
Wrap the stream creation in `asyncio.wait_for()`. For active streams, add a per-chunk timeout.

### Fix 3: Create generic CircuitBreaker class
**File:** `aria_engine/circuit_breaker.py` (NEW)
```python
class CircuitBreaker:
    """Generic circuit breaker for any external service."""
    
    def __init__(self, name: str, threshold: int = 5, reset_after: float = 60.0):
        self.name = name
        self.threshold = threshold
        self.reset_after = reset_after
        self._failures = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed, open, half-open
    
    def is_open(self) -> bool:
        if self._state == "open":
            if time.monotonic() - self._last_failure_time > self.reset_after:
                self._state = "half-open"
                return False
            return True
        return False
    
    def record_success(self):
        self._failures = 0
        self._state = "closed"
    
    def record_failure(self):
        self._failures += 1
        self._last_failure_time = time.monotonic()
        if self._failures >= self.threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker OPEN for {self.name} after {self._failures} failures")
```

### Fix 4: Add circuit breaker to BaseSkill
**File:** `aria_skills/base.py`
```python
class BaseSkill:
    def __init__(self, ...):
        self._circuit = CircuitBreaker(name=self.name, threshold=5, reset_after=60)
    
    async def safe_execute(self, fn, *args, **kwargs):
        if self._circuit.is_open():
            return SkillResult.fail(f"Circuit open for {self.name}")
        try:
            result = await fn(*args, **kwargs)
            self._circuit.record_success()
            return result
        except Exception as e:
            self._circuit.record_failure()
            raise
```

### Fix 5: Expose circuit breaker state via Prometheus
**File:** `aria_engine/metrics.py`
Wire the `llm_circuit_breaker_state` gauge for each skill:
```python
skill_circuit_state = Gauge('aria_skill_circuit_state', 'Circuit breaker state', ['skill_name'])
```

### Fix 6: Migrate key skills to use safe_execute
Priority skills to migrate:
- `aria_skills/knowledge_graph/__init__.py` L70-80 — direct try/except
- `aria_skills/moltbook/__init__.py` L141-149 — direct try/except
- All skills that call external APIs

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Engine layer changes |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — standalone resilience improvement.

## Verification
```bash
# 1. LLM timeout exists:
grep 'wait_for' aria_engine/llm_gateway.py
# EXPECTED: asyncio.wait_for in both complete() and stream()

# 2. CircuitBreaker class exists:
python -c "from aria_engine.circuit_breaker import CircuitBreaker; print('OK')"
# EXPECTED: OK

# 3. BaseSkill uses circuit breaker:
grep 'circuit' aria_skills/base.py
# EXPECTED: CircuitBreaker initialization and usage

# 4. Prometheus gauge exists:
grep 'skill_circuit' aria_engine/metrics.py
# EXPECTED: Gauge definition

# 5. Manual: Kill LiteLLM, send 6 messages, verify circuit opens
# EXPECTED: After 5 failures, next call returns "Circuit open" immediately
```

## Prompt for Agent
```
Read these files FIRST:
- aria_engine/llm_gateway.py (full — focus on complete() L155+ and stream() L260+)
- aria_skills/base.py (full — focus on safe_execute L363 and execute_with_retry L240)
- aria_engine/metrics.py (L110-L130 — circuit breaker gauge)
- aria_skills/knowledge_graph/__init__.py (L60-L100 — direct API call example)

CONSTRAINTS: #1 (engine layer).

STEPS:
1. Create aria_engine/circuit_breaker.py with generic CircuitBreaker class
2. Add asyncio.wait_for(timeout=120) to llm_gateway.complete()
3. Add timeout to llm_gateway.stream() (per-stream + per-chunk)
4. Add CircuitBreaker to BaseSkill.__init__()
5. Wire safe_execute to use circuit breaker (check before, record after)
6. Add Prometheus gauge for per-skill circuit state
7. Migrate knowledge_graph, moltbook to use safe_execute
8. Add LLMTimeoutError to aria_engine/exceptions.py
9. Run tests to verify no regressions
10. Simulate timeout by temporarily setting timeout=1 and calling a slow model
```
