# S-38: Navigation Update — Visualization Pages in Nav Menu
**Epic:** E18 — Visualization & Graph Execution | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem

Tickets S-31 through S-37 create 7 new visualization pages, but the navigation menu in `src/web/templates/base.html` (lines ~155–370) doesn't include them. Users can't discover the new pages without knowing the URLs.

Current Memory dropdown in the nav (from `base.html`):
```
💾 Memory
  ├── /memories         — Key-Value Memory
  ├── /knowledge        — Knowledge Graph
  ├── /working-memory   — Working Memory
  ├── /records          — Records
  ├── /activities       — Activities
  └── /thoughts         — Thoughts
```

After S-31–S-37, the Memory dropdown should become:
```
💾 Memory
  ├── 🔍 /memory-search     — Unified Search (S-37)
  ├── 🕸️ /memory-graph       — Memory Graph (S-31)
  ├── 📊 /memory-timeline    — Timeline & Heatmap (S-32)
  ├── 🔮 /embedding-explorer — Embedding Clusters (S-33)
  ├── 🔄 /memory-dashboard   — Consolidation (S-35)
  ├── ─── (separator) ───
  ├── /memories             — Key-Value Memory
  ├── /memory-explorer      — Semantic Memory ← (currently hidden!)
  ├── /knowledge            — Knowledge Graph
  ├── /working-memory       — Working Memory
  ├── /records              — Records
  ├── /activities           — Activities
  └── /thoughts             — Thoughts
```

And the Intelligence dropdown should get:
```
Intelligence
  └── 📚 /lessons    — Lessons Learned (S-36)
```

**Also**: `/memory-explorer` is currently **NOT in the nav menu** at all (route exists at `src/web/app.py` line 333 but no nav link). This is a pre-existing gap.

## Root Cause

Each S-31–S-37 ticket mentions "update nav" but doing it in each ticket risks merge conflicts. This ticket consolidates all nav changes into a single atomic update.

## Fix

### 1. Update Memory dropdown in `src/web/templates/base.html`

**File:** `src/web/templates/base.html`

Find the Memory dropdown section and replace it with the expanded version. The exact HTML depends on the existing dropdown pattern — look for the `💾 Memory` heading and its `<a>` children.

**New Memory dropdown items (in order):**
```html
<a href="/memory-search" class="dropdown-item">🔍 Memory Search</a>
<a href="/memory-graph" class="dropdown-item">🕸️ Memory Graph</a>
<a href="/memory-timeline" class="dropdown-item">📊 Memory Timeline</a>
<a href="/embedding-explorer" class="dropdown-item">🔮 Embedding Clusters</a>
<a href="/memory-dashboard" class="dropdown-item">🔄 Consolidation</a>
<div class="dropdown-divider"></div>
<a href="/memories" class="dropdown-item">Memories (KV)</a>
<a href="/memory-explorer" class="dropdown-item">Semantic Explorer</a>
<a href="/knowledge" class="dropdown-item">Knowledge Graph</a>
<a href="/working-memory" class="dropdown-item">Working Memory</a>
<a href="/records" class="dropdown-item">Records</a>
<a href="/activities" class="dropdown-item">Activities</a>
<a href="/thoughts" class="dropdown-item">Thoughts</a>
```

### 2. Add Lessons to Intelligence dropdown

Find the Intelligence dropdown and add:
```html
<a href="/lessons" class="dropdown-item">📚 Lessons Learned</a>
```

### 3. (Optional) Add Chat Execution Graph note

The chat execution graph (S-34) is embedded in the chat page — no nav entry needed. But add a tooltip or badge in the chat UI header indicating "Execution Graph Available" when tool calls are present.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ❌ | Template-only change. |
| 2 | .env for secrets (zero in code) | ❌ | No secrets. |
| 3 | models.yaml single source of truth | ❌ | N/A. |
| 4 | Docker-first testing | ✅ | Must verify nav renders correctly in Docker. |
| 5 | aria_memories only writable path | ❌ | No writes. |
| 6 | No soul modification | ❌ | No soul files touched. |

## Dependencies
- **S-31, S-32, S-33, S-34, S-35, S-36, S-37** — All must have their routes registered in `app.py` before nav links will work. However, nav links can be added preemptively (they'll 404 until routes are added).
- **S-05 (nav regrouping)** — If S-05 has already been completed, the nav structure may have changed. Check `base.html` before applying.

## Verification
```bash
# 1. All new nav links present:
for path in memory-search memory-graph memory-timeline embedding-explorer memory-dashboard lessons; do
    count=$(grep -c "$path" src/web/templates/base.html)
    echo "$path: $count matches"
done
# EXPECTED: each path shows >= 1 match

# 2. memory-explorer now in nav (was missing):
grep -c "memory-explorer" src/web/templates/base.html
# EXPECTED: >= 1

# 3. Dropdown divider present:
grep -c "dropdown-divider" src/web/templates/base.html
# EXPECTED: >= 1 (in Memory dropdown)

# 4. No broken links (all routes exist in app.py):
for route in memory-search memory-graph memory-timeline embedding-explorer memory-dashboard lessons; do
    count=$(grep -c "$route" src/web/app.py)
    echo "Route /$route in app.py: $count"
done  
# EXPECTED: each shows >= 1 (routes defined)

# 5. Nav renders without errors (Docker):
curl -s http://localhost:5000/ | grep -c "Memory Graph\|Memory Search\|Memory Timeline"
# EXPECTED: >= 3 (nav links visible on home page)
```

## Prompt for Agent
```
You are implementing S-38: Navigation Update for the Aria project.

FILES TO READ FIRST:
- src/web/templates/base.html (full file, ~512 lines) — navigation structure
- src/web/app.py (lines 128-370) — all route definitions (verify routes exist)

CONSTRAINTS:
1. Only modify base.html (and optionally app.py if S-31–S-37 routes are missing)
2. Preserve existing nav structure — only ADD items, don't remove existing ones
3. Ensure /memory-explorer (line 333 in app.py) gets a nav link (was missing)
4. Use emoji prefixes for new visualization pages (consistent with existing style)
5. Add dropdown-divider between new viz pages and existing CRUD pages

STEPS:
1. Read base.html to find exact Memory and Intelligence dropdown locations
2. Add new Memory dropdown items (see Fix section for exact HTML)
3. Add "Lessons Learned" to Intelligence dropdown
4. Verify all routes exist in app.py (grep for each)
5. Run verification commands
6. Test in Docker to ensure nav renders correctly
```
