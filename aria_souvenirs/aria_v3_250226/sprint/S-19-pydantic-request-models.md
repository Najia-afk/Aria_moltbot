# S-19: Pydantic Request Models for 33 POST Endpoints
**Epic:** E11 — API Quality | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
33 POST/PATCH endpoints use raw `request: Request` + `await request.json()` instead of Pydantic `BaseModel` request bodies. This bypasses FastAPI's automatic validation, OpenAPI schema generation, and type coercion. Malformed payloads produce unstructured 500 errors instead of 422 validation responses.

### Affected Endpoints (33 total)
| Router | File | Endpoints |
|--------|------|-----------|
| goals | `src/api/routers/goals.py` L82 | POST /goals |
| thoughts | `src/api/routers/thoughts.py` L42 | POST /thoughts |
| activities | `src/api/routers/activities.py` L90 | POST /activities |
| sessions | `src/api/routers/sessions.py` L126 | POST /sessions |
| memories | `src/api/routers/memories.py` L131 | POST /memories |
| security | `src/api/routers/security.py` L68 | POST /security-events |
| proposals | `src/api/routers/proposals.py` L28 | POST /proposals |
| operations | `src/api/routers/operations.py` L63+ | 6+ POST endpoints |
| social | `src/api/routers/social.py` L144 | POST /social |
| working_memory | `src/api/routers/working_memory.py` L148 | POST /working-memory |
| + ~15 more | Various | Various POST/PATCH |

The `engine_chat.py` router already uses Pydantic correctly — follow that pattern.

## Root Cause
Rapid development using the quick `await request.json()` pattern. Never migrated to proper Pydantic models.

## Fix

### Fix 1: Create request model schemas
**File:** `src/api/schemas/` (NEW directory) or co-located in each router

For each endpoint, create a Pydantic model:
```python
# src/api/schemas/goals.py
from pydantic import BaseModel, Field
from typing import Optional

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: Optional[int] = Field(default=0, ge=0, le=10)
    source: Optional[str] = "user"

class GoalUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    status: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=10)
```

### Fix 2: Update each endpoint signature
**Pattern — BEFORE:**
```python
@router.post("/goals")
async def create_goal(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    title = data.get("title", "")
    ...
```

**Pattern — AFTER:**
```python
@router.post("/goals", response_model=GoalResponse)
async def create_goal(body: GoalCreate, db: AsyncSession = Depends(get_db)):
    ...
```

### Fix 3: Add response models
For each entity, also create response models:
```python
class GoalResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True  # SQLAlchemy ORM mode
```

### Fix 4: Verify OpenAPI completeness
After migration, check `/openapi.json` to confirm all endpoints have proper request/response schemas.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | API layer schemas |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- None — can be done incrementally, router by router.

## Verification
```bash
# 1. Count endpoints without Pydantic:
grep -rn 'await request.json()' src/api/routers/ | wc -l
# EXPECTED: 0

# 2. Verify 422 on bad input:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/goals \
  -H 'Content-Type: application/json' -H 'X-API-Key: KEY' \
  -d '{"title": ""}'
# EXPECTED: 422 (min_length violated)

# 3. Verify OpenAPI completeness:
curl -s http://localhost:8000/openapi.json | python -c "
import json, sys
spec = json.load(sys.stdin)
for path, methods in spec['paths'].items():
    for method, details in methods.items():
        if method in ('post','put','patch') and 'requestBody' not in details:
            print(f'MISSING SCHEMA: {method.upper()} {path}')
"
# EXPECTED: No missing schemas

# 4. Count Pydantic models created:
grep -rn 'class.*BaseModel' src/api/schemas/ | wc -l
# EXPECTED: ≥ 33 (one per endpoint minimum)
```

## Prompt for Agent
```
Read these files FIRST:
- src/api/routers/engine_chat.py (EXAMPLE — uses Pydantic correctly)
- src/api/routers/goals.py (full — example of raw request.json)
- src/api/routers/thoughts.py (full)
- src/api/routers/activities.py (full)

CONSTRAINTS: #1 (API layer). Follow engine_chat.py as the gold standard pattern.

STEPS:
1. List ALL endpoints using `await request.json()` — grep all routers
2. For each router, examine the expected JSON fields from the .json() call
3. Create Pydantic request models in src/api/schemas/ (one file per entity)
4. Create response models with from_attributes = True
5. Update each endpoint: replace Request param with Pydantic body param
6. Add Field validators: min_length, max_length, ge, le as appropriate
7. Test that existing API calls still work (backward compatible field names)
8. Check /openapi.json for completeness
9. Run ALL existing tests to catch regressions
10. Do NOT change business logic — only input/output typing
```
