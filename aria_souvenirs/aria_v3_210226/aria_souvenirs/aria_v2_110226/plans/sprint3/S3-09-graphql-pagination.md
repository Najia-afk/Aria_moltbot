# S3-09: Add Pagination to GraphQL Queries
**Epic:** E2 — Pagination | **Priority:** P2 | **Points:** 3 | **Phase:** 2

## Problem
GraphQL queries accept `limit` but no `offset`. After S2-06 adds REST pagination, GQL should match.

## Root Cause
GQL resolvers written before pagination existed.

## Fix

### File: `src/api/gql/schema.py`
Add `offset: int = 0` to all list queries. Change default `limit` from 100 to 25.

### File: `src/api/gql/resolvers.py`
Add `.offset(offset)` to all resolve_ functions. Accept `offset` parameter.

Apply to: resolve_activities, resolve_thoughts, resolve_memories, resolve_goals, resolve_sessions, resolve_knowledge_entities, resolve_knowledge_relations.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | GQL layer |
| 2 | .env | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test via GQL |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- S2-06 (REST pagination) as reference.

## Verification
```bash
grep 'offset' src/api/gql/schema.py | wc -l
# EXPECTED: 7+
curl -s -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ goals(limit:5, offset:5) { id title } }"}'
# EXPECTED: Goals 6-10
```

## Prompt for Agent
```
Add pagination (offset) to all Aria GraphQL queries.
FILES: src/api/gql/schema.py, resolvers.py
```
