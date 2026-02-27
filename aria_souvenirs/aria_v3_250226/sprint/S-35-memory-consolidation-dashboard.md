# S-35: Memory Consolidation Dashboard — Surface→Medium→Deep Flow Visualization
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P2 | **Points:** 5 | **Phase:** 3

## Problem

Aria has a **3-tier file-based memory system** managed by `aria_mind/memory.py` (class `MemoryManager`):
- **Surface** (`aria_memories/memory/surface/`) — one-beat transient snapshots, auto-pruned
- **Medium** (`aria_memories/memory/medium/`) — 6-hour consolidated summaries, 24h TTL
- **Deep** (`aria_memories/memory/deep/`) — permanent synthesized insights/patterns

Additionally, the `memory_compression` skill (`aria_skills/memory_compression/`) implements a 3-tier compression pipeline:
- **Raw** — last 20 messages verbatim (high-value)
- **Recent** — last 100 messages compressed to ~30%
- **Archive** — everything older compressed to ~10%

And `conversation_summary` skill (`aria_skills/conversation_summary/`) consolidates sessions into `SemanticMemory` entries.

**The problem**: There is **no dashboard** that shows:
1. How memories flow through the pipeline (raw → compressed → semantic)
2. Compression ratios achieved
3. How many memories are at each tier (surface vs medium vs deep)
4. Consolidation history (when was the last consolidation? what was summarized?)
5. Memory promotion paths (WorkingMemory → SemanticMemory)

The `memory_explorer.html` only shows the final SemanticMemory state — not how memories arrived there.

## Root Cause

The memory consolidation pipeline was built for Aria's internal use (cron-driven via heartbeat) with logging but no observability UI. The `MemoryManager.consolidate_memories()` method in `aria_mind/memory.py` logs its actions but doesn't persist consolidation metrics to a queryable store.

The file-based tiers (`surface/`, `medium/`, `deep/`) are only accessible via the artifacts API (`POST /artifacts`, `GET /artifacts/{category}/*`) but have no summary endpoint.

## Fix

### 1. New API endpoint: `GET /api/memory-consolidation`

**File:** `src/api/routers/memories.py`

**PREREQUISITE — Imports:** If S-31 has not been applied, add to line 16:
```python
from db.models import Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned
```

**⚠️ Async I/O note:** The filesystem operations (`Path.glob()`, `stat()`) below are **blocking**. In an async endpoint, wrap them in `asyncio.to_thread()` to avoid blocking the event loop:
```python
import asyncio

def _scan_tier(tier_path: Path) -> dict:
    """Synchronous filesystem scan — run via to_thread."""
    if not tier_path.exists():
        return {"count": 0, "total_bytes": 0, "newest": 0, "oldest": 0}
    files = list(tier_path.glob("*"))
    file_stats = [f.stat() for f in files if f.is_file()]
    return {
        "count": len(file_stats),
        "total_bytes": sum(s.st_size for s in file_stats),
        "newest": max((s.st_mtime for s in file_stats), default=0),
        "oldest": min((s.st_mtime for s in file_stats), default=0),
    }
```
Then in the endpoint:
```python
tiers = {}
for tier in ["surface", "medium", "deep"]:
    tiers[tier] = await asyncio.to_thread(_scan_tier, base / "memory" / tier)
```

```python
@router.get("/memory-consolidation")
async def get_memory_consolidation_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """
    Memory consolidation dashboard data:
    - File tier counts (surface/medium/deep)
    - SemanticMemory source distribution (how memories were created)
    - Compression metrics (by source)
    - Recent consolidation activity
    - WorkingMemory → SemanticMemory promotion candidates
    """
    import os
    from pathlib import Path
    
    base = Path(os.environ.get("ARIA_MEMORIES_PATH", "aria_memories"))
    
    # 1. File tier counts
    tiers = {}
    for tier in ["surface", "medium", "deep"]:
        tier_path = base / "memory" / tier
        if tier_path.exists():
            files = list(tier_path.glob("*"))
            tiers[tier] = {
                "count": len(files),
                "total_bytes": sum(f.stat().st_size for f in files if f.is_file()),
                "newest": max((f.stat().st_mtime for f in files if f.is_file()), default=0),
                "oldest": min((f.stat().st_mtime for f in files if f.is_file()), default=0),
            }
        else:
            tiers[tier] = {"count": 0, "total_bytes": 0, "newest": 0, "oldest": 0}
    
    # 2. SemanticMemory source distribution
    source_stmt = select(
        SemanticMemory.source,
        func.count().label("count"),
        func.avg(SemanticMemory.importance).label("avg_importance"),
    ).group_by(SemanticMemory.source)
    source_result = await db.execute(source_stmt)
    sources = {
        (r.source or "unknown"): {"count": r.count, "avg_importance": round(float(r.avg_importance or 0), 3)}
        for r in source_result.all()
    }
    
    # 3. Recent semantic memories (last 24h — consolidation output)
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    recent_stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.created_at >= cutoff_24h)
        .order_by(SemanticMemory.created_at.desc())
        .limit(20)
    )
    recent_result = await db.execute(recent_stmt)
    recent_memories = [
        {
            "id": str(m.id),
            "summary": (m.summary or m.content or "")[:120],
            "category": m.category,
            "source": m.source,
            "importance": m.importance,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in recent_result.scalars().all()
    ]
    
    # 4. WorkingMemory → promotion candidates (high importance, long-lived)
    promo_stmt = (
        select(WorkingMemory)
        .where(WorkingMemory.importance >= 0.7)
        .order_by(WorkingMemory.importance.desc())
        .limit(15)
    )
    promo_result = await db.execute(promo_stmt)
    promotion_candidates = [
        {
            "id": str(wm.id),
            "key": f"{wm.category}/{wm.key}",
            "importance": wm.importance,
            "access_count": wm.access_count,
            "created_at": wm.created_at.isoformat() if wm.created_at else None,
        }
        for wm in promo_result.scalars().all()
    ]
    
    # 5. Category-level compression stats (approximate)
    category_stmt = select(
        SemanticMemory.category,
        func.count().label("count"),
        func.avg(func.length(SemanticMemory.content)).label("avg_content_len"),
        func.avg(func.length(SemanticMemory.summary)).label("avg_summary_len"),
    ).group_by(SemanticMemory.category)
    cat_result = await db.execute(category_stmt)
    compression_stats = {}
    for r in cat_result.all():
        content_len = float(r.avg_content_len or 0)
        summary_len = float(r.avg_summary_len or 0)
        ratio = round(summary_len / content_len, 2) if content_len > 0 else 0
        compression_stats[r.category] = {
            "count": r.count,
            "avg_content_len": round(content_len),
            "avg_summary_len": round(summary_len),
            "compression_ratio": ratio,
        }
    
    return {
        "file_tiers": tiers,
        "source_distribution": sources,
        "recent_consolidations": recent_memories,
        "promotion_candidates": promotion_candidates,
        "compression_stats": compression_stats,
    }
```

