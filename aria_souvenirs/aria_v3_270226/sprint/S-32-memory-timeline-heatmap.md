# S-32: Memory Timeline — Temporal Heatmap & Access Pattern Visualization
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P2 | **Points:** 5 | **Phase:** 3

## Problem

Aria creates memories across 5+ stores (SemanticMemory, WorkingMemory, KV Memory, Thoughts, LessonsLearned) continuously via heartbeat, conversation summary, knowledge extraction, and manual storage. However, there is **no temporal view** of when memories were created, accessed, or decayed.

Current memory pages show only static card grids or tables:
- `memory_explorer.html` (422 lines) — card grid with stat cards, no timeline
- `working_memory.html` — CRUD table with importance badges, no decay visualization
- `memories.html` — card grid with category filter, no temporal axis

The `WorkingMemory` model (`src/api/db/models.py` line 642) has `ttl_hours`, `created_at`, `updated_at`, `accessed_at`, and `access_count` — all the data needed for a decay timeline — but this data is never visualized.

The `SemanticMemory` model (`src/api/db/models.py` line 694) has `created_at`, `accessed_at`, `access_count`, and `importance` — perfect for a temporal heatmap — but no chart renders this.

**Missing:** A `/memory-timeline` route serving a Chart.js-powered temporal dashboard showing:
1. Memory creation heatmap (hour-of-day × day-of-week)
2. Access pattern line chart (memories accessed over time)
3. Working memory TTL countdown bars (live decay visualization)
4. Memory type distribution over time (stacked area chart)

## Root Cause

Memory pages were built for CRUD operations, not analytics. The `memory_explorer.html` has `loadStats()` (line ~260) that fetches `GET /memories/semantic/stats` but this endpoint only returns aggregate counts (`total`, `by_category`, `by_source`, `avg_importance`, `top_accessed`) — no temporal data.

The `working_memory.html` has stat cards for total/categories/importance but no time-series data. The `GET /working-memory/stats` endpoint (`src/api/routers/working_memory.py` line 319) returns category counts and averages, not temporal buckets.

No API endpoint exists that returns time-bucketed memory creation/access data for charting.

## Fix

### 1. New API endpoint: `GET /api/memory-timeline`

**File:** `src/api/routers/memories.py`

**PREREQUISITE — Imports:** This endpoint uses `WorkingMemory` and `Thought` models. If S-31 has not been applied yet, add them to the import at line 16:
```python
from db.models import Memory, SemanticMemory, WorkingMemory, Thought, LessonLearned
```
Also add to imports section:
```python
from datetime import datetime, timedelta
```

```python
@router.get("/memory-timeline")
async def get_memory_timeline(
    hours: int = Query(168, ge=1, le=720, description="Hours lookback (default 7 days)"),
    bucket_hours: int = Query(1, ge=1, le=24, description="Bucket size in hours"),
    db: AsyncSession = Depends(get_db),
):
    """
    Time-bucketed memory creation and access data for timeline charts.
    Returns: creation heatmap, access timeline, type distribution, TTL countdowns.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    
    # 1. Semantic memory creation buckets
    sem_stmt = (
        select(
            func.date_trunc('hour', SemanticMemory.created_at).label('bucket'),
            func.count().label('count'),
            func.avg(SemanticMemory.importance).label('avg_importance'),
        )
        .where(SemanticMemory.created_at >= cutoff)
        .group_by('bucket')
        .order_by('bucket')
    )
    sem_result = await db.execute(sem_stmt)
    sem_buckets = [{"t": r.bucket.isoformat(), "count": r.count, "avg_imp": round(float(r.avg_importance or 0), 3)} for r in sem_result.all()]
    
    # 2. Working memory creation buckets
    wm_stmt = (
        select(
            func.date_trunc('hour', WorkingMemory.created_at).label('bucket'),
            func.count().label('count'),
        )
        .where(WorkingMemory.created_at >= cutoff)
        .group_by('bucket')
        .order_by('bucket')
    )
    wm_result = await db.execute(wm_stmt)
    wm_buckets = [{"t": r.bucket.isoformat(), "count": r.count} for r in wm_result.all()]
    
    # 3. Thought creation buckets
    th_stmt = (
        select(
            func.date_trunc('hour', Thought.created_at).label('bucket'),
            func.count().label('count'),
        )
        .where(Thought.created_at >= cutoff)
        .group_by('bucket')
        .order_by('bucket')
    )
    th_result = await db.execute(th_stmt)
    th_buckets = [{"t": r.bucket.isoformat(), "count": r.count} for r in th_result.all()]
    
    # 4. Working memory TTL countdowns (items with TTL set)
    ttl_stmt = (
        select(WorkingMemory)
        .where(WorkingMemory.ttl_hours.isnot(None))
        .order_by(WorkingMemory.importance.desc())
        .limit(50)
    )
    ttl_result = await db.execute(ttl_stmt)
    ttl_items = []
    now = datetime.utcnow()
    for wm in ttl_result.scalars().all():
        expires_at = wm.created_at + timedelta(hours=wm.ttl_hours) if wm.created_at and wm.ttl_hours else None
        remaining_hours = (expires_at - now).total_seconds() / 3600 if expires_at and expires_at > now else 0
        ttl_items.append({
            "id": str(wm.id),
            "key": f"{wm.category}/{wm.key}",
            "importance": wm.importance,
            "ttl_hours": wm.ttl_hours,
            "remaining_hours": round(remaining_hours, 1),
            "expired": remaining_hours <= 0,
            "created_at": wm.created_at.isoformat() if wm.created_at else None,
        })
    
    # 5. Hour-of-day × day-of-week heatmap for semantic memories
    heatmap_stmt = (
        select(
            func.extract('dow', SemanticMemory.created_at).label('dow'),
            func.extract('hour', SemanticMemory.created_at).label('hour'),
            func.count().label('count'),
        )
        .where(SemanticMemory.created_at >= cutoff)
        .group_by('dow', 'hour')
    )
    heatmap_result = await db.execute(heatmap_stmt)
    heatmap = [{"dow": int(r.dow), "hour": int(r.hour), "count": r.count} for r in heatmap_result.all()]
    
    return {
        "semantic_timeline": sem_buckets,
        "working_memory_timeline": wm_buckets,
        "thoughts_timeline": th_buckets,
        "ttl_countdowns": ttl_items,
        "creation_heatmap": heatmap,
        "period_hours": hours,
        "bucket_hours": bucket_hours,
    }
```

