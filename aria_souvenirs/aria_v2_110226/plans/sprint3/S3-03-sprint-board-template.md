# S3-03: Create Sprint Board HTML Template
**Epic:** E5 — Sprint Board | **Priority:** P0 | **Points:** 8 | **Phase:** 2

## Problem
No Kanban/sprint board UI exists for managing goals. The current goals.html shows a flat card grid with no column-based workflow view.

## Root Cause
Sprint board is a new feature.

## Fix

### Step 1: Create template
**File: `src/web/templates/sprint_board.html`** (NEW)

Full Kanban board with:
- 5 columns: Backlog | To Do | Doing | On Hold | Done
- Goal cards with priority badge, progress bar, due date
- Drag-and-drop between columns
- Sprint selector dropdown
- Archive tab (Completed/Cancelled)
- Stacked bar chart (goals by day/status)
- Quick-add goal button
- Column counters

The template should extend base.html and follow the same dark theme as other pages.

Card layout:
```
┌─────────────────────────┐
│ 🔴 P1  ┆  Due: 2h      │
│ Goal Title Here         │
│ ▓▓▓▓▓▓░░░░ 60%         │
│ #learn  #create         │
└─────────────────────────┘
```

### Step 2: Add Flask route
**File: `src/web/app.py`**
```python
@app.route('/sprint-board')
def sprint_board():
    return render_template('sprint_board.html')
```

### Step 3: Add to navigation
**File: `src/web/templates/base.html`**
Add to the nav dropdown:
```html
<a href="/sprint-board" class="nav-link">📋 Sprint Board</a>
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend fetches from API, never direct DB |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in browser |
| 5 | aria_memories | ❌ | No file writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S3-01** (Goal model fields) and **S3-02** (board API endpoints) must complete first.

## Verification
```bash
# 1. Template exists:
ls src/web/templates/sprint_board.html
# EXPECTED: file exists

# 2. Route exists in app.py:
grep 'sprint.board\|sprint_board' src/web/app.py
# EXPECTED: route definition found

# 3. Nav link exists:
grep 'sprint' src/web/templates/base.html
# EXPECTED: Sprint Board link in navigation

# 4. Browser test:
curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/sprint-board
# EXPECTED: 200

# 5. Template uses board API:
grep 'goals/board' src/web/templates/sprint_board.html
# EXPECTED: API call to /goals/board
```

## Prompt for Agent
```
You are creating a Kanban sprint board template for the Aria dashboard.

FILES TO READ FIRST:
- src/web/templates/goals.html (reference — existing goal UI, CSS patterns, dark theme)
- src/web/templates/base.html (extends this, navigation structure)
- src/web/app.py (add Flask route)
- Sprint board API from S3-02 (/goals/board, /goals/archive, /goals/{id}/move, /goals/history)

STEPS:
1. Create src/web/templates/sprint_board.html with:
   - 5 Kanban columns (backlog, todo, doing, on_hold, done)
   - Goal cards with priority, progress, due_date, tags
   - HTML5 drag-and-drop (vanilla JS, no libraries)
   - Stacked bar chart using Chart.js (already included in base)
   - Archive tab with pagination
   - Sprint selector
2. Add route to src/web/app.py
3. Add nav link to base.html
4. Match existing dark theme (CSS custom properties from base.html)

CONSTRAINTS: Vanilla JS only (no React/Vue). Chart.js for charts. Fetch API for HTTP calls.
IMPORTANT: Drag-and-drop must call PATCH /goals/{id}/move on drop.
```
