# S-37: Unified Memory Search — Cross-Memory-Type Search Page
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem

Aria has **5 searchable memory stores**, each with its own isolated search:
1. **Memory** (KV) — `GET /memories?category=` (category filter, `src/api/routers/memories.py` line 107)
2. **SemanticMemory** — `GET /memories/search?query=` (pgvector cosine similarity, line 300)
3. **WorkingMemory** — `GET /working-memory?category=&key=` (exact match filter, `src/api/routers/working_memory.py` line 48)
4. **Thoughts** — `GET /thoughts` (list only, no search param — `src/api/routers/thoughts.py` line 22)
5. **LessonsLearned** — `GET /lessons` (list only, no filter params — `src/api/routers/lessons.py` line 91)

A user searching for "authentication" or "security patterns" must visit 5 different pages and run 5 different searches. There is no unified search that queries across all memory types simultaneously.

The `memory_explorer.html` has a semantic search section (line ~200) that only searches `SemanticMemory`. The `memories.html` has a search by key. The `working_memory.html` has a category filter. None cross-reference.

**Missing:** A `/memory-search` page with a single search box that queries all 5 memory types in parallel and presents results in a ranked, unified view with type badges.

## Root Cause

Each memory type was built independently with its own router, model, and search mechanism. No unified search API exists. The frontend mirrors this separation with dedicated pages for each type.

## Fix

### 1. New API endpoint: `GET /api/memory-search`

**File:** `src/api/routers/memories.py`

**PREREQUISITE — Imports:** If S-31 has not been applied, add to line 16:
```python
from db.models import Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned
```
Also add:
```python
from sqlalchemy import or_, cast, String
```

**⚠️ Note:** The `/memory-search` route is safe from the `GET /memories/{key}` catch-all at line 486 because it's a different path prefix (`/memory-search` vs `/memories/...`). No special ordering needed for this endpoint. However, it should still be placed logically near other memory endpoints.

```python
@router.get("/memory-search")
async def unified_memory_search(
    query: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(10, ge=1, le=50),
    types: str = Query("all", description="Comma-separated: semantic,kv,working,thought,lesson"),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified search across all memory types.
    
    Strategy:
    - SemanticMemory: pgvector cosine similarity (primary, highest quality)
    - Others: ILIKE text search on content/key/value fields
    
    Results ranked by relevance (semantic similarity for vector results, 
    text match quality for ILIKE results).
    """
    search_types = [t.strip() for t in types.split(",")] if types != "all" else [
        "semantic", "kv", "working", "thought", "lesson"
    ]
    results = []
    
    # 1. Semantic search (vector, highest quality)
    if "semantic" in search_types:
        try:
            embedding = await generate_embedding(query)  # Reuse existing function at line 163
            if embedding:
                from pgvector.sqlalchemy import Vector
                stmt = (
                    select(
                        SemanticMemory,
                        SemanticMemory.embedding.cosine_distance(embedding).label("distance"),
                    )
                    .where(SemanticMemory.embedding.isnot(None))
                    .order_by("distance")
                    .limit(limit)
                )
                result = await db.execute(stmt)
                for row in result.all():
                    mem = row[0]
                    similarity = 1 - row[1]  # Convert distance to similarity
                    results.append({
                        "type": "semantic_memory",
                        "id": str(mem.id),
                        "title": mem.summary or (mem.content or "")[:80],
                        "content": (mem.content or "")[:300],
                        "category": mem.category,
                        "relevance": round(float(similarity), 4),
                        "importance": mem.importance,
                        "source": mem.source,
                        "created_at": mem.created_at.isoformat() if mem.created_at else None,
                    })
        except Exception:
            pass  # Graceful fallback if embedding fails
    
    # 2. KV Memory text search
    if "kv" in search_types:
        pattern = f"%{query}%"
        stmt = (
            select(Memory)
            .where(or_(Memory.key.ilike(pattern), cast(Memory.value, String).ilike(pattern)))
            .order_by(Memory.updated_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        for m in result.scalars().all():
            results.append({
                "type": "kv_memory",
                "id": str(m.id),
                "title": m.key,
                "content": str(m.value)[:300] if m.value else "",
                "category": m.category,
                "relevance": 0.5,  # Text match — lower than vector
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
    
    # 3. Working Memory text search
    if "working" in search_types:
        pattern = f"%{query}%"
        stmt = (
            select(WorkingMemory)
            .where(or_(
                WorkingMemory.key.ilike(pattern),
                cast(WorkingMemory.value, String).ilike(pattern),
            ))
            .order_by(WorkingMemory.importance.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        for wm in result.scalars().all():
            results.append({
                "type": "working_memory",
                "id": str(wm.id),
                "title": f"{wm.category}/{wm.key}",
                "content": str(wm.value)[:300] if wm.value else "",
                "category": wm.category,
                "relevance": 0.45,
                "importance": wm.importance,
                "created_at": wm.created_at.isoformat() if wm.created_at else None,
            })
    
    # 4. Thoughts text search
    if "thought" in search_types:
        stmt = (
            select(Thought)
            .where(Thought.content.ilike(f"%{query}%"))
            .order_by(Thought.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        for t in result.scalars().all():
            results.append({
                "type": "thought",
                "id": str(t.id),
                "title": (t.content or "")[:80],
                "content": (t.content or "")[:300],
                "category": t.category,
                "relevance": 0.4,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
    
    # 5. Lessons text search
    if "lesson" in search_types:
        stmt = (
            select(LessonLearned)
            .where(or_(
                LessonLearned.error_pattern.ilike(f"%{query}%"),
                LessonLearned.resolution.ilike(f"%{query}%"),
            ))
            .order_by(LessonLearned.occurrences.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        for ll in result.scalars().all():
            results.append({
                "type": "lesson",
                "id": str(ll.id),
                "title": ll.error_pattern[:80],
                "content": (ll.resolution or "")[:300],
                "category": ll.skill_name or "general",
                "relevance": 0.35,
                "occurrences": ll.occurrences,
                "created_at": ll.created_at.isoformat() if ll.created_at else None,
            })
    
    # Sort by relevance descending
    results.sort(key=lambda r: r.get("relevance", 0), reverse=True)
    
    # Stats
    type_counts = {}
    for r in results:
        type_counts[r["type"]] = type_counts.get(r["type"], 0) + 1
    
    return {
        "query": query,
        "results": results[:limit * 2],  # Cap total results
        "total": len(results),
        "by_type": type_counts,
    }
```