### 2. New template: `src/web/templates/memory_timeline.html`

Chart.js dashboard with:
- **Stacked area chart**: semantic + working + thought creation counts over time (3 datasets)
- **Heatmap**: 7×24 grid (dow × hour), cell color intensity = memory creation count
- **Bar chart**: TTL countdown bars for WorkingMemory items with TTL, colored by remaining time (green→yellow→red)
- **Importance trend**: line chart of average importance over time from `sem_buckets.avg_imp`

Use Chart.js (already CDN-included in most pages via `chart-helpers.js`).

### 3. New route in `src/web/app.py`

**BEFORE:**
```python
    @app.route('/memory-graph')
    def memory_graph():
        return render_template('memory_graph.html')

    @app.route('/sentiment')
```

**AFTER:**
```python
    @app.route('/memory-graph')
    def memory_graph():
        return render_template('memory_graph.html')

    @app.route('/memory-timeline')
    def memory_timeline():
        return render_template('memory_timeline.html')

    @app.route('/sentiment')
```

### 4. Nav menu update in `src/web/templates/base.html`

Add `/memory-timeline` to the 💾 Memory dropdown.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API endpoint uses ORM with `date_trunc` and `extract` aggregations. Template calls through `/api/` proxy. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved. |
| 3 | models.yaml single source of truth | ❌ | No model references. |
| 4 | Docker-first testing | ✅ | PostgreSQL `date_trunc` and `extract` functions — must test in Docker with real DB. |
| 5 | aria_memories only writable path | ❌ | Read-only endpoint. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **S-31** should complete first — shares model imports (`WorkingMemory`, `Thought`, `LessonLearned` in `memories.py` line 16) and nav menu changes.
- **Non-blocking** — Can execute independently if model imports and nav changes are applied inline.

## Verification
```bash
# 1. API endpoint returns timeline data:
curl -s "http://localhost:${ARIA_API_PORT:-8000}/api/memory-timeline?hours=48" | python3 -m json.tool | head -30
# EXPECTED: JSON with "semantic_timeline", "working_memory_timeline", "thoughts_timeline", "ttl_countdowns", "creation_heatmap"

# 2. Route registered:
grep -n "memory.timeline\|memory_timeline" src/web/app.py
# EXPECTED: route definition for /memory-timeline

# 3. Template exists and uses Chart.js:
grep -c "Chart\|chart" src/web/templates/memory_timeline.html
# EXPECTED: >= 5 (Chart.js references)

# 4. Nav link added:
grep -n "memory-timeline" src/web/templates/base.html
# EXPECTED: link in Memory dropdown

# 5. No SQL injection (uses ORM):
grep -rn "text(\|raw\|execute.*f\"" src/api/routers/memories.py | grep -i "memory.timeline"
# EXPECTED: no output (no raw SQL)
```

## Prompt for Agent
```
You are implementing S-32: Memory Timeline for the Aria project.

FILES TO READ FIRST:
- src/web/templates/creative_pulse.html (lines 1-337) — REFERENCE PATTERN for Chart.js time-series dashboard
- src/web/templates/sessions.html — REFERENCE PATTERN for hourly charts
- src/api/routers/memories.py (lines 1-514) — where to add endpoint
- src/api/db/models.py (lines 640-720) — WorkingMemory and SemanticMemory models
- src/web/static/js/chart-helpers.js — shared chart utilities
- src/web/app.py (lines 148-160) — where to add route

CONSTRAINTS:
1. All DB access through ORM (use func.date_trunc, func.extract from sqlalchemy)
2. Template calls API through /api/ proxy
3. Use Chart.js CDN (same as creative_pulse.html, sessions.html)
4. Template must extend base.html

STEPS:
1. Add GET /memory-timeline endpoint to src/api/routers/memories.py (see Fix section)
2. Create src/web/templates/memory_timeline.html with 4 charts:
   a. Stacked area: memory creation over time (3 types)
   b. Heatmap: 7×24 creation pattern (custom Chart.js plugin or matrix-style)
   c. Bar chart: TTL countdowns for WorkingMemory
   d. Line chart: importance trend over time
3. Add /memory-timeline route to src/web/app.py
4. Add nav link in base.html Memory dropdown
5. Run verification commands

Chart.js config reference from sessions.html:
- Time axis: type 'time', time.unit 'hour'
- Stacked: options.scales.y.stacked = true, datasets fill = true
- Colors: use CSS variables --accent-primary (#8b5cf6), --accent-blue (#3b82f6), etc.
```
