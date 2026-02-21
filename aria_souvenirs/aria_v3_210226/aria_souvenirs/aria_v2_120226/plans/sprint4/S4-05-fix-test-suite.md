# S4-05: Fix and Expand Test Suite
**Epic:** Sprint 4 — Reliability & Self-Healing | **Priority:** P0 | **Points:** 5 | **Phase:** 4

## Problem
The test suite is **completely broken** on the host:
```
ImportError: cannot import name 'AgentContext' from 'aria_agents.context'
```

Root cause: the host Mac Mini runs Python 3.9.6 (Apple system Python) which can't parse `str | None` syntax. **S1-01 fixes this by upgrading the host to Python 3.12+.** Once the host Python is upgraded, the import error disappears — but the test suite still needs attention:

- Test files may be outdated after the Sprint 1–7 refactoring marathon (74 tickets)
- No API endpoint integration tests that actually hit the running API
- No CI pipeline enforces test passage

## Root Cause
1. Host Python too old (S1-01 fixes this — upgrade to 3.12+)
2. Tests were not updated as code was refactored across 74 tickets
3. No CI pipeline enforces test passage

## Fix

### Phase 1: Unblock Tests (depends on S1-01)
```bash
# After S1-01 fixes context.py:
cd /Users/najia/aria
python -m pytest tests/ -q --tb=short 2>&1 | head -40
```

### Phase 2: Fix Broken Tests
For each test failure:
1. Read the test file
2. Read the source file it tests
3. Determine if the test is outdated (wrong imports, changed API) or genuinely failing
4. Fix or skip with `@pytest.mark.skip(reason="needs update after Sprint X")`

### Phase 3: Add Missing Coverage
Priority endpoint tests to add:
```python
# tests/test_api_endpoints.py
import httpx
import pytest

API_BASE = "http://localhost:8000"

@pytest.mark.asyncio
async def test_health():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"

@pytest.mark.asyncio
async def test_goals_list():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{API_BASE}/api/goals")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

# ... repeat for all 17 working endpoints
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Tests must respect layers — no SQLAlchemy imports in skill tests |
| 2 | .env secrets | ✅ | Use config/test env vars, not hardcoded secrets |
| 3 | models.yaml SSOT | ✅ | No hardcoded model names in tests |
| 4 | Docker-first | ✅ | Integration tests need running containers |
| 5 | aria_memories writable | ❌ | Test files in tests/ |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
**S1-01 must be complete** — tests cannot run until Python 3.9 compat is fixed.

## Verification
```bash
# 1. Tests run without import errors:
python -m pytest tests/ -q --tb=short 2>&1 | tail -5
# EXPECTED: no ImportError, shows pass/fail summary

# 2. At least N tests pass:
python -m pytest tests/ -q 2>&1 | grep "passed"
# EXPECTED: X passed (should be majority)

# 3. No Python 3.10+ syntax issues — host is 3.12+ after S1-01:
python3 --version
# EXPECTED: Python 3.12.x or 3.13.x

# 4. Integration tests exist:
ls tests/test_api_endpoints.py 2>/dev/null
# EXPECTED: file exists

# 5. Integration tests pass (requires running containers):
python -m pytest tests/test_api_endpoints.py -q 2>&1
# EXPECTED: all pass
```

## Prompt for Agent
```
Fix the broken test suite and add missing endpoint coverage.

**Files to read FIRST:**
- aria_agents/context.py (full — verify S1-01 fix was applied: host Python is now 3.12+, modern syntax is fine)
- tests/conftest.py (full — understand the import chain and fixtures)
- tests/ — list ALL files to understand test scope and coverage
- src/api/main.py (lines 1-80 — list all mounted routers for endpoint test targets)
- src/api/routers/ — list all files to know which endpoints need integration tests

**Constraints:**
- Constraint 1 (5-layer): test files must NOT import SQLAlchemy directly — use api_client or httpx
- Constraint 2 (secrets): use env vars or test config, never hardcode API keys
- Constraint 3 (models.yaml): no hardcoded model names in tests
- Constraint 4 (Docker-first): integration tests need running containers (aria-api, aria-db)
- S1-01 must be complete: host Python upgraded to 3.12+, modern syntax (str | None) is valid

**Steps:**
1. Verify S1-01 is in place:
   a. Run: python3 --version
   b. EXPECTED: Python 3.12.x or 3.13.x (NOT 3.9)
   c. Run: python3 -c "from aria_agents.context import AgentContext; print('OK')"
   d. EXPECTED: "OK" (no ImportError)
2. Run pytest and capture ALL errors:
   a. Run: python3 -m pytest tests/ -q --tb=short 2>&1 | tee /tmp/pytest_output.txt
   b. Run: grep -c "FAILED\|ERROR" /tmp/pytest_output.txt
   c. Document: total collected, passed, failed, errors
3. Triage each failure (read the test file AND the source it tests):
   a. Category A (stale imports): test imports a function/class that was renamed/moved → fix the import
   b. Category B (changed API shape): test expects old response format → update assertions
   c. Category C (missing fixture): test needs a DB or service that isn't mocked → skip with reason
   d. Category D (genuine bug): test reveals actual broken code → create a follow-up ticket
   e. For each: decide FIX (< 5 min) or SKIP with `@pytest.mark.skip(reason="needs update: <detail>")`
4. Fix all Category A and B failures:
   a. For each, read the test file and the source it imports
   b. Make minimal changes to the test — do NOT refactor the source to match old tests
5. Create tests/test_api_endpoints.py:
   a. Use httpx.AsyncClient for all tests (async, supports timeout)
   b. API_BASE = "http://localhost:8000"
   c. Add tests for ALL 17 working endpoints:
      - GET /health → 200, status=healthy, database=connected
      - GET /api/goals → 200, isinstance list
      - GET /api/memories → 200
      - GET /api/thoughts → 200
      - GET /api/activities → 200
      - GET /api/sessions → 200
      - GET /api/kg/entities → 200
      - GET /api/working-memory → 200
      - GET /api/lessons → 200
      - GET /api/litellm/spend → 200
      - GET /api/litellm/models → 200
      - GET /api/model-usage → 200
      - GET /api/providers/balances → 200
      - GET /api/skills → 200
      - GET /api/proposals → 200
      - GET /api/records → 200
      - POST /graphql → 200 (with simple introspection query)
   d. Each test: assert status_code, assert response is valid JSON, assert basic shape
6. Run full suite again:
   a. Run: python3 -m pytest tests/ -q --tb=short 2>&1
   b. Target: 0 errors, > 80% passing
   c. Run: python3 -m pytest tests/test_api_endpoints.py -v 2>&1
   d. EXPECTED: all 17 endpoint tests pass
7. Document results:
   a. Add a comment block at top of any skipped test explaining WHY and WHAT to fix
   b. Final report: X total, Y passed, Z skipped, W failed (with reasons)
```