### 2. New template: `src/web/templates/memory_search.html`

- **Single search box** (top of page, prominent)
- **Type filter chips**: Toggle each memory type on/off (all on by default)
- **Result cards**: Each card shows type badge (colored icon), title, content preview, relevance bar, category, timestamp
- **Type badges**: semantic_memory (🧠 purple), kv_memory (📦 blue), working_memory (⚡ orange), thought (💭 green), lesson (📚 red)
- **Keyboard shortcut**: Ctrl+K or Cmd+K to focus search (like Spotlight)

### 3. New route and nav

**File:** `src/web/app.py`:
```python
    @app.route('/memory-search')
    def memory_search():
        return render_template('memory_search.html')
```

**File:** `src/web/templates/base.html` — add to Memory dropdown as first item (most useful).

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | All DB access through ORM. Uses existing `generate_embedding()` function (line 163) for vector search. Template calls /api/ proxy. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets. Embedding API key handled by existing _get_embedding. |
| 3 | models.yaml single source of truth | ✅ | Embedding model used by `_get_embedding()` should come from models.yaml (verify). |
| 4 | Docker-first testing | ✅ | pgvector + ILIKE — must test in Docker with real DB. |
| 5 | aria_memories only writable path | ❌ | Read-only endpoint. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **None blocking** — Reuses existing search functions from `memories.py`.
- **S-31, S-32** — shares nav changes. Non-blocking.

## Verification
```bash
# 1. API returns unified results:
curl -s "http://localhost:8000/api/memory-search?query=security&limit=5" | python3 -m json.tool | head -25
# EXPECTED: JSON with "results" array containing mixed types, "by_type" breakdown

# 2. Multiple types in results:
curl -s "http://localhost:8000/api/memory-search?query=error&limit=20" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Total: {d[\"total\"]}, Types: {d[\"by_type\"]}')
"
# EXPECTED: results from multiple memory types

# 3. Route registered:
grep -n "memory.search\|memory_search" src/web/app.py
# EXPECTED: route for /memory-search

# 4. Template exists:
ls -la src/web/templates/memory_search.html
# EXPECTED: file exists

# 5. Type filter chips in template:
grep -c "type.*filter\|type-chip\|mem-type" src/web/templates/memory_search.html
# EXPECTED: >= 3

# 6. Relevance sorting works:
curl -s "http://localhost:8000/api/memory-search?query=pattern&limit=10" | python3 -c "
import json, sys
d = json.load(sys.stdin)
relevances = [r['relevance'] for r in d['results']]
print('Sorted desc:', relevances == sorted(relevances, reverse=True))
"
# EXPECTED: Sorted desc: True
```

## Prompt for Agent
```
You are implementing S-37: Unified Memory Search for the Aria project.

FILES TO READ FIRST:
- src/api/routers/memories.py (full file, 514 lines) — existing search endpoints, generate_embedding function at line 163
- src/api/routers/working_memory.py (lines 48-70) — WM list/filter pattern
- src/api/routers/thoughts.py — thought search pattern
- src/api/routers/lessons.py — lesson search pattern  
- src/web/templates/memory_explorer.html (lines 198-260) — semantic search section UI pattern
- src/api/db/models.py — all memory models (Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned)

CONSTRAINTS:
1. ORM for all DB access — NO raw SQL
2. Vector search for SemanticMemory (reuse existing generate_embedding at line 163)
3. ILIKE for text-based stores (KV, WM, Thoughts, Lessons)
4. Results sorted by relevance (semantic > text match)
5. Template extends base.html
6. Graceful fallback: if vector search fails, still return text results

STEPS:
1. Add GET /memory-search endpoint to src/api/routers/memories.py
2. Create src/web/templates/memory_search.html with:
   a. Prominent search box with Ctrl+K shortcut
   b. Type filter chips (toggle each type)
   c. Result cards with type badge, title, content preview, relevance bar
   d. Color coding: semantic_memory=purple, kv_memory=blue, working_memory=orange, thought=green, lesson=red
3. Add /memory-search route to src/web/app.py
4. Add "🔍 Memory Search" as first item in Memory nav dropdown
5. Run verification commands
```
