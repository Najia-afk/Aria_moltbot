# S-36: Lessons Learned Dashboard — Error Pattern Graph & Effectiveness Trends
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P2 | **Points:** 3 | **Phase:** 3

## Problem

The `LessonLearned` model (`src/api/db/models.py`, table `aria_data.lessons_learned`) stores error patterns, resolutions, occurrence counts, and effectiveness scores. The API router `src/api/routers/lessons.py` provides full CRUD + lookup by pattern/type/skill + bulk seed.

However, there is **no dedicated web page** for viewing lessons. The data exists and the API works, but the only way to see it is via raw API calls (`GET /api/lessons`). There is no:
1. Error pattern network graph (which skills produce which errors → which resolutions fix them)
2. Effectiveness trend over time
3. Occurrence frequency chart
4. Skill error heatmap

The `tasks/lessons.md` markdown file captures lessons manually, but the DB-backed `LessonLearned` system is invisible to the user.

## Root Cause

The `lessons_learned` table was added as a programmatic error-learning system for Aria's self-correction loop, not as a user-facing feature. The API (`src/api/routers/lessons.py`) was built for skill consumption, not for dashboard rendering.

No template `lessons.html` exists. No route `/lessons` exists in `src/web/app.py`.

## Fix

### 1. New API endpoint: `GET /api/lessons/dashboard`

**File:** `src/api/routers/lessons.py`

```python
@router.get("/lessons/dashboard")
async def get_lessons_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard data for lessons learned visualization:
    - Skill → error type graph (for vis-network)
    - Top patterns by occurrence
    - Effectiveness distribution
    - Recent lessons
    """
    # All lessons (cap at 500 for performance)
    stmt = select(LessonLearned).order_by(LessonLearned.occurrences.desc()).limit(500)
    result = await db.execute(stmt)
    lessons = result.scalars().all()
    
    # Build graph nodes and edges
    nodes = []
    edges = []
    skill_set = set()
    error_type_set = set()
    
    for ll in lessons:
        lesson_id = f"lesson_{ll.id}"
        nodes.append({
            "id": lesson_id,
            "label": ll.error_pattern[:40],
            "type": "lesson",
            "occurrences": ll.occurrences,
            "effectiveness": ll.effectiveness,
            "resolution": ll.resolution,
        })
        
        # Skill node
        skill = ll.skill_name or "unknown"
        if skill not in skill_set:
            nodes.append({"id": f"skill_{skill}", "label": skill, "type": "skill"})
            skill_set.add(skill)
        edges.append({"from": f"skill_{skill}", "to": lesson_id, "type": "produces"})
        
        # Error type node
        etype = ll.error_type or "generic"
        if etype not in error_type_set:
            nodes.append({"id": f"etype_{etype}", "label": etype, "type": "error_type"})
            error_type_set.add(etype)
        edges.append({"from": lesson_id, "to": f"etype_{etype}", "type": "classified_as"})
    
    # Stats
    total = len(lessons)
    avg_effectiveness = sum(ll.effectiveness for ll in lessons) / total if total else 0
    total_occurrences = sum(ll.occurrences for ll in lessons)
    top_patterns = [
        {
            "pattern": ll.error_pattern,
            "skill": ll.skill_name,
            "occurrences": ll.occurrences,
            "effectiveness": ll.effectiveness,
        }
        for ll in lessons[:15]
    ]
    
    # Effectiveness distribution (buckets)
    eff_buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    for ll in lessons:
        e = ll.effectiveness
        if e < 0.2: eff_buckets["0.0-0.2"] += 1
        elif e < 0.4: eff_buckets["0.2-0.4"] += 1
        elif e < 0.6: eff_buckets["0.4-0.6"] += 1
        elif e < 0.8: eff_buckets["0.6-0.8"] += 1
        else: eff_buckets["0.8-1.0"] += 1
    
    # Per-skill aggregates
    skill_stats = {}
    for ll in lessons:
        s = ll.skill_name or "unknown"
        skill_stats.setdefault(s, {"count": 0, "total_occ": 0, "avg_eff": 0})
        skill_stats[s]["count"] += 1
        skill_stats[s]["total_occ"] += ll.occurrences
        skill_stats[s]["avg_eff"] += ll.effectiveness
    for s in skill_stats:
        n = skill_stats[s]["count"]
        skill_stats[s]["avg_eff"] = round(skill_stats[s]["avg_eff"] / n, 3) if n else 0
    
    return {
        "graph": {"nodes": nodes, "edges": edges},
        "stats": {
            "total_lessons": total,
            "avg_effectiveness": round(avg_effectiveness, 3),
            "total_occurrences": total_occurrences,
        },
        "top_patterns": top_patterns,
        "effectiveness_distribution": eff_buckets,
        "skill_breakdown": skill_stats,
    }
```

