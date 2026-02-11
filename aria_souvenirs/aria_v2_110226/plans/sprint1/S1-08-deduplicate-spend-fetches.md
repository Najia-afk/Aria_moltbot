# S1-08: Deduplicate Spend Log Fetches

**Priority:** Medium | **Estimate:** 2 pts | **Status:** TODO

---

## Problem

Both `models.html` and `wallets.html` fire **multiple independent `fetch()` calls** to the same `/litellm/spend` endpoint on page load, causing redundant network traffic and potential race conditions.

### models.html — 3 separate fetch paths

| Caller | Location | Fetch |
|--------|----------|-------|
| `loadGlobalSpend()` | `src/web/templates/models.html:712` | `fetch(\`${API_URL}/litellm/spend?limit=500&lite=true\`)` |
| `updateCharts()` | `src/web/templates/models.html:944` | `fetch(\`${API_URL}/litellm/spend?limit=500&lite=true\`)` (fallback when cache empty) |
| `loadSpendLogs()` | `src/web/templates/models.html:859` | `fetch(\`${API_URL}/litellm/spend?limit=${limit}\`)` (fallback when cache misses) |

`loadGlobalSpend()` stores results to `window._allSpendLogs` at line 763, and both `updateCharts()` (line 937-943) and `loadSpendLogs()` (line 854-857) attempt to read from cache — but race conditions mean the cache may not be populated yet.

Init sequence at `models.html:1227-1232`:
```javascript
await loadGlobalSpend();  // must complete before charts use cached logs
loadModels();             // calls updateCharts() internally at line 790
loadSpendLogs();          // may fire before loadGlobalSpend cache is ready
```

`loadModels()` at line 790 calls `updateCharts()` synchronously, which can race with the `await loadGlobalSpend()`.

### wallets.html — 2 separate fetch paths

| Caller | Location | Fetch |
|--------|----------|-------|
| `loadSpend()` | `src/web/templates/wallets.html:637` | `fetch(\`${API_URL}/litellm/spend?limit=500&lite=true\`)` |
| `createBalanceChart()` | `src/web/templates/wallets.html:699` | `fetch(\`${API_URL}/litellm/spend?limit=500&lite=true\`)` (fallback) |

`loadSpend()` stores to `window._walletSpendLogs` at line 675, but `createBalanceChart()` at line 695-702 may fire before the cache is populated.

---

## Root Cause

No centralized data-fetching layer. Each function independently fetches the same endpoint, with inconsistent caching (sometimes `window._allSpendLogs`, sometimes `window._walletSpendLogs`) and no loading-state guard to prevent concurrent fetches.

---

## Fix

Introduce a single `fetchSpendLogs()` function per page that:
1. Returns a cached promise if a fetch is already in-flight (dedup)
2. Stores the result in `window._spendLogsCache`
3. All consumers call this function instead of raw `fetch()`

### Before (models.html:707-714)

```javascript
async function loadGlobalSpend() {
    const container = document.getElementById('spend-cards');
    
    try {
        // Fetch all logs to calculate real spend
        const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
        const logs = await logsResp.json();
```

### After (models.html — new shared fetcher + updated loadGlobalSpend)

```javascript
// === Shared Spend Log Fetcher (deduplicates all spend requests) ===
let _spendLogsPromise = null;
async function fetchSpendLogs(limit = 500) {
    if (_spendLogsPromise) return _spendLogsPromise;
    _spendLogsPromise = (async () => {
        const resp = await fetch(`${API_URL}/litellm/spend?limit=${limit}&lite=true`);
        const logs = await resp.json();
        window._allSpendLogs = Array.isArray(logs) ? logs : [];
        return window._allSpendLogs;
    })();
    try {
        return await _spendLogsPromise;
    } finally {
        // Allow re-fetch after 30s staleness
        setTimeout(() => { _spendLogsPromise = null; }, 30000);
    }
}

async function loadGlobalSpend() {
    const container = document.getElementById('spend-cards');
    
    try {
        const logs = await fetchSpendLogs();
```

### Before (models.html:934-949 — updateCharts fallback)

```javascript
async function updateCharts() {
    const periodDays = getPeriodDays();
    
    // Reuse logs already fetched by loadGlobalSpend (cached in window._allSpendLogs)
    let allLogs = [];
    try {
        const cached = window._allSpendLogs;
        if (Array.isArray(cached) && cached.length > 0) {
            allLogs = filterLogsByPeriod(cached, periodDays);
        } else {
            const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
            const logsData = await logsResp.json();
            allLogs = Array.isArray(logsData) ? filterLogsByPeriod(logsData, periodDays) : [];
        }
    } catch (err) {
        console.error('Failed to fetch spend logs:', err);
    }
```

### After (models.html — updateCharts uses shared fetcher)

```javascript
async function updateCharts() {
    const periodDays = getPeriodDays();
    
    let allLogs = [];
    try {
        const logs = await fetchSpendLogs();
        allLogs = filterLogsByPeriod(logs, periodDays);
    } catch (err) {
        if (window.ARIA_DEBUG) console.error('Failed to fetch spend logs:', err);
    }
```

### Before (models.html:848-860 — loadSpendLogs fallback)

