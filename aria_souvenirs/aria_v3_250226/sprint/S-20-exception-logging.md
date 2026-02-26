# S-20: Exception Logging — Eliminate Silent Swallowing
**Epic:** E11 — API Quality | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
21+ `except Exception: pass` or `except Exception: continue` blocks across the API silently swallow errors, making production debugging nearly impossible.

### Affected Files (representative, 21+ total)
| File | Line | Context |
|------|------|---------|
| `src/api/routers/health.py` | L67 | Host stats fetch error swallowed |
| `src/api/routers/engine_chat.py` | L502 | WebSocket close error swallowed |
| `src/api/routers/memories.py` | L402 | Embedding error swallowed |
| `src/api/routers/sessions.py` | L282 | LiteLLM error swallowed |
| `src/api/routers/analysis.py` | L247 | Data parsing error swallowed |
| `src/api/routers/analysis.py` | L569 | Analysis error swallowed |
| `src/api/sentiment_autoscorer.py` | L243 | Scoring error swallowed |
| `src/api/routers/engine_roundtable.py` | L935 | WS error swallowed |
| `src/api/routers/engine_roundtable.py` | L1038 | Synthesis error swallowed |

## Root Cause
Quick development pattern of wrapping risky calls in `try/except: pass` to avoid crashing. Never revisited.

## Fix

### Fix 1: Add logging to every bare except
For each `except Exception: pass`:

**BEFORE:**
```python
try:
    result = await some_operation()
except Exception:
    pass
```

**AFTER:**
```python
try:
    result = await some_operation()
except Exception:
    logger.warning("some_operation failed", exc_info=True)
```

### Decision matrix for log level:
| Context | Level | Example |
|---------|-------|---------|
| Data enrichment, optional | `DEBUG` | Host stats in /health |
| WebSocket cleanup | `DEBUG` | WS close in engine_chat |
| Embedding generation | `WARNING` | memories.py — data integrity |
| LLM call failure | `ERROR` | sessions.py — core functionality |
| Data parsing in loop | `WARNING` | analysis.py — partial data loss |
| Synthesis generation | `ERROR` | roundtable.py — core output |

### Fix 2: Update GraphQL resolvers
**File:** `src/api/gql/resolvers.py` L52-200
Add try/except with proper logging and Strawberry error returns:
```python
@strawberry.field
def activities(self, info, limit: int = 25, offset: int = 0) -> list[Activity]:
    try:
        return await _fetch_activities(limit, offset)
    except Exception:
        logger.error("GraphQL: activities resolver failed", exc_info=True)
        raise  # Let Strawberry handle the error response
```

### Fix 3: Ensure all routers have logger configured
Verify each router file has:
```python
import logging
logger = logging.getLogger(__name__)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Logging only, no logic change |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-24 (structured logging) should come first to ensure logs are in JSON format.

## Verification
```bash
# 1. No bare except:pass remaining:
grep -rn 'except.*:\s*$' src/api/ --include='*.py' -A1 | grep -c 'pass$'
# EXPECTED: 0

# 2. All except blocks have logging:
grep -rn 'except Exception' src/api/ --include='*.py' -A2 | grep -c 'logger\.\(debug\|info\|warning\|error\)'
# EXPECTED: ≥ 21

# 3. All routers have logger:
for f in src/api/routers/*.py; do
  if ! grep -q 'logger = logging' "$f"; then
    echo "MISSING LOGGER: $f"
  fi
done
# EXPECTED: No output
```

## Prompt for Agent
```
STEPS:
1. grep -rn 'except.*Exception.*:' src/api/ to find ALL bare exception handlers
2. For each, read surrounding context to determine appropriate log level
3. Add logger.warning/error/debug with exc_info=True
4. Verify each router file has `import logging; logger = logging.getLogger(__name__)`
5. Do NOT change any business logic — only add logging
6. Do NOT remove any try/except blocks — they exist for resilience
7. Run verification greps
```
