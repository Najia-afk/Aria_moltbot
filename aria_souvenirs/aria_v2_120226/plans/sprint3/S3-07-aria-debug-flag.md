# S3-07: Add Global ARIA_DEBUG Flag
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P2 | **Points:** 2 | **Phase:** 3

## Problem
Debug logging is scattered across templates:
- Some use `console.log` (which should NOT be in production — see S1-02)
- Some use conditional logging with local booleans
- No single flag to turn debugging on/off across the entire frontend

After S1-02 removes bare console.logs, we need a clean mechanism for when debugging IS needed.

## Root Cause
No debug infrastructure exists. Developers add `console.log` when debugging and forget to remove them later.

## Fix
Add a global debug flag to `aria-common.js`:

```javascript
// Global debug flag — set via ?debug=1 in URL or localStorage
const ARIA_DEBUG = (new URLSearchParams(window.location.search).has('debug')) ||
                   (localStorage.getItem('aria_debug') === '1');

function ariaLog(...args) {
    if (ARIA_DEBUG) {
        console.log('[ARIA]', ...args);
    }
}

function ariaWarn(...args) {
    if (ARIA_DEBUG) {
        console.warn('[ARIA]', ...args);
    }
}
```

Usage across templates:
```javascript
// Instead of:  console.log('Loading goals...');
// Use:         ariaLog('Loading goals...');
```

This gives developers a clean way to debug in production without shipping noise.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify in container |
| 5 | aria_memories writable | ❌ | Code changes |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S1-02 must be complete first (remove bare console.logs before adding debug infrastructure).

## Verification
```bash
# 1. ARIA_DEBUG flag exists:
grep -n "ARIA_DEBUG" src/web/static/js/aria-common.js
# EXPECTED: const ARIA_DEBUG defined

# 2. ariaLog and ariaWarn exist:
grep -n "function ariaLog\|function ariaWarn" src/web/static/js/aria-common.js
# EXPECTED: both functions defined

# 3. No bare console.log remaining in templates:
grep -rn "console\.log\b" src/web/templates/ --include="*.html" | grep -v "ariaLog\|ARIA_DEBUG\|// debug" | wc -l
# EXPECTED: 0

# 4. Test that debug mode works:
curl -s "http://localhost:5000/?debug=1" | grep -c "ARIA_DEBUG"
# EXPECTED: 0 (flag is in JS, not visible in HTML source)

# 5. All pages load:
for page in / goals thoughts memories; do
  curl -s -o /dev/null -w "%{http_code}\n" "http://localhost:5000$page"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Add a global ARIA_DEBUG flag and ariaLog/ariaWarn debug helpers.

**Files to read:**
- src/web/static/js/aria-common.js (full — add to this file)
- Scan: grep -rn "console\.\(log\|warn\|debug\)" src/web/templates/ --include="*.html"

**Steps:**
1. Add ARIA_DEBUG, ariaLog(), ariaWarn() to the TOP of aria-common.js
2. Replace any remaining console.log/warn in templates with ariaLog/ariaWarn
3. Test page loads normally (no debug output by default)
4. Test page loads with ?debug=1 (debug output appears in browser console)
```
