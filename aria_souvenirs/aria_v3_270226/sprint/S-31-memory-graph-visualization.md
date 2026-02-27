# S-31: Memory Graph — Interactive Vis-Network for All Memory Types
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P1 | **Points:** 8 | **Phase:** 2

## Problem

Aria has **7 distinct memory stores** (Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned, KnowledgeEntity, EngineChatMessage) but **zero relationship visualization** between them. Each memory type lives in isolation — the existing pages (`memories.html`, `memory_explorer.html`, `working_memory.html`) show flat card grids with no inter-memory connections.

The `knowledge.html` page (line 1–518) already demonstrates a fully working vis-network graph for KnowledgeEntity/KnowledgeRelation, and `skill_graph.html` (line 1–596) does the same for skills. However, the **Memory** dropdown in `base.html` (nav menu) has no graph page — only flat CRUD views:
- `/memories` → card grid (KV store)
- `/memory-explorer` → card grid (semantic, not even in nav menu)
- `/working-memory` → CRUD table
- `/knowledge` → vis-network graph (KG entities only, no memory linkage)

**Missing:** A `/memory-graph` route and `memory_graph.html` template that renders all memory types as a unified interactive network graph using vis-network.

**Files involved:**
- `src/web/app.py` line 162 (`/memories` route) — no `/memory-graph` route exists
- `src/web/templates/base.html` line ~155–370 (nav menu) — Memory dropdown has no graph link
- `src/api/routers/memories.py` lines 112–514 — has CRUD but no graph endpoint
- `src/api/routers/working_memory.py` lines 48–494 — has CRUD but no graph endpoint
- `src/api/routers/knowledge.py` line 219 — `GET /knowledge-graph` returns entities+relations (pattern to reuse)
- `src/api/db/models.py` line 66 (`Memory`), line 83 (`Thought`), line 642 (`WorkingMemory`), line 694 (`SemanticMemory`), line 719 (`LessonLearned`)

## Root Cause

The memory subsystem was built incrementally — KV store first (Memory), then pgvector (SemanticMemory), then working memory (WorkingMemory), then knowledge graph (KnowledgeEntity/KnowledgeRelation). Each was added as an independent component with its own API router and HTML page. No relationship model was ever built to connect:
- SemanticMemory → KnowledgeEntity (memories that mention entities)
- WorkingMemory → SemanticMemory (promoted items)
- Thought → SemanticMemory (consolidated thoughts)
- LessonLearned → SemanticMemory (lesson context)

The vis-network library is already bundled at `src/web/static/js/vis-network.min.js` and used by 4 pages (knowledge, skill_graph, rpg, roundtable). The pattern is proven — this ticket reuses it for a memory-centric graph.

## Fix

### 1. New API endpoint: `GET /api/memory-graph`

**File:** `src/api/routers/memories.py`

**PREREQUISITE — Add missing imports** at line 16:
```python
# BEFORE:
from db.models import Memory, SemanticMemory

# AFTER:
from db.models import Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned
```

**AFTER** (add at end of file, before the closing of the router):

