# S6-09: Fix Rate Limits & API Key Rotation Endpoints (5 endpoints)

## Summary
GET /rate-limits, POST /rate-limits/check, POST /rate-limits/increment, GET /api-key-rotations, and POST /api-key-rotations all disconnect because their tables don't exist. After S6-01 creates the tables, verify these 5 endpoints work end-to-end, including the upsert logic in rate limit increment.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] GET /rate-limits returns list of rate limit entries (empty initially)
- [ ] POST /rate-limits/check accepts a skill name, returns allowed=true/false
- [ ] POST /rate-limits/increment accepts a skill name, creates/updates rate limit counter with upsert
- [ ] GET /api-key-rotations returns list of rotation logs
- [ ] POST /api-key-rotations logs a new rotation event
- [ ] Frontend /rate-limits page loads and displays rate limit data
- [ ] Frontend /api-key-rotations page loads and displays rotation history

## Technical Details
- rate_limits table uses on_conflict_do_update (upsert) via pg_insert — verify the unique constraint on "skill" column exists
- api_key_rotations is simpler CRUD — should work once table exists
- Test the rate limit check logic: does it correctly compare current_count vs max_per_hour?

## Files to Modify
| File | Change |
|------|--------|
| Verification only | no code changes expected if S6-01 and S6-07 are done |
| src/api/routers/operations.py | fix any bugs discovered during testing |

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
- S6-01, S6-07