### 2. New template: `src/web/templates/memory_consolidation.html`

Dashboard with:
- **Sankey-style flow diagram** (simplified): 3 columns showing Surface→Medium→Deep with count badges and arrows (CSS-only, not a charting lib)
- **Source distribution doughnut** (Chart.js): Where memories come from (heartbeat, conversation_summary, manual, etc.)
- **Compression ratio bar chart** (Chart.js): Per-category compression ratio
- **Recent consolidation table**: Last 24h of new SemanticMemory entries
- **Promotion candidates panel**: High-importance WorkingMemory items that could be promoted
- **File tier cards**: Surface/Medium/Deep with file count, total size, age

### 3. New route and nav

**File:** `src/web/app.py` — add route after memory-timeline:
```python
    @app.route('/memory-dashboard')
    def memory_dashboard():
        return render_template('memory_consolidation.html')
```

**File:** `src/web/templates/base.html` — add to Memory dropdown.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API reads ORM + filesystem (aria_memories only). Template via /api/ proxy. |
| 2 | .env for secrets (zero in code) | ❌ | Uses ARIA_MEMORIES_PATH env var (non-secret config). |
| 3 | models.yaml single source of truth | ❌ | No model references. |
| 4 | Docker-first testing | ✅ | File paths must work inside Docker container (volume mount). |
| 5 | aria_memories only writable path | ✅ | Reads from aria_memories/ — doesn't write. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **S-31, S-32** — shares nav menu changes. Non-blocking.
- File tier visualization depends on `aria_memories/memory/` directory existing (created by `MemoryManager`).

## Verification
```bash
# 1. API endpoint returns consolidation data:
curl -s "http://localhost:8000/api/memory-consolidation" | python3 -m json.tool | head -30
# EXPECTED: JSON with "file_tiers", "source_distribution", "compression_stats"

# 2. Route registered:
grep -n "memory.dashboard\|memory_dashboard" src/web/app.py
# EXPECTED: route for /memory-dashboard

# 3. Template exists:
ls -la src/web/templates/memory_consolidation.html
# EXPECTED: file exists

# 4. Reads only from aria_memories:
grep -n "aria_memories\|ARIA_MEMORIES_PATH" src/api/routers/memories.py | tail -5
# EXPECTED: references to aria_memories path

# 5. No writes to filesystem:
grep -n "\.write\|open.*w\|makedirs\|mkdir" src/api/routers/memories.py | grep -i "consolidation"
# EXPECTED: no output (read-only endpoint)
```

## Prompt for Agent
```
You are implementing S-35: Memory Consolidation Dashboard for the Aria project.

FILES TO READ FIRST:
- aria_mind/memory.py (full file) — MemoryManager with 3-tier file memory
- aria_skills/memory_compression/__init__.py (lines 1-100) — compression pipeline
- aria_skills/conversation_summary/__init__.py (lines 1-80) — session summarizer
- src/api/routers/memories.py (lines 1-514) — where to add endpoint
- src/web/templates/creative_pulse.html — REFERENCE for dashboard pattern with Chart.js

CONSTRAINTS:
1. ORM for DB access, os.path/pathlib for file system reads
2. Only read from aria_memories/ — never write
3. ARIA_MEMORIES_PATH env var for base path (default: "aria_memories")
4. Template extends base.html, uses Chart.js CDN

STEPS:
1. Add GET /memory-consolidation endpoint (see Fix section)
2. Create src/web/templates/memory_consolidation.html with:
   a. File tier cards (surface/medium/deep) with count, size, age
   b. CSS flow diagram: Surface → Medium → Deep with arrows
   c. Chart.js doughnut: source distribution
   d. Chart.js bar: compression ratios per category
   e. Table: recent consolidations (last 24h)
   f. Panel: promotion candidates (high-importance WorkingMemory)
3. Add /memory-dashboard route to src/web/app.py
4. Add nav link in base.html
5. Run verification commands
```
