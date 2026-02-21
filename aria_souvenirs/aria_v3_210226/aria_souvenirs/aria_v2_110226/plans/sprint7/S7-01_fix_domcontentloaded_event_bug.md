# S7-01: Fix DOMContentLoaded Event Object Bug

## Summary
Four pages pass the `Event` object as the first argument to their load functions when using `document.addEventListener('DOMContentLoaded', loadFn)`. The Event object gets interpreted as the `page` parameter → FastAPI returns 422 validation error → pages show empty. Fix: wrap in arrow function `() => loadFn()`.

**Affected pages:** Thoughts (67 rows in DB, page empty), Memories (31 rows), Social (19 rows), Goals (53 rows — may partially work but fragile).

## Priority / Points
- **Priority**: P0-Critical
- **Story Points**: 2
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] thoughts.html: `DOMContentLoaded, loadThoughts` → `DOMContentLoaded, () => loadThoughts()`
- [ ] memories.html: `DOMContentLoaded, loadMemories` → `DOMContentLoaded, () => loadMemories()`
- [ ] social.html: `DOMContentLoaded, loadPosts` → `DOMContentLoaded, () => loadPosts()`
- [ ] goals.html: `DOMContentLoaded, loadGoals` → `DOMContentLoaded, () => loadGoals()`
- [ ] All four pages display data after fix
- [ ] No 422 errors in API logs

## Technical Details
The `DOMContentLoaded` event listener passes the Event object as the first argument to the callback. When the callback has a default parameter (e.g., `loadThoughts(page = 1)`), the Event object overrides the default → `page = [object Event]` → FastAPI rejects with 422.

### Root Cause (per file)
| File | Line | Current Code |
|------|------|-------------|
| src/web/templates/thoughts.html | ~140 | `document.addEventListener('DOMContentLoaded', loadThoughts)` |
| src/web/templates/memories.html | ~283 | `document.addEventListener('DOMContentLoaded', loadMemories)` |
| src/web/templates/social.html | ~451 | `document.addEventListener('DOMContentLoaded', loadPosts)` |
| src/web/templates/goals.html | ~1395 | `document.addEventListener('DOMContentLoaded', loadGoals)` |

## Files to Modify
| File | Change |
|------|--------|
| src/web/templates/thoughts.html | Wrap loadThoughts in arrow function |
| src/web/templates/memories.html | Wrap loadMemories in arrow function |
| src/web/templates/social.html | Wrap loadPosts in arrow function |
| src/web/templates/goals.html | Wrap loadGoals in arrow function |

## Verification
```bash
# After fix, these should return data:
curl -s 'http://localhost:8000/thoughts?page=1&limit=5' | python3 -m json.tool
curl -s 'http://localhost:8000/memories?page=1&limit=5' | python3 -m json.tool
curl -s 'http://localhost:8000/social?page=1&limit=5' | python3 -m json.tool
curl -s 'http://localhost:8000/goals?page=1&limit=5' | python3 -m json.tool
# Then load each page in the browser and confirm data renders
```

## Dependencies
- None (independent fix)
