# S6-03: Fix move_goal 500 Error & Board Column Validation

## Summary
PATCH /goals/{id}/move returns 500 when the request body is missing `board_column` or contains an invalid column name. The handler at goals.py L175 doesn't validate input before updating the database. The column_to_status mapping silently passes None through, and the SQL UPDATE can fail on constraint violations.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 3
- **Sprint**: 6 — Production Stabilization

## Acceptance Criteria
- [ ] PATCH /goals/{id}/move returns 400 with clear error when board_column is missing or invalid
- [ ] Valid board_column values documented and enforced: "backlog", "todo", "in_progress", "review", "done"
- [ ] Drag-and-drop on /sprint-board page works end-to-end
- [ ] Status auto-mapping (e.g., moving to "done" column sets status to "completed") verified
- [ ] completed_at set correctly when moving to "done", cleared when moving away from "done"

## Technical Details
- Add Pydantic model for move request body with board_column as required field
- Validate board_column against allowed values, return 400 with allowed_columns list on invalid
- Fix the column_to_status.get(None) edge case
- Ensure completed_at uses datetime.utcnow() instead of sa_text("NOW()") for SQLAlchemy compatibility
- Add unit test for valid/invalid move requests

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/goals.py | add validation, fix move_goal handler |
| src/web/templates/sprint_board.html | improve error message on drag-drop failure |

## Constraints Checklist
| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | 5-layer | - | - |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | - | - |
| 4 | Docker-first | ✅ | Docker rebuild |
| 5 | aria_memories only | - | - |
| 6 | No soul edit | ❌ | Untouched |

## Dependencies
- None
