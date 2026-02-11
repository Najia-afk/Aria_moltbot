# S2-09: Wire Pagination into All Frontend Templates
**Epic:** E2 — Pagination | **Priority:** P1 | **Points:** 5 | **Phase:** 1

## Problem
After S2-08 creates the shared pagination component, each template's `loadData()` function needs to be updated to:
1. Pass `page` and `limit` to API calls
2. Handle the new `{items, total, page, limit, pages}` response format
3. Add a `<div id="pagination-xxx">` container
4. Initialize `AriaPagination` and update on data load

## Root Cause
Templates currently call APIs and expect flat arrays. The new paginated format wraps data in `{items: [...]}`.

## Fix

Templates to update (9 templates):
1. `goals.html` — Goals table/grid
2. `activities.html` — Activity log table
3. `thoughts.html` — Thoughts table
4. `memories.html` — Memories table
5. `social.html` — Social posts
6. `sessions.html` — Agent sessions table
7. `security.html` — Security events table
8. `model_usage.html` — Model usage table (if exists, or the pricing page)
9. `working_memory.html` — Working memory

For each template, the pattern is:

BEFORE (example from goals.html):
```javascript
async function loadGoals() {
    const resp = await fetch(`${API_BASE}/goals?limit=100&status=${filter}`);
    const goals = await resp.json();
    renderGoals(goals);
}
```

AFTER:
```javascript
let goalsPager;
let goalsState = { page: 1, limit: 25 };

async function loadGoals(page = 1, limit = 25) {
    goalsState = { page, limit };
    const resp = await fetch(`${API_BASE}/goals?page=${page}&limit=${limit}&status=${filter}`);
    const data = await resp.json();
    renderGoals(data.items || data);  // backward compat
    if (goalsPager) goalsPager.update(data);
}

// Initialize pagination
document.addEventListener('DOMContentLoaded', () => {
    goalsPager = new AriaPagination('goals-pagination', {
        onPageChange: (page, limit) => loadGoals(page, limit),
        limit: 25
    });
    loadGoals();
});
```

Add `<div id="goals-pagination"></div>` after the data container in HTML.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend-only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first | ✅ | Test in browser |
| 5 | aria_memories writable | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S2-06** (API pagination) and **S2-08** (pagination.js) must complete first.

## Verification
```bash
# 1. Verify pagination containers exist in all templates:
for t in goals activities thoughts memories social sessions security working_memory; do
  count=$(grep -c 'pagination' src/web/templates/${t}.html 2>/dev/null || echo 0)
  echo "$t: $count pagination references"
done
# EXPECTED: All show 2+ references

# 2. Verify AriaPagination is instantiated:
grep -l 'AriaPagination' src/web/templates/*.html | wc -l
# EXPECTED: 9 files

# 3. Browser test: Navigate to each page and verify pagination controls appear
```

## Prompt for Agent
```
You are wiring pagination into all Aria dashboard templates.

FILES TO READ FIRST:
- src/web/static/js/pagination.js (the AriaPagination class from S2-08)
- src/web/templates/goals.html (example template to update)
- All 9 templates listed above

STEPS (for EACH of the 9 templates):
1. Read the template and find the loadData/loadXxx function
2. Add page/limit parameters to the function
3. Update fetch URL to include &page= and &limit=
4. Change response parsing to use data.items (with fallback)
5. Add <div id="xxx-pagination"></div> after the data container
6. Initialize AriaPagination on DOMContentLoaded
7. Verify all 9 templates are updated

CONSTRAINTS: Frontend-only. Use AriaPagination class. Maintain backward compatibility.
```