```javascript
async function loadSpendLogs() {
    const tbody = document.getElementById('spend-logs-tbody');
    const limit = parseInt(document.getElementById('logs-limit')?.value || '25', 10);
    
    try {
        let logs;
        const cached = window._allSpendLogs;
        if (Array.isArray(cached) && cached.length > 0 && limit <= cached.length) {
            logs = cached.slice(0, limit);
        } else {
            const response = await fetch(`${API_URL}/litellm/spend?limit=${limit}`);
            logs = await response.json();
        }
```

### After (models.html — loadSpendLogs uses shared fetcher)

```javascript
async function loadSpendLogs() {
    const tbody = document.getElementById('spend-logs-tbody');
    const limit = parseInt(document.getElementById('logs-limit')?.value || '25', 10);
    
    try {
        const allLogs = await fetchSpendLogs();
        const logs = allLogs.slice(0, limit);
```

### Before (wallets.html:633-637)

```javascript
async function loadSpend() {
    try {
        // Fetch all spend logs to calculate real spend from tokens
        console.log('loadSpend: Fetching from', `${API_URL}/litellm/spend?limit=500&lite=true`);
        const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

### After (wallets.html — shared fetcher + updated loadSpend)

```javascript
// === Shared Spend Log Fetcher ===
let _spendLogsPromise = null;
async function fetchSpendLogs(limit = 500) {
    if (_spendLogsPromise) return _spendLogsPromise;
    _spendLogsPromise = (async () => {
        const resp = await fetch(`${API_URL}/litellm/spend?limit=${limit}&lite=true`);
        const logs = await resp.json();
        window._walletSpendLogs = Array.isArray(logs) ? logs : [];
        return window._walletSpendLogs;
    })();
    try { return await _spendLogsPromise; }
    finally { setTimeout(() => { _spendLogsPromise = null; }, 30000); }
}

async function loadSpend() {
    try {
        const spendLogs = await fetchSpendLogs();
```

### Before (wallets.html:695-702)

```javascript
    let spendLogs = window._walletSpendLogs;
    if (!spendLogs) {
        try {
            const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
            spendLogs = await logsResp.json();
        } catch (e) {
            spendLogs = [];
        }
    }
```

### After (wallets.html)

```javascript
    let spendLogs;
    try {
        spendLogs = await fetchSpendLogs();
    } catch (e) {
        spendLogs = [];
    }
```

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | No new npm/pip dependencies | ✅ Pure JS change |
| 2 | Jinja2 template compatibility | ✅ No template syntax changes |
| 3 | No breaking API contract changes | ✅ Same endpoint, fewer calls |
| 4 | Works with existing Docker setup | ✅ Frontend-only change |
| 5 | Backward compatible with LiteLLM proxy | ✅ Same query params |
| 6 | No changes to Python backend | ✅ Template JS only |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| S1-09 (remove console.log) | Soft | Apply S1-09 after this ticket to avoid merge conflicts in same files |
| LiteLLM proxy `/spend` endpoint | Runtime | Must remain available at `${API_URL}/litellm/spend` |

---

## Verification

```bash
# 1. Check no duplicate fetch calls remain in models.html
grep -c "fetch.*litellm/spend" src/web/templates/models.html
# Expected: 1 (only inside fetchSpendLogs)

# 2. Check no duplicate fetch calls remain in wallets.html
grep -c "fetch.*litellm/spend" src/web/templates/wallets.html
# Expected: 1 (only inside fetchSpendLogs)

# 3. Verify shared fetcher exists in models.html
grep -c "fetchSpendLogs" src/web/templates/models.html
# Expected: 4+ (definition + callers)

# 4. Verify shared fetcher exists in wallets.html
grep -c "fetchSpendLogs" src/web/templates/wallets.html
# Expected: 3+ (definition + callers)

# 5. Browser test — open Network tab, load /models page
# Expected: Only 1 request to /litellm/spend (not 2-3)

# 6. Browser test — open Network tab, load /wallets page
# Expected: Only 1 request to /litellm/spend (not 2)
```

---

## Prompt for Agent

```
Read src/web/templates/models.html and src/web/templates/wallets.html.

In models.html, there are 3 separate fetch() calls to /litellm/spend:
- loadGlobalSpend() at line 712
- updateCharts() fallback at line 944
- loadSpendLogs() fallback at line 859

In wallets.html, there are 2 separate fetch() calls:
- loadSpend() at line 637
- createBalanceChart() fallback at line 699

For each file, create a single shared `fetchSpendLogs()` function that:
1. Returns a cached promise if a fetch is in-flight (dedup concurrent calls)
2. Caches the result array on window (window._allSpendLogs for models, window._walletSpendLogs for wallets)
3. Expires the cache after 30 seconds to allow refresh

Then update all consumers (loadGlobalSpend, updateCharts, loadSpendLogs, loadSpend, createBalanceChart) to call fetchSpendLogs() instead of raw fetch().

Remove the individual fetch() calls and cache-check logic from each consumer. Keep error handling in each consumer for their own UI updates.

Verify with: grep -c "fetch.*litellm/spend" on each file — should be exactly 1 per file.
```
