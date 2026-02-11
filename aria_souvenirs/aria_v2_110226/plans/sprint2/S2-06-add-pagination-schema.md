# S2-06: Add Shared PaginatedResponse Schema & Pagination to All API Endpoints
**Epic:** E2 — Pagination | **Priority:** P0 | **Points:** 8 | **Phase:** 1

## Problem
9 out of 19 list endpoints lack proper pagination. They accept `limit` but have no `offset`/`page` parameter and don't return total count. This means:
- Frontend can only show the first N items (no "next page")
- Large datasets cause slow responses (no cursor/offset)
- Dashboard tables have no pagination controls

Currently only `records.py` has proper server-side pagination and `knowledge.py` has basic offset.

## Root Cause
Pagination was never systematically implemented. Each endpoint was written independently with just a `limit` parameter.

## Fix

### Step 1: Create shared pagination helper
**File: `src/api/pagination.py`** (NEW FILE)
```python
"""Shared pagination utilities for all API endpoints."""
from typing import Any
from pydantic import BaseModel


class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    limit: int
    pages: int  # ceil(total / limit)


def paginate_query(stmt, page: int = 1, limit: int = 25):
    """Apply offset/limit to a SQLAlchemy select statement.
    
    Returns (modified_stmt, offset) tuple.
    """
    offset = (max(1, page) - 1) * limit
    return stmt.offset(offset).limit(limit), offset


def build_paginated_response(items: list, total: int, page: int, limit: int) -> dict:
    """Build a standard paginated response dict."""
    import math
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total / limit) if limit > 0 else 0,
    }
```

### Step 2: Update each endpoint (9 endpoints)
Each endpoint gets `page: int = 1, limit: int = 25` params and returns `PaginatedResponse` format.

Example for `goals.py`:
BEFORE:
```python
@router.get("/goals")
async def list_goals(
    limit: int = 100,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Goal.status == status)
    result = await db.execute(stmt)
    return [g.to_dict() for g in result.scalars().all()]
```
AFTER:
```python
@router.get("/goals")
async def list_goals(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func
    from pagination import paginate_query, build_paginated_response
    
    base = select(Goal).order_by(Goal.priority.asc(), Goal.created_at.desc())
    if status:
        base = base.where(Goal.status == status)
    
    # Count total
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0
    
    # Paginate
    stmt, _ = paginate_query(base, page, limit)
    result = await db.execute(stmt)
    items = [g.to_dict() for g in result.scalars().all()]
    
    return build_paginated_response(items, total, page, limit)
```

Apply the same pattern to ALL 9 endpoints:
1. `GET /goals` — goals.py
2. `GET /activities` — activities.py  
3. `GET /thoughts` — thoughts.py
4. `GET /memories` — memories.py
5. `GET /social` — social.py (the list endpoint)
6. `GET /sessions` — sessions.py
7. `GET /security-events` — security.py
8. `GET /model-usage` — model_usage.py
9. `GET /working-memory` — working_memory.py

Default limit: 25 for most, 50 for activities/model-usage (high volume).

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Changes in API layer only |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Test all 9 endpoints locally |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul files touched |

## Dependencies
- S2-01 should complete first (goals.py sort fix) to avoid merge conflicts.

## Verification
```bash
# 1. Verify pagination.py exists:
python3 -c "from pagination import build_paginated_response; print('OK')"

# 2. Test goals endpoint returns paginated format:
curl -s 'http://localhost:8000/api/goals?page=1&limit=5' | python3 -c "
import sys,json; d=json.load(sys.stdin)
assert 'items' in d and 'total' in d and 'pages' in d, f'Missing keys: {d.keys()}'
print(f'Page {d[\"page\"]}/{d[\"pages\"]}, showing {len(d[\"items\"])}/{d[\"total\"]}')
"

# 3. Test page 2:
curl -s 'http://localhost:8000/api/goals?page=2&limit=5' | python3 -c "
import sys,json; d=json.load(sys.stdin)
print(f'Page {d[\"page\"]}/{d[\"pages\"]}, items: {len(d[\"items\"])}')
"

# 4. Verify all 9 endpoints have pagination:
for ep in goals activities thoughts memories social sessions security-events model-usage working-memory; do
  resp=$(curl -s "http://localhost:8000/api/$ep?page=1&limit=2")
  has_items=$(echo "$resp" | python3 -c "import sys,json; print('items' in json.load(sys.stdin))" 2>/dev/null)
  echo "$ep: paginated=$has_items"
done
# EXPECTED: all show paginated=True

# 5. Run tests:
cd src/api && python -m pytest -x -q
```

## Prompt for Agent
```
You are adding pagination to ALL list endpoints in the Aria API.

FILES TO READ FIRST:
- src/api/routers/goals.py, activities.py, thoughts.py, memories.py, social.py, sessions.py, security.py, model_usage.py, working_memory.py
- src/api/routers/records.py (REFERENCE — has proper pagination already)
- src/api/deps.py (get_db dependency)

STEPS:
1. Create src/api/pagination.py with PaginatedResponse, paginate_query, build_paginated_response
2. Update each of the 9 list endpoints to:
   a. Accept page: int = 1, limit: int = 25 params
   b. Count total using func.count() subquery
   c. Apply offset/limit via paginate_query()
   d. Return build_paginated_response() format
3. Keep backward compatibility — if caller doesn't pass page, defaults to page=1
4. Run verification commands

CONSTRAINTS: API layer only. Standard {items, total, page, limit, pages} response format.
IMPORTANT: Do NOT touch .env. Do NOT add secrets to code.
```