### 2. New template: `src/web/templates/lessons.html`

Dashboard with:
- **Stat cards**: total lessons, avg effectiveness, total occurrences
- **vis-network graph**: Skill nodes (blue squares) → Lesson nodes (orange dots, sized by occurrences) → Error type nodes (red triangles)
- **Top patterns table**: sortable by occurrences, effectiveness
- **Effectiveness distribution bar chart** (Chart.js)
- **Skill breakdown panel**: per-skill error count and avg effectiveness

### 3. New route and nav

**File:** `src/web/app.py`:
```python
    @app.route('/lessons')
    def lessons_page():
        return render_template('lessons.html')
```

**File:** `src/web/templates/base.html` — add to Intelligence dropdown.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API reads LessonLearned via ORM. Template calls /api/ proxy. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved. |
| 3 | models.yaml single source of truth | ❌ | No model references. |
| 4 | Docker-first testing | ✅ | Standard API + template, must test in Docker. |
| 5 | aria_memories only writable path | ❌ | Read-only endpoint. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **None** — Self-contained. Uses existing `lessons.py` router and `LessonLearned` model.

## Verification
```bash
# 1. API endpoint returns dashboard data:
curl -s "http://localhost:8000/api/lessons/dashboard" | python3 -m json.tool | head -20
# EXPECTED: JSON with "graph", "stats", "top_patterns", "effectiveness_distribution", "skill_breakdown"

# 2. Route registered:
grep -n "lessons_page\|/lessons" src/web/app.py
# EXPECTED: route for /lessons

# 3. Template exists with vis-network and Chart.js:
grep -c "vis-network\|Chart" src/web/templates/lessons.html
# EXPECTED: >= 2

# 4. Graph has nodes and edges:
curl -s "http://localhost:8000/api/lessons/dashboard" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Nodes: {len(d[\"graph\"][\"nodes\"])}, Edges: {len(d[\"graph\"][\"edges\"])}')
print(f'Total lessons: {d[\"stats\"][\"total_lessons\"]}')
"
# EXPECTED: Node/edge counts, total lessons count
```

## Prompt for Agent
```
You are implementing S-36: Lessons Learned Dashboard for the Aria project.

FILES TO READ FIRST:
- src/api/routers/lessons.py (full file) — existing CRUD endpoints for LessonLearned
- src/api/db/models.py — search for "LessonLearned" class to get model definition
- src/web/templates/knowledge.html (lines 1-518) — REFERENCE for vis-network graph pattern
- src/web/templates/skill_health.html — REFERENCE for dashboard with stat cards

CONSTRAINTS:
1. ORM for DB access (LessonLearned model)
2. Template extends base.html
3. vis-network for graph (reuse /static/js/vis-network.min.js)
4. Chart.js CDN for effectiveness distribution chart

STEPS:
1. Add GET /lessons/dashboard endpoint to src/api/routers/lessons.py
2. Create src/web/templates/lessons.html with:
   a. Stat cards: total, avg effectiveness, total occurrences
   b. vis-network graph: skill→lesson→error_type
   c. Top patterns table (sortable)
   d. Chart.js bar: effectiveness distribution
   e. Skill breakdown panel
3. Add /lessons route to src/web/app.py
4. Add "Lessons" link to Intelligence nav dropdown in base.html
5. Run verification commands

Graph node types:
- skill: blue (#3b82f6) square, size 16
- lesson: orange (#f59e0b) dot, size = 8 + occurrences * 2 (capped at 24)
- error_type: red (#ef4444) triangle, size 14

Edge types:
- produces: solid blue, width 1
- classified_as: dashed red, width 1
```
