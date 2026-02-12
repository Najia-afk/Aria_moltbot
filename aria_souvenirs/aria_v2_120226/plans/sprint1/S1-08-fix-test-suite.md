# S1-08: Run Full Test Suite & Fix All Failures
**Epic:** Sprint 1 — Critical Bugs | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
The test suite is completely broken due to the Python 3.9 compatibility issue (S1-01). After fixing S1-01, we need to run the full test suite and fix any remaining failures.

**Current state:** `pytest` cannot even collect tests due to ImportError in conftest.py.
**Target state:** `pytest tests/ -q` passes with 0 failures.

The test suite contains 40+ test files covering:
- Architecture compliance
- Model naming/loading/profiles
- Skill naming/persistence
- Agent management
- Kernel functionality
- Memory systems
- Goal management
- Heartbeat
- Knowledge graph
- Security
- Pipeline
- Integration tests

## Root Cause
Primary: Python 3.10 syntax in `aria_agents/context.py` (fixed by S1-01).
Secondary: Unknown — may have additional failures from yesterday's code changes that haven't been tested.

## Fix
1. Apply S1-01 fix first
2. Run `pytest tests/ -q --tb=short`
3. Fix each failure category
4. Re-run until clean

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Tests may verify architecture compliance |
| 2 | .env secrets | ✅ | Tests must not contain real secrets |
| 3 | models.yaml SSOT | ✅ | Model tests verify this |
| 4 | Docker-first | ✅ | Some tests may need running containers |
| 5 | aria_memories writable | ❌ | Tests use temp dirs |
| 6 | No soul modification | ❌ | Tests only read soul |

## Dependencies
**S1-01 must complete first** — test suite cannot import without the Python 3.9 fix.

## Verification
```bash
# 1. Collect tests (verify no import errors):
python3 -m pytest tests/ --collect-only 2>&1 | tail -5
# EXPECTED: "N items collected" (no errors)

# 2. Run full suite:
python3 -m pytest tests/ -q --tb=short 2>&1 | tail -20
# EXPECTED: "N passed" with 0 failures

# 3. If failures, run with verbose for details:
python3 -m pytest tests/ -v --tb=long 2>&1 | grep "FAILED\|ERROR" | head -20
# EXPECTED: no output (no failures)

# 4. Architecture test specifically:
python3 -m pytest tests/test_architecture.py -v 2>&1 | tail -10
# EXPECTED: all pass

# 5. Model tests:
python3 -m pytest tests/test_model_loader.py tests/test_model_naming.py tests/test_model_refs.py -v 2>&1 | tail -10
# EXPECTED: all pass
```

## Prompt for Agent
```
Fix all test suite failures after the Python 3.9 compatibility fix.

**Files to read:**
- tests/conftest.py (full — understand test setup)
- aria_agents/context.py (verify S1-01 fix applied)
- tests/test_imports.py (first failures to check)
- tests/test_architecture.py (architecture compliance)

**Constraints:** All 6 constraints apply — tests verify them.

**Steps:**
1. Verify S1-01 fix is applied: `python3 -c "from aria_agents.context import AgentContext; print('OK')"`
2. Run `python3 -m pytest tests/ --collect-only` — verify collection works
3. Run `python3 -m pytest tests/ -q --tb=short` — get failure summary
4. For each failure:
   a. Read the failing test file
   b. Read the source file it tests
   c. Determine if test is wrong or source is wrong
   d. Fix the source (prefer) or update test (if test is outdated)
5. Re-run until clean
6. Report final test count and status
```
