# S4-08: Add Knowledge Graph Queries to GraphQL
**Epic:** E8 — Knowledge Graph | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem
The new knowledge graph endpoints (traverse, search, skill-for-task) are only available via REST. GraphQL should expose them too for flexibility.

## Root Cause
New endpoints were added to REST but not to the GraphQL schema.

## Fix

### File: `src/api/gql/types.py`
Add new types:
```python
@strawberry.type
class GraphTraversalResult:
    nodes: list[KnowledgeEntityType]
    edges: list[KnowledgeRelationType]
    node_count: int
    edge_count: int
    start: str

@strawberry.type
class SkillCandidate:
    skill: str
    match_type: str
    description: Optional[str]
    matched_tool: Optional[str] = None
    layer: Optional[int] = None

@strawberry.type
class SkillForTaskResult:
    task: str
    candidates: list[SkillCandidate]
    count: int
```

### File: `src/api/gql/schema.py`
Add queries:
```python
@strawberry.field
async def graph_traverse(self, start_name: str, relation_type: Optional[str] = None, max_depth: int = 2) -> JSON:
    return await resolve_graph_traverse(start_name, relation_type, max_depth)

@strawberry.field
async def skill_for_task(self, task: str) -> JSON:
    return await resolve_skill_for_task(task)
```

### File: `src/api/gql/resolvers.py`
Add resolver functions wrapping the REST logic.

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
- S4-02 (REST pathfinding endpoints)

## Verification
```bash
# 1. GraphQL traverse:
curl -s -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ graphTraverse(startName: \"api_client\") }"}'
# EXPECTED: valid response

# 2. GraphQL skill discovery:
curl -s -X POST http://localhost:8000/api/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ skillForTask(task: \"telegram\") }"}'
# EXPECTED: candidates list
```

## Prompt for Agent
```
Add knowledge graph queries to Aria's GraphQL schema.
FILES: src/api/gql/types.py, schema.py, resolvers.py
STEPS: 1. Add types 2. Add queries 3. Add resolvers 4. Verify
```
