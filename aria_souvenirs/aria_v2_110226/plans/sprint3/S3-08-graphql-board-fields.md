# S3-08: Add Sprint Board Fields to GraphQL Schema
**Epic:** E5 — Sprint Board | **Priority:** P2 | **Points:** 2 | **Phase:** 2

## Problem
GraphQL `GoalType` doesn't include sprint, board_column, position, assigned_to, tags, updated_at.

## Root Cause
New DB fields from S3-01 weren't added to GQL types.

## Fix

### File: `src/api/gql/types.py`
Add to GoalType: `sprint: Optional[str]; board_column: Optional[str]; position: int; assigned_to: Optional[str]; tags: Optional[JSON]; updated_at: Optional[str]`

### File: `src/api/gql/resolvers.py`
Update resolve_goals to map new fields.

### File: `src/api/gql/schema.py`
Add `goal_board` and `sprint_summary` queries returning JSON type.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | GQL layer |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | GraphQL playground |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- S3-01 (model fields), S3-02 (API endpoints)

## Verification
```bash
grep -E 'sprint|board_column|assigned_to' src/api/gql/types.py
# EXPECTED: fields present
curl -s -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ goals(limit:1) { id sprint boardColumn } }"}'
# EXPECTED: valid response
```

## Prompt for Agent
```
Add sprint board fields to Aria GraphQL schema.
FILES: src/api/gql/types.py, resolvers.py, schema.py, db/models.py
```
