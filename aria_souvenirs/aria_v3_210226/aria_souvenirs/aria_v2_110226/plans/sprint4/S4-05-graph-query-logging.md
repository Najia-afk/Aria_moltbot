# S4-05: Add Query Logging for Aria's Graph Traversals
**Epic:** E8 — Knowledge Graph | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem
When Aria queries the knowledge graph, there's no logging of:
- What queries she made
- Which paths she traversed
- Whether the result was useful (did she use the suggested skill?)
- How many tokens were saved vs. reading TOOLS.md

This data is needed for:
1. Debugging Aria's reasoning
2. Optimizing the graph structure
3. The vis.js skill graph (S4-03) to show Aria's query patterns

## Root Cause
No query logging exists for knowledge graph traversals.

## Fix

### Step 1: Add DB model for query logs
**File: `src/api/db/models.py`**
```python
class KnowledgeQueryLog(Base):
    __tablename__ = "knowledge_query_log"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    query_type: Mapped[str] = mapped_column(String(50), nullable=False)  # traverse, search, skill_for_task
    query_params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    result_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    tokens_saved: Mapped[int | None] = mapped_column(Integer)  # estimated tokens saved vs TOOLS.md
    used_result: Mapped[bool | None] = mapped_column(Boolean)  # did Aria use the suggested skill?
    source: Mapped[str] = mapped_column(String(50), server_default=text("'aria'"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("NOW()"))
    
    __table_args__ = (
        Index("idx_kql_type", "query_type"),
        Index("idx_kql_created", "created_at"),
    )
```

### Step 2: Log queries in knowledge.py endpoints
After each traverse/search/skill_for_task query, log it:
```python
# After returning results:
db.add(KnowledgeQueryLog(
    query_type="traverse",
    query_params={"start": start_name, "relation": relation_type, "depth": max_depth},
    result_count=len(result_nodes),
    tokens_saved=2000 - (len(str(result_nodes)) // 4),  # rough estimate
    source="api",
))
await db.commit()
```

### Step 3: Add query log API
```python
@router.get("/knowledge-graph/query-log")
async def get_query_log(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent knowledge graph queries for analysis."""
    stmt = select(KnowledgeQueryLog).order_by(KnowledgeQueryLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return {"queries": [q.to_dict() for q in result.scalars().all()]}
```

### Step 4: Alembic migration
```bash
cd src/api && alembic revision --autogenerate -m "add_knowledge_query_log"
alembic upgrade head
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | DB+API changes |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Run migration |
| 5 | aria_memories | ❌ | DB writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S4-02** (traverse/search endpoints exist)

## Verification
```bash
# 1. Model exists:
grep 'KnowledgeQueryLog' src/api/db/models.py
# EXPECTED: class definition

# 2. Migration runs:
cd src/api && alembic upgrade head

# 3. Queries are logged:
curl -s 'http://localhost:8000/api/knowledge-graph/traverse?start_name=api_client'
curl -s http://localhost:8000/api/knowledge-graph/query-log | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Logged queries: {len(d[\"queries\"])}')"
# EXPECTED: 1+ logged queries
```

## Prompt for Agent
```
Add query logging for Aria's knowledge graph traversals.

FILES TO READ FIRST:
- src/api/db/models.py (add KnowledgeQueryLog model)
- src/api/routers/knowledge.py (log queries in existing endpoints)

STEPS:
1. Add KnowledgeQueryLog model with indexes
2. Log traverse, search, skill_for_task queries with params + result count
3. Add GET /knowledge-graph/query-log endpoint
4. Create alembic migration
5. Run verification

CONSTRAINTS: DB+API layer. Logging should not slow down queries significantly.
```
