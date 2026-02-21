# S3-01: Extract Shared Utility Functions to utils.js
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P0 | **Points:** 5 | **Phase:** 3

## Problem
The architecture checker found 13 duplicate JS functions across templates. Four utility functions are duplicated most frequently:

| Function | Duplicated In | Copies |
|----------|--------------|--------|
| `escapeHtml` | sprint_board.html, proposals.html | 2 |
| `formatTime` | search.html, thoughts.html, memories.html | 3 |
| `showToast` | heartbeat.html, goals.html, memories.html | 3 |
| `closeModal` | social.html, performance.html, knowledge.html | 3 |

Total: **11 duplicate function definitions** that should be in a shared file.

## Root Cause
Templates were developed independently and each embedded their own utility functions. A shared `utils.js` already exists at `src/web/static/js/utils.js` (2061 bytes, created 2026-02-11) but not all templates use it, and it may not contain all needed functions.

## Fix
1. Read current `utils.js` to see what's already there
2. Add missing functions (`escapeHtml`, `formatTime`, `showToast`, `closeModal`)
3. Update each template to:
   a. Add `<script src="/static/js/utils.js"></script>` if not present
   b. Remove the inline duplicate function definition
4. Verify all pages still work

**Key principle:** Templates should NOT define utility functions inline. All shared functions go in `utils.js`.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify pages load after changes |
| 5 | aria_memories writable | ❌ | Code changes only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — first in Sprint 3. S3-02..S3-07 may reference utils.js additions made here.

## Verification
```bash
# 1. Architecture check — fewer duplicate warnings:
python3 scripts/check_architecture.py 2>&1 | grep "DUP_JS.*escapeHtml\|DUP_JS.*formatTime\|DUP_JS.*showToast\|DUP_JS.*closeModal"
# EXPECTED: no output (duplicates removed)

# 2. Functions in utils.js:
grep -n "function escapeHtml\|function formatTime\|function showToast\|function closeModal" src/web/static/js/utils.js
# EXPECTED: all 4 functions defined

# 3. Templates include utils.js:
for tmpl in sprint_board proposals search thoughts memories heartbeat goals social performance knowledge; do
  grep -l "utils.js" "src/web/templates/${tmpl}.html" 2>/dev/null && echo "  ✅ $tmpl" || echo "  ❌ $tmpl missing utils.js"
done
# EXPECTED: all ✅

# 4. No inline duplicates:
grep -rn "function escapeHtml\|function formatTime\|function showToast\|function closeModal" src/web/templates/*.html
# EXPECTED: no output (all moved to utils.js)

# 5. All affected pages return 200:
for page in sprint-board proposals search thoughts memories heartbeat goals social performance knowledge; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000/$page"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Extract duplicate utility functions from templates into shared utils.js.

**Files to read:**
- src/web/static/js/utils.js (full — see what's already there)
- src/web/templates/sprint_board.html (search for escapeHtml)
- src/web/templates/thoughts.html (search for formatTime)
- src/web/templates/goals.html (search for showToast)
- src/web/templates/social.html (search for closeModal)

**Constraints:** Docker-first testing.

**Steps:**
1. Read utils.js to understand existing functions
2. Read each template to find the canonical implementation of each function
3. Add missing functions to utils.js (use the most complete implementation)
4. For each template with a duplicate:
   a. Verify `<script src="/static/js/utils.js"></script>` is included
   b. Remove the inline function definition
   c. Test the page loads correctly
5. Run architecture checker to verify duplicate count reduced
6. Run verification commands
```
