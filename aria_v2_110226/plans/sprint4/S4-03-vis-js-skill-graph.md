# S4-03: Create vis.js Skill Graph Visualization Page
**Epic:** E8 — Knowledge Graph | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
No dedicated visualization for the skill/focus graph. The existing knowledge.html shows a general entity graph but doesn't highlight skills, focus modes, or tool relationships in a meaningful way.

## Root Cause
knowledge.html visualizes all entities equally. A skill-focused view with color-coded nodes, cluster grouping by category, and interactive filtering is needed.

## Fix

### Step 1: Create template
**File: `src/web/templates/skill_graph.html`** (NEW)

Features:
- vis.js network graph (already used in knowledge.html — reference implementation)
- Color-coded by entity type: skills=blue, tools=purple, focus_modes=orange, categories=green
- Node size based on connection count (more connected = larger)
- Click on skill → show tools, dependencies, focus affinities in sidebar
- Filter controls: by type, by category, by focus mode
- Search bar to highlight matching nodes
- Layout: hierarchical (focus → category → skill → tool) or physics-based toggle
- Edge labels showing relation type (depends_on, provides, affinity, belongs_to)
- Cluster toggle: group nodes by category with expand/collapse
- Query log panel: shows recent pathfinding queries (from S4-05)

### Step 2: Add Flask route
**File: `src/web/app.py`**
```python
@app.route('/skill-graph')
def skill_graph():
    return render_template('skill_graph.html')
```

### Step 3: Add navigation link
**File: `src/web/templates/base.html`**
Add to Intelligence dropdown:
```html
<a href="/skill-graph" class="nav-link">🔗 Skill Graph</a>
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend fetches from API |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in browser |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S4-01** (graph populated) and **S4-02** (traverse/search endpoints)

## Verification
```bash
# 1. Template exists:
ls src/web/templates/skill_graph.html

# 2. Route exists:
grep 'skill.graph\|skill_graph' src/web/app.py

# 3. Nav link:
grep 'skill-graph\|Skill Graph' src/web/templates/base.html

# 4. Page loads:
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/skill-graph
# EXPECTED: 200

# 5. Uses vis.js:
grep 'vis-network\|vis.Network\|vis.DataSet' src/web/templates/skill_graph.html
# EXPECTED: vis.js usage found
```

## Prompt for Agent
```
Create a skill graph visualization page using vis.js for the Aria dashboard.

FILES TO READ FIRST:
- src/web/templates/knowledge.html (REFERENCE — existing vis.js graph)
- src/web/templates/base.html (extend, nav link)
- src/web/app.py (add route)

STEPS:
1. Create src/web/templates/skill_graph.html
2. Fetch data from /knowledge-graph (filter for auto_generated entities)
3. Color-code nodes by type, size by connections
4. Add click handler showing details sidebar
5. Add search, filter, layout toggle
6. Add route and nav link
7. Match dark theme

CONSTRAINTS: vis.js (already in project). Vanilla JS. Dark theme.
```
