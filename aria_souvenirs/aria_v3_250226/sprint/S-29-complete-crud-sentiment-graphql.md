# S-29: Complete CRUD Endpoints + Sentiment API + GraphQL Mutations
**Epic:** E16 — Missing API Endpoints | **Priority:** P2 | **Points:** 5 | **Phase:** 3

## Problem
The API has significant coverage gaps:

### 1. Missing DELETE/UPDATE on 8+ entities
Only 2 of ~15 entity types have full CRUD. Most have only GET and POST:

| Entity | GET | POST | PUT/PATCH | DELETE |
|--------|-----|------|-----------|--------|
| thoughts | ✅ | ✅ | ❌ | ❌ |
| activities | ✅ | ✅ | ❌ | ❌ |
| model_usage | ✅ | ✅ | ❌ | ❌ |
| security_events | ✅ | ✅ | ❌ | ❌ |
| proposals | ✅ | ✅ | ❌ | ❌ |
| knowledge_graph | ✅ | ✅ | ❌ | ❌ |
| analysis | ✅ | ✅ | ❌ | ❌ |
| cron_runs | ✅ | ❌ | ❌ | ❌ |

### 2. Sentiment table has no REST router
`src/api/db/models.py` defines `SentimentEvent` at L525-564 with full columns, but there is NO `routers/sentiment.py`. The web UI calls `/api/sentiment/events` via the proxy.

### 3. GraphQL has only 2 mutations
**File:** `src/api/gql/schema.py` L108-117 — only `upsert_memory` and `update_goal`.  
Missing mutations for: thoughts, activities, sessions, proposals, knowledge_graph, security_events, model_usage.

### 4. GraphQL uses offset/limit only
**File:** `src/api/gql/schema.py` L41-100 — all queries use `offset` and `limit` parameters. No cursor-based pagination (first/after).  
At 89 tables and growing, offset pagination causes performance degradation at scale.

### 5. GraphQL resolvers have no error handling
**File:** `src/api/gql/resolvers.py` L52-200 — raw DB queries without try/except. Any DB error crashes the GraphQL response.

## Root Cause
API was built feature-by-feature for the web UI's read-heavy workflow. Write/delete operations were deferred. GraphQL was added as a secondary layer with minimal mutations.

## Fix

### Fix 1: Add DELETE/UPDATE to existing routers
For each entity missing DELETE/UPDATE, add endpoints following the pattern in `goals.py` (which has full CRUD):

```python
# Example: src/api/routers/thoughts.py
@router.put("/{thought_id}")
async def update_thought(thought_id: int, data: ThoughtUpdate, db: Session = Depends(get_db)):
    thought = db.query(Thought).filter(Thought.id == thought_id).first()
    if not thought:
        raise HTTPException(404, "Thought not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(thought, field, value)
    db.commit()
    db.refresh(thought)
    return thought

@router.delete("/{thought_id}")
async def delete_thought(thought_id: int, db: Session = Depends(get_db)):
    thought = db.query(Thought).filter(Thought.id == thought_id).first()
    if not thought:
        raise HTTPException(404, "Thought not found")
    db.delete(thought)
    db.commit()
    return {"deleted": True}
```

### Fix 2: Create Sentiment router
**File:** `src/api/routers/sentiment.py` (NEW)
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db.session import get_db
from ..db.models import SentimentEvent
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/sentiment", tags=["sentiment"])

class SentimentEventCreate(BaseModel):
    session_id: Optional[int] = None
    source: str
    text_sample: Optional[str] = None
    sentiment_label: str
    sentiment_score: float
    confidence: float
    model_used: Optional[str] = None

class SentimentEventResponse(BaseModel):
    id: int
    session_id: Optional[int]
    source: str
    sentiment_label: str
    sentiment_score: float
    confidence: float
    scored_at: datetime

    class Config:
        from_attributes = True