```python
@router.get("/memory-graph")
async def get_memory_graph(
    limit: int = Query(200, ge=1, le=2000),
    include_types: str = Query("all", description="Comma-separated: semantic,working,kv,thought,lesson"),
    db: AsyncSession = Depends(get_db),
):
    """
    Build a graph of memory nodes and inferred relationships for vis-network.
    
    Node types: semantic_memory, working_memory, kv_memory, thought, lesson, knowledge_entity
    Edge types: same_category, temporal_proximity, shared_source, importance_cluster, entity_mention
    """
    nodes = []
    edges = []
    node_id = 0
    types = [t.strip() for t in include_types.split(",")] if include_types != "all" else [
        "semantic", "working", "kv", "thought", "lesson"
    ]
    
    category_index = {}  # category -> [node_ids] for same-category edges
    source_index = {}    # source -> [node_ids] for shared-source edges
    
    # --- Semantic Memories ---
    if "semantic" in types:
        stmt = select(SemanticMemory).order_by(
            SemanticMemory.importance.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        for mem in result.scalars().all():
            nid = f"sem_{mem.id}"
            nodes.append({
                "id": nid,
                "label": (mem.summary or mem.content or "")[:60],
                "type": "semantic_memory",
                "category": mem.category,
                "importance": mem.importance,
                "source": mem.source,
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
                "access_count": mem.access_count,
            })
            category_index.setdefault(mem.category, []).append(nid)
            if mem.source:
                source_index.setdefault(mem.source, []).append(nid)
    
    # --- Working Memory ---
    if "working" in types:
        stmt = select(WorkingMemory).order_by(
            WorkingMemory.importance.desc()
        ).limit(limit)
        result = await db.execute(stmt)
        for wm in result.scalars().all():
            nid = f"wm_{wm.id}"
            nodes.append({
                "id": nid,
                "label": f"{wm.category}/{wm.key}"[:60],
                "type": "working_memory",
                "category": wm.category,
                "importance": wm.importance,
                "source": wm.source,
                "ttl_hours": wm.ttl_hours,
                "created_at": wm.created_at.isoformat() if wm.created_at else None,
            })
            category_index.setdefault(wm.category, []).append(nid)
            if wm.source:
                source_index.setdefault(wm.source, []).append(nid)
    
    # --- KV Memories ---
    if "kv" in types:
        stmt = select(Memory).order_by(Memory.updated_at.desc()).limit(limit)
        result = await db.execute(stmt)
        for m in result.scalars().all():
            nid = f"kv_{m.id}"
            nodes.append({
                "id": nid,
                "label": m.key[:60],
                "type": "kv_memory",
                "category": m.category,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            })
            category_index.setdefault(m.category, []).append(nid)
    
    # --- Thoughts ---
    if "thought" in types:
        stmt = select(Thought).order_by(Thought.created_at.desc()).limit(min(limit, 50))
        result = await db.execute(stmt)
        for t in result.scalars().all():
            nid = f"th_{t.id}"
            nodes.append({
                "id": nid,
                "label": (t.content or "")[:60],
                "type": "thought",
                "category": t.category,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })
            category_index.setdefault(t.category, []).append(nid)
    
    # --- Lessons Learned ---
    if "lesson" in types:
        stmt = select(LessonLearned).order_by(LessonLearned.occurrences.desc()).limit(min(limit, 50))
        result = await db.execute(stmt)
        for ll in result.scalars().all():
            nid = f"ll_{ll.id}"
            nodes.append({
                "id": nid,
                "label": ll.error_pattern[:60],
                "type": "lesson",
                "category": ll.skill_name or "general",
                "occurrences": ll.occurrences,
                "effectiveness": ll.effectiveness,
                "created_at": ll.created_at.isoformat() if ll.created_at else None,
            })
            if ll.skill_name:
                category_index.setdefault(ll.skill_name, []).append(nid)
    
    # --- Build edges from shared categories (same_category) ---
    edge_id = 0
    for cat, nids in category_index.items():
        if len(nids) < 2:
            continue
        # Connect first node to all others in category (star topology, not full mesh)
        hub = nids[0]
        for spoke in nids[1:min(len(nids), 8)]:  # Cap at 8 edges per category hub
            edges.append({
                "id": f"e_{edge_id}",
                "from": hub,
                "to": spoke,
                "type": "same_category",
                "label": cat,
            })
            edge_id += 1
    
    # --- Build edges from shared sources ---
    for src, nids in source_index.items():
        if len(nids) < 2:
            continue
        hub = nids[0]
        for spoke in nids[1:min(len(nids), 6)]:
            edges.append({
                "id": f"e_{edge_id}",
                "from": hub,
                "to": spoke,
                "type": "shared_source",
                "label": src,
            })
            edge_id += 1
    
    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "by_type": {
                t: sum(1 for n in nodes if n["type"] == t)
                for t in set(n["type"] for n in nodes)
            },
            "categories": list(category_index.keys()),
        },
    }
```

### 2. New template: `src/web/templates/memory_graph.html`

Create a new template following the `knowledge.html` pattern (vis-network graph with type filters, search, node inspector):

- **vis-network** force-directed graph
- **Node types:** semantic_memory (purple dot), working_memory (orange diamond), kv_memory (blue square), thought (green triangle), lesson (red star)
- **Edge types:** same_category (solid gray), shared_source (dashed blue)
- **Controls:** Type checkboxes to filter, category dropdown, layout toggle (physics/hierarchical), search
- **Inspector panel:** Click a node → show full details in sidebar

### 3. New route in `src/web/app.py`

