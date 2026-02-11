# S6-07: Add Router-Level Exception Handlers for DB Errors

## Summary
When a table is missing, SQLAlchemy raises `ProgrammingError: relation "xxx" does not exist`. Currently this crashes the async connection handler, causing the server to disconnect without any response. Every router that queries the DB should have a catch for this error pattern, returning a clean 503 with a diagnostic message instead of crashing.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] Add a FastAPI exception handler for `sqlalchemy.exc.ProgrammingError` that returns 503 with `{"error": "Database table not available", "detail": "..."}`
- [ ] Add a FastAPI exception handler for `sqlalchemy.exc.OperationalError` that returns 503 with `{"error": "Database connection error", "detail": "..."}`
- [ ] Server no longer disconnects on missing table queries — returns clean JSON error
- [ ] Frontend receives 503 and can show "Service temporarily unavailable" instead of hanging
- [ ] All 18 previously-disconnecting endpoints now return 503 JSON instead of crashing

## Technical Details
- Add global exception handlers in src/api/main.py using `@app.exception_handler(ProgrammingError)`
- This is a global catch — no need to modify individual routers
- Log the full traceback at ERROR level for debugging
- Return JSON with enough detail for the /health/db endpoint to cross-reference
- Consider also catching `asyncpg.exceptions.UndefinedTableError`

## Files to Modify
| File | Change |
|------|--------|
| src/api/main.py | add global exception handlers for SQLAlchemy DB errors |

## Constraints Checklist
| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer | ✅ | - |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | - | - |
| 4 | Docker-first | ✅ | Docker rebuild |
| 5 | aria_memories only | - | - |
| 6 | No soul edit | ❌ | Untouched |

## Dependencies
- None (can be done independently, provides immediate value even before S6-01)
