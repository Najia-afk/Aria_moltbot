# S3-03: Extract Shared Data Loader Functions
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
Data loading functions are duplicated across templates:

| Function | Duplicated In | Copies |
|----------|--------------|--------|
| `loadStats` | sessions.html, model_usage.html, skill_stats.html, security.html | 4 |
| `loadAll` | sessions.html, model_usage.html | 2 |
| `loadBalances` | models.html, wallets.html | 2 |
| `updateStats` | proposals.html, goals.html | 2 |
| `init` | rate_limits.html, performance.html, working_memory.html | 3 |

These functions follow similar patterns: fetch data from API, parse JSON, update DOM. The specific endpoints differ, but the fetch+error-handling pattern is identical.

## Root Cause
Each page implemented its own data loading without a shared abstraction. The `aria-common.js` file (created Feb 11) started this consolidation with `fetchBalances()` and `fetchSpendSummary()`, but only covers balances/spend.

## Fix
Extend `aria-common.js` or create `data-loaders.js` with a generic fetch wrapper:

```javascript
/**
 * Fetch data from an API endpoint with standard error handling.
 * @param {string} url - API endpoint URL
 * @param {object} options - Fetch options
 * @returns {Promise<object>} Parsed JSON response
 */
async function fetchAriaData(url, options = {}) {
    const { timeout = 10000, retries = 1 } = options;
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    
    try {
        const response = await fetch(url, { signal: controller.signal, ...options });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        clearTimeout(timeoutId);
        if (retries > 0) {
            await new Promise(r => setTimeout(r, 1000));
            return fetchAriaData(url, { ...options, retries: retries - 1 });
        }
        throw error;
    }
}
```

Then standardize `loadStats`, `loadAll`, etc. to use this wrapper.

**Important note:** While the function names are duplicated, the implementations likely differ (different endpoints, different DOM updates). We should extract the **fetch pattern** but keep page-specific DOM update logic inline.

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
S3-01 should complete first (shared utils pattern established).

## Verification
```bash
# 1. Shared fetch wrapper exists:
grep -n "fetchAriaData\|fetchWithRetry\|fetchWithTimeout" src/web/static/js/aria-common.js src/web/static/js/utils.js 2>/dev/null
# EXPECTED: function defined in one of the shared JS files

# 2. Architecture check — fewer data loader duplicates:
python3 scripts/check_architecture.py 2>&1 | grep "DUP_JS.*loadStats\|DUP_JS.*loadAll\|DUP_JS.*loadBalances\|DUP_JS.*updateStats\|DUP_JS.*init"
# EXPECTED: fewer warnings than before

# 3. All affected pages return 200:
for page in sessions model-usage wallets models proposals goals rate-limits performance working-memory security; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000/$page"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Extract shared data loading patterns into a reusable fetch wrapper.

**Files to read FIRST:**
- src/web/static/js/aria-common.js (full — existing shared code, check for fetchBalances/fetchSpendSummary)
- src/web/static/js/utils.js (full — check for existing fetch helpers)
- Run: grep -rn "function loadStats\|function loadAll\|function loadBalances\|function updateStats\|function init" src/web/templates/ --include="*.html"
  → This gives you the exact files and line numbers for every duplicate
- For each duplicate found, read 20 lines around it to understand if the implementation is truly identical or just same-named:
  - src/web/templates/sessions.html (search for `function loadStats`)
  - src/web/templates/model_usage.html (search for `function loadStats`)
  - src/web/templates/skill_stats.html (search for `function loadStats`)
  - src/web/templates/security.html (search for `function loadStats`)
  - src/web/templates/models.html (search for `function loadBalances`)
  - src/web/templates/wallets.html (search for `function loadBalances`)
  - src/web/templates/proposals.html (search for `function updateStats`)
  - src/web/templates/goals.html (search for `function updateStats`)

**Constraints:**
- Constraint 4 (Docker-first): rebuild web container and verify ALL affected pages after changes
- S3-01 must be complete first (shared utils pattern established)

**Steps:**
1. Audit all duplicated data-loading functions:
   a. Run: grep -rn "function loadStats\|function loadAll\|function loadBalances\|function updateStats" src/web/templates/ --include="*.html"
   b. For each match, read the full function body (typically 10-30 lines)
   c. Classify each as: IDENTICAL (exact same logic, different endpoint) vs UNIQUE (same name, different behavior)
2. Create the shared fetchAriaData wrapper:
   a. Add to src/web/static/js/aria-common.js (NOT a new file — keep shared JS consolidated)
   b. Signature: `async function fetchAriaData(url, options = {})` with timeout, retry, and AbortController
   c. Must handle: timeout (10s default), retry on 5xx (1 retry default), JSON parse, error callback
3. Extract TRULY identical functions:
   a. If `loadBalances` in models.html and wallets.html calls the same endpoint with same DOM updates → extract to aria-common.js
   b. If `loadStats` in sessions.html and model_usage.html fetches different endpoints → keep separate but use fetchAriaData as base
4. Rename false duplicates:
   a. If two functions named `loadStats` do completely different things, rename one: `loadSessionStats`, `loadModelStats`, etc.
   b. This eliminates architecture checker false positives without breaking anything
   c. Update ALL call sites after renaming (search for the function name in the same template)
5. Add `<script src="/static/js/aria-common.js"></script>` to any template that uses the shared functions but doesn't include it
6. Verify:
   a. Run: python3 scripts/check_architecture.py 2>&1 | grep -i "dup.*js\|warning" | head -10
   b. EXPECTED: fewer duplicate warnings than before (was 13)
   c. Run: for page in sessions model-usage wallets models proposals goals rate-limits performance working-memory security; do curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000/$page"; done
   d. EXPECTED: all 200
```
