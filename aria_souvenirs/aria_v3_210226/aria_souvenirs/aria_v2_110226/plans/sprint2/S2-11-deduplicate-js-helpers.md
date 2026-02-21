# S2-11: Deduplicate escapeHtml/formatDate Across Templates
**Epic:** E3 — Code Quality | **Priority:** P2 | **Points:** 2 | **Phase:** 1

## Problem
Multiple templates define their own `escapeHtml()` and `formatDate()` functions:
- `pricing.js` has a global `escapeHtml()` and `formatDate()` (relative time)
- `api_key_rotations.html` redefines `formatDate()` (returns `toLocaleString()`)
- `security.html`, `activities.html`, `sessions.html` each define local `escapeHtml()`
- This causes inconsistent behavior and makes maintenance harder.

## Root Cause
Templates were written independently without a shared utility library. Each developer added their own helper functions.

## Fix

### Step 1: Create `src/web/static/js/utils.js` (NEW)
Move shared utility functions here:
```javascript
// Shared utilities for Aria Dashboard
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function formatRelativeTime(dateStr) {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    return date.toLocaleDateString();
}

function formatDateTime(dateStr) {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
}
```

### Step 2: Include in base.html before pagination.js
### Step 3: Remove local definitions from individual templates

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend-only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first | ✅ | Test all pages |
| 5 | aria_memories | ❌ | No writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
None — can run in parallel with other Sprint 2 tickets.

## Verification
```bash
# 1. Verify utils.js exists:
ls src/web/static/js/utils.js
# EXPECTED: file exists

# 2. Check no duplicate escapeHtml definitions remain:
grep -rl 'function escapeHtml' src/web/templates/ | wc -l
# EXPECTED: 0 (all removed from templates)

# 3. Verify utils.js is included in base.html:
grep 'utils.js' src/web/templates/base.html
# EXPECTED: <script src="/static/js/utils.js"></script>
```

## Prompt for Agent
```
You are deduplicating JavaScript utility functions across Aria dashboard templates.

FILES TO READ FIRST:
- src/web/static/js/pricing.js (existing shared JS)
- src/web/templates/base.html (where to include new utils.js)
- grep -rl 'function escapeHtml' src/web/templates/ (find all duplicates)
- grep -rl 'function formatDate' src/web/templates/ (find all duplicates)

STEPS:
1. Create src/web/static/js/utils.js with shared escapeHtml, formatRelativeTime, formatDateTime
2. Include utils.js in base.html before other scripts
3. Remove local escapeHtml/formatDate definitions from ALL templates
4. Verify no duplicate definitions remain

CONSTRAINTS: Frontend-only. Don't break existing template functionality.
```
