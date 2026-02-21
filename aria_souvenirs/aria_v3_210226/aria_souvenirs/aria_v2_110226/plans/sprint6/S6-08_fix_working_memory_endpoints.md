# S6-08: Fix Working Memory Endpoints (4 endpoints)

## Summary
All four working memory endpoints disconnect the server because the `working_memory` table doesn't exist. After S6-01 creates the table and S6-07 adds error handling, verify these endpoints work end-to-end. Also validate that the CRUD operations, context aggregation, and checkpoint creation work correctly.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] POST /working-memory creates a working memory item successfully
- [ ] GET /working-memory returns list of items with pagination
- [ ] GET /working-memory/context returns aggregated context from recent items
- [ ] POST /working-memory/checkpoint creates a snapshot of current working memory
- [ ] DELETE /working-memory/{id} removes an item
- [ ] Frontend /working-memory page loads and displays items, context, and checkpoints
- [ ] All stat cards on the page show actual values (not "-")

## Technical Details
- After S6-01 runs ensure_schema() successfully, verify working_memory table exists
- Test each endpoint manually and with the api_client skill functions (remember, recall, get_working_memory_context, working_memory_checkpoint)
- Verify the frontend template renders correctly with real data
- Check for any additional bugs in the handlers now that the table exists

## Files to Modify
| File | Change |
|------|--------|
| Verification only | no code changes expected if S6-01 and S6-07 are done |
| src/api/routers/working_memory.py | fix any bugs discovered during testing |

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
