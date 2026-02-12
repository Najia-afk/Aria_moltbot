# S4-03: Add Error Recovery to api_client
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P1 | **Points:** 3 | **Phase:** 4

## Problem
The `api_client` module (`aria_skills/api_client/__init__.py`, 1013+ lines) is the single gateway for all Skills → API communication. Currently:
- **No retry on transient errors** — a single 502/503/504 fails the entire skill
- **No circuit breaker** — if API is overloaded, all skills hammer it simultaneously
- **No timeout standardization** — some calls use defaults (5s), others use custom timeouts
- **Connection pool exhaustion** — no limit on concurrent requests

When one API call fails, the calling skill fails, the agent fails, and Aria logs an error. A 2-second network blip cascades into a full work cycle failure.

## Root Cause
The api_client was built as a thin httpx wrapper without production resilience patterns.

## Fix
Add to `aria_skills/api_client/__init__.py`:

### 1. Retry with Exponential Backoff
```python
import asyncio
from typing import Optional

MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0  # seconds
RETRYABLE_STATUS = {502, 503, 504, 408, 429}

async def _request_with_retry(
    method: str, 
    url: str, 
    retries: int = MAX_RETRIES,
    **kwargs
) -> httpx.Response:
    """Make HTTP request with retry on transient errors."""
    last_error: Optional[Exception] = None
    
    for attempt in range(retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code in RETRYABLE_STATUS and attempt < retries:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            return response
        except (httpx.ConnectError, httpx.ReadTimeout) as e:
            last_error = e
            if attempt < retries:
                delay = RETRY_DELAY_BASE * (2 ** attempt)
                await asyncio.sleep(delay)
    
    raise last_error or Exception("Request failed after retries")
```

### 2. Circuit Breaker (Simple)
```python
import time

class CircuitBreaker:
    """Simple circuit breaker — opens after N failures, closes after cooldown."""
    def __init__(self, failure_threshold: int = 5, cooldown: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown = cooldown
        self.failures = 0
        self.last_failure_time = 0.0
        self.is_open = False
    
    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.is_open = True
    
    def record_success(self):
        self.failures = 0
        self.is_open = False
    
    def can_proceed(self) -> bool:
        if not self.is_open:
            return True
        # Check if cooldown has elapsed
        if time.time() - self.last_failure_time > self.cooldown:
            self.is_open = False  # Half-open: try one request
            return True
        return False

_circuit = CircuitBreaker()
```

### 3. Default Timeout
```python
DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | api_client is Layer 4 — changes must NOT break the API surface |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Test in container |
| 5 | aria_memories writable | ❌ | Code changes only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone improvement to existing module.

## Verification
```bash
# 1. Retry logic exists:
grep -n "retry\|RETRY\|exponential\|backoff" aria_skills/api_client/__init__.py
# EXPECTED: multiple matches

# 2. Circuit breaker exists:
grep -n "CircuitBreaker\|circuit\|_circuit" aria_skills/api_client/__init__.py
# EXPECTED: class and instance defined

# 3. Default timeout set:
grep -n "DEFAULT_TIMEOUT\|Timeout" aria_skills/api_client/__init__.py
# EXPECTED: timeout configuration

# 4. Existing API calls still work:
curl -s http://localhost:8000/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])"
# EXPECTED: healthy

# 5. Skills still work through api_client:
docker exec aria-api python -c "
from aria_skills.api_client import AriaClient
print('api_client imports successfully')
"
# EXPECTED: "api_client imports successfully"

# 6. Modern Python syntax is fine (host is 3.12+ after S1-01):
python3 --version
# EXPECTED: Python 3.12.x or 3.13.x
```

## Prompt for Agent
```
Add retry, circuit breaker, and timeout defaults to the api_client module.

**Files to read:**
- aria_skills/api_client/__init__.py (FULL — this is the main file, 1013+ lines)
- aria_skills/api_client/ (list all files)

**Steps:**
1. Read the full api_client to understand its structure
2. Add CircuitBreaker class (simple, not a library dependency)
3. Add _request_with_retry() that wraps all HTTP methods
4. Add DEFAULT_TIMEOUT constant
5. Update existing get/post/put/delete methods to use retry wrapper
6. Use Optional[str] NOT str | None (Python 3.9 compat!)
7. Test import works: docker exec aria-api python -c "from aria_skills.api_client import AriaClient"
8. Test API health still returns healthy
```
