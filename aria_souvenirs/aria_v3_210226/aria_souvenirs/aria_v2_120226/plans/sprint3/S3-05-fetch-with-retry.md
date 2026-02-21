# S3-05: Add fetchWithRetry Wrapper for All API Calls
**Epic:** Sprint 3 — Frontend Deduplication | **Priority:** P1 | **Points:** 3 | **Phase:** 3

## Problem
Frontend pages make API calls with inconsistent error handling:
- Some pages silently fail
- Some show "Failed to load" without retry option
- Some have timeout handling, others don't
- No standardized loading/error states

Sprint 6 ticket S6-04 added error handling to some pages, but the implementation is scattered across individual templates.

## Root Cause
Each template implements its own `fetch()` calls with varying error handling patterns. No shared wrapper exists for consistent timeout, retry, and error display.

## Fix
Add `fetchWithRetry()` to `src/web/static/js/aria-common.js`:

```javascript
/**
 * Fetch with timeout, retry, and error display.
 * @param {string} url - API URL
 * @param {object} options - {timeout: ms, retries: n, onError: fn}
 * @returns {Promise<Response>}
 */
async function fetchWithRetry(url, options = {}) {
    const { timeout = 10000, retries = 2, onError = null } = options;
    let lastError;
    
    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);
            const response = await fetch(url, { signal: controller.signal });
            clearTimeout(timeoutId);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response;
        } catch (error) {
            lastError = error;
            if (attempt < retries) {
                await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
            }
        }
    }
    
    if (onError) onError(lastError);
    throw lastError;
}

/**
 * Show error state in a container element.
 * @param {string} containerId - DOM element ID
 * @param {string} message - Error message
 * @param {function} retryFn - Function to call on retry click
 */
function showErrorState(containerId, message, retryFn) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `
        <div class="error-state" style="text-align:center;padding:2rem;color:#ff6b6b;">
            <p>⚠️ ${escapeHtml(message)}</p>
            ${retryFn ? '<button onclick="(' + retryFn.toString() + ')()" class="btn btn-sm btn-outline-light mt-2">Retry</button>' : ''}
        </div>
    `;
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Frontend only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No models |
| 4 | Docker-first | ✅ | Verify all pages work |
| 5 | aria_memories writable | ❌ | Code changes |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S3-01 (utils.js must have `escapeHtml` for the error state).

## Verification
```bash
# 1. fetchWithRetry in shared JS:
grep -n "fetchWithRetry\|showErrorState" src/web/static/js/aria-common.js
# EXPECTED: both functions defined

# 2. At least some templates use it:
grep -rl "fetchWithRetry\|showErrorState" src/web/templates/ --include="*.html" | wc -l
# EXPECTED: > 0

# 3. All pages load:
for page in / goals thoughts memories models wallets sessions; do
  curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000$page"
done
# EXPECTED: all 200
```

## Prompt for Agent
```
Add a shared fetchWithRetry wrapper and error display function, then retrofit 2-3 pages.

**Files to read FIRST:**
- src/web/static/js/aria-common.js (full — this is where you'll add the functions)
- src/web/static/js/utils.js (full — check for existing escapeHtml, any fetch helpers)
- src/web/templates/goals.html — search for `fetch(` to see current error handling pattern
- src/web/templates/thoughts.html — search for `fetch(` to see a second pattern
- src/web/templates/memories.html — search for `fetch(` to see a third pattern
- Run: grep -rn "fetch(" src/web/templates/ --include="*.html" | grep -v "fetchWithRetry\|fetchAriaData" | wc -l
  → Count how many raw fetch() calls exist (these are all candidates for retrofit)

**Constraints:**
- Constraint 4 (Docker-first): verify all pages work in running container after changes
- S3-01 dependency: utils.js must have `escapeHtml()` — verify before using it in showErrorState

**Steps:**
1. Verify escapeHtml exists:
   a. Run: grep -n "function escapeHtml" src/web/static/js/*.js
   b. If NOT found → add it to utils.js first (from S3-01), then continue
2. Add fetchWithRetry() to aria-common.js:
   a. Place AFTER any existing utility functions, BEFORE any page-specific code
   b. Signature: `async function fetchWithRetry(url, options = {})`
   c. Options: `{ timeout: 10000, retries: 2, onError: null }`
   d. Must use AbortController for timeout, exponential delay between retries
   e. Returns the Response object (caller does `.json()` themselves)
3. Add showErrorState() to aria-common.js:
   a. Signature: `function showErrorState(containerId, message, retryFn)`
   b. Uses escapeHtml() for the message text (XSS safe)
   c. Shows a retry button if retryFn is provided
4. Retrofit goals.html as the first example:
   a. Find all `fetch('/api/goals'...)` calls
   b. Replace with: `const response = await fetchWithRetry('/api/goals')`
   c. Add try/catch with showErrorState for the container
   d. Test: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/goals → 200
5. Retrofit thoughts.html as the second example:
   a. Same pattern as step 4 for `/api/thoughts`
   b. Test: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/thoughts → 200
6. Retrofit memories.html as the third example:
   a. Same pattern for `/api/memories`
   b. Test: curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/memories → 200
7. Final verification:
   a. Run: grep -n "fetchWithRetry\|showErrorState" src/web/static/js/aria-common.js
   b. EXPECTED: both functions defined
   c. Run: grep -rl "fetchWithRetry" src/web/templates/ --include="*.html" | wc -l
   d. EXPECTED: >= 3 (the three retrofitted pages)
   e. Run: for page in / goals thoughts memories models wallets sessions knowledge; do curl -s -o /dev/null -w "%{http_code} $page\n" "http://localhost:5000$page"; done
   f. EXPECTED: all 200
```