**File:** `src/web/app.py`  
**Location:** After line 162 (`/memories` route)

**BEFORE:**
```python
    @app.route('/memories')
    def memories():
        return render_template('memories.html')

    @app.route('/sentiment')
```

**AFTER:**
```python
    @app.route('/memories')
    def memories():
        return render_template('memories.html')

    @app.route('/memory-graph')
    def memory_graph():
        return render_template('memory_graph.html')

    @app.route('/sentiment')
```

### 4. Nav menu update in `src/web/templates/base.html`

Add `/memory-graph` to the 💾 Memory dropdown, after `/knowledge`.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | New API endpoint uses ORM (SemanticMemory, WorkingMemory, etc.). Template calls through `/api/` proxy. No layer violations. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved — read-only visualization endpoint. |
| 3 | models.yaml single source of truth | ❌ | No model references — pure data visualization. |
| 4 | Docker-first testing | ✅ | Must verify in `docker compose up`. Template extends `base.html`, API endpoint in FastAPI container. |
| 5 | aria_memories only writable path | ❌ | Read-only endpoint — no writes. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **None** — This ticket is self-contained. Uses existing ORM models and existing vis-network library.
- **S-05 (nav regrouping)** — If S-05 is done first, the nav structure may differ. Check `base.html` nav before applying nav changes.

## Verification
```bash
# 1. API endpoint returns graph data:
curl -s http://localhost:${ARIA_API_PORT:-8000}/api/memory-graph?limit=50 | python3 -m json.tool | head -20
# EXPECTED: JSON with "nodes", "edges", "stats" keys

# 2. Route registered in Flask app:
grep -n "memory.graph\|memory_graph" src/web/app.py
# EXPECTED: route definition for /memory-graph

# 3. Template exists:
ls -la src/web/templates/memory_graph.html
# EXPECTED: file exists, ~600-800 lines

# 4. Nav menu updated:
grep -n "memory-graph" src/web/templates/base.html
# EXPECTED: link in Memory nav dropdown

# 5. vis-network loads (Docker):
curl -s http://localhost:${ARIA_WEB_PORT:-5050}/memory-graph | grep -c "vis-network"
# EXPECTED: 1 (script tag present)

# 6. No architecture violations:
grep -rn "from sqlalchemy\|import sqlalchemy" src/web/templates/memory_graph.html
# EXPECTED: no output (zero matches)
```

## Prompt for Agent
```
You are implementing S-31: Memory Graph Visualization for the Aria project.

FILES TO READ FIRST:
- src/web/templates/knowledge.html (lines 1-518) — REFERENCE PATTERN for vis-network graph
- src/web/templates/skill_graph.html (lines 1-596) — REFERENCE PATTERN for skill graph
- src/api/routers/memories.py (lines 1-514) — existing memory endpoints
- src/api/routers/knowledge.py (lines 219-280) — GET /knowledge-graph pattern
- src/api/db/models.py (lines 640-720) — WorkingMemory and SemanticMemory models
- src/web/app.py (lines 148-160) — where to add route
- src/web/templates/base.html (lines 155-200) — nav menu Memory section

CONSTRAINTS:
1. All DB access through ORM (SQLAlchemy models in src/api/db/models.py)
2. Template calls API through /api/ proxy (Flask proxies to FastAPI)
3. Use bundled vis-network.min.js from /static/js/vis-network.min.js
4. Template must extend base.html

STEPS:
1. Add GET /memory-graph endpoint to src/api/routers/memories.py (see Fix section for full code)
2. Create src/web/templates/memory_graph.html modeled on knowledge.html pattern
3. Add /memory-graph route to src/web/app.py after line 148
4. Add "Memory Graph" link to base.html nav Memory dropdown
5. Run verification commands

Node color/shape mapping:
- semantic_memory: purple (#8b5cf6), dot, size 15 (importance-scaled)
- working_memory: orange (#f59e0b), diamond, size 12
- kv_memory: blue (#3b82f6), square, size 10
- thought: green (#22c55e), triangle, size 8
- lesson: red (#ef4444), star, size 14

Edge styling:
- same_category: solid gray, width 1, dashes false
- shared_source: dashed blue (#3b82f6), width 1.5, dashes [5,5]

Physics: forceAtlas2Based (same as knowledge.html and roundtable)
```