@router.get("/events")
async def list_events(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    return db.query(SentimentEvent).order_by(SentimentEvent.scored_at.desc()).offset(offset).limit(limit).all()

@router.post("/events", response_model=SentimentEventResponse)
async def create_event(data: SentimentEventCreate, db: Session = Depends(get_db)):
    event = SentimentEvent(**data.dict())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

@router.get("/events/{event_id}")
async def get_event(event_id: int, db: Session = Depends(get_db)):
    ...

@router.get("/summary")
async def sentiment_summary(hours: int = 24, db: Session = Depends(get_db)):
    """Aggregate sentiment stats for dashboard charts."""
    ...
```

Register in `main.py`:
```python
from .routers import sentiment
app.include_router(sentiment.router, prefix="/api")
```

### Fix 3: Add GraphQL mutations
**File:** `src/api/gql/schema.py`
Add mutations for all core entities using Strawberry:
```python
@strawberry.type
class Mutation:
    @strawberry.mutation
    async def upsert_memory(self, info, ...) -> Memory: ...

    @strawberry.mutation
    async def update_goal(self, info, ...) -> Goal: ...

    # NEW mutations:
    @strawberry.mutation
    async def create_thought(self, info, content: str, category: Optional[str] = None) -> Thought: ...

    @strawberry.mutation
    async def delete_thought(self, info, id: int) -> bool: ...

    @strawberry.mutation
    async def create_activity(self, info, activity_type: str, description: str) -> Activity: ...

    @strawberry.mutation
    async def create_proposal(self, info, title: str, description: str, proposed_by: str) -> Proposal: ...

    @strawberry.mutation
    async def update_proposal_status(self, info, id: int, status: str) -> Proposal: ...

    @strawberry.mutation
    async def create_session(self, info, session_type: str) -> Session: ...
```

### Fix 4: Add cursor-based pagination
**File:** `src/api/gql/schema.py`
```python
@strawberry.type
class PageInfo:
    has_next_page: bool
    end_cursor: Optional[str]

@strawberry.type
class ThoughtEdge:
    node: ThoughtType
    cursor: str

@strawberry.type
class ThoughtConnection:
    edges: list[ThoughtEdge]
    page_info: PageInfo

@strawberry.type
class Query:
    @strawberry.field
    async def thoughts_paginated(
        self, info, first: int = 20, after: Optional[str] = None
    ) -> ThoughtConnection:
        db = info.context["db"]
        query = db.query(Thought).order_by(Thought.id)
        if after:
            cursor_id = int(base64.b64decode(after))
            query = query.filter(Thought.id > cursor_id)
        items = query.limit(first + 1).all()
        has_next = len(items) > first
        edges = [
            ThoughtEdge(node=t, cursor=base64.b64encode(str(t.id).encode()).decode())
            for t in items[:first]
        ]
        return ThoughtConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=has_next,
                end_cursor=edges[-1].cursor if edges else None
            )
        )
```

### Fix 5: Add error handling to resolvers
**File:** `src/api/gql/resolvers.py`
Wrap every resolver in try/except:
```python
@strawberry.field
async def thoughts(self, info, limit: int = 50, offset: int = 0) -> list[ThoughtType]:
    try:
        db = info.context["db"]
        return db.query(Thought).offset(offset).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"GraphQL thoughts resolver failed: {e}")
        raise GraphQLError("Failed to fetch thoughts")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | API layer only |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | Test in Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-19 (Pydantic models) — new endpoints should use Pydantic models from day one
- S-16 (auth) — new endpoints must include auth dependency
- S-14 (schema-qualified queries) — new queries must use schema-qualified names

## Verification
```bash
# 1. Sentiment API works:
curl -s http://localhost:8000/api/sentiment/events | python3 -m json.tool
# EXPECTED: JSON array

# 2. DELETE endpoint works:
ID=$(curl -s http://localhost:8000/api/thoughts | python3 -c "import sys,json;print(json.load(sys.stdin)[-1]['id'])")
curl -X DELETE http://localhost:8000/api/thoughts/$ID
# EXPECTED: {"deleted": true}

# 3. GraphQL mutation works:
curl -X POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"mutation { createThought(content: \"test\") { id content } }"}'
# EXPECTED: {"data": {"createThought": {"id": ..., "content": "test"}}}

# 4. Cursor pagination works:
curl -X POST http://localhost:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ thoughtsPaginated(first: 2) { edges { cursor node { id } } pageInfo { hasNextPage endCursor } } }"}'
# EXPECTED: edges with cursors + pageInfo

# 5. OpenAPI updated:
curl -s http://localhost:8000/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(len([p for p in d['paths'] if 'sentiment' in p]))"
# EXPECTED: ≥ 2
```

## Prompt for Agent
```
Read these files FIRST:
- src/api/gql/schema.py (full — see L108-117 for mutations, L41-100 for pagination)
- src/api/gql/resolvers.py (full — see L52-200 for bare resolvers)
- src/api/db/models.py (full — find SentimentEvent at L525-564)
- src/api/routers/goals.py (full — reference for complete CRUD pattern)
- src/api/routers/thoughts.py (full — example of incomplete CRUD)
- src/api/main.py (full — see all include_router calls)

CONSTRAINTS: #1 (5-layer arch — API layer changes only), #4 (test in Docker).

STEPS:
1. Create src/api/routers/sentiment.py with full CRUD (GET list, GET by id, POST, summary)
2. Register sentiment router in main.py
3. Add PUT/{id} and DELETE/{id} to: thoughts, activities, model_usage, security_events, proposals, knowledge_graph, analysis
4. For each new endpoint, create Pydantic Update model with Optional fields
5. Add GraphQL mutations for: create_thought, delete_thought, create_activity, create_proposal, update_proposal_status, create_session
6. Implement cursor-based pagination (PageInfo, Edge, Connection types) for thoughts, memories, activities
7. Keep existing offset/limit queries for backward compatibility
8. Wrap all resolver functions in try/except SQLAlchemyError → GraphQLError
9. Add auth dependency (Depends(get_current_user)) to all new REST endpoints
10. Run existing tests to confirm no breakage
11. Test new endpoints via curl in Docker
```
