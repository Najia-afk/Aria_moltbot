# S1-04: Consolidate Duplicate JS (models + wallets)

**Sprint:** 1 — Code Quality  
**Priority:** 🟡 MEDIUM  
**Estimate:** 5 points  
**Status:** TODO  

---

## Problem

`models.html` and `wallets.html` contain ~400 lines of **near-identical JavaScript** for balance fetching, spend calculation, and chart rendering.

### loadBalances duplication

**`src/web/templates/models.html:586-703`** (118 lines):

```javascript
// models.html:586
async function loadBalances() {
    const grid = document.getElementById('balances-grid');
    try {
        const response = await fetch(`${API_URL}/providers/balances`);
        balanceData = await response.json();
        let html = '';
        let totalUSD = 0;
        // Kimi balance (already in USD)
        if (balanceData.kimi) { ... }
        // OpenRouter balance
        if (balanceData.openrouter) { ... }
        // Local models
        if (balanceData.local) { ... }
        grid.innerHTML = html || '...';
        document.getElementById('stat-balance').textContent = '$' + totalUSD.toFixed(2);
    } catch (error) { ... }
}
```

**`src/web/templates/wallets.html:539-632`** (94 lines):

```javascript
// wallets.html:539
async function loadBalances() {
    try {
        const response = await fetch(`${API_URL}/providers/balances`);
        const data = await response.json();
        let totalUSD = 0;
        // Kimi — international API
        if (data.kimi) { ... }
        // OpenRouter
        if (data.openrouter) { ... }
        // Local
        if (data.local) { ... }
        document.getElementById('total-balance').textContent = '$' + totalUSD.toFixed(2);
    } catch (error) { ... }
}
```

Both fetch `/providers/balances`, iterate over Kimi/OpenRouter/Local, calculate `totalUSD`, and render. The only differences are the DOM element IDs and HTML structure.

### loadSpend duplication

**`src/web/templates/models.html:707-775`** — `loadGlobalSpend()` fetches spend logs, calculates totals, renders spend cards.

**`src/web/templates/wallets.html:633-690`** — `loadSpend()` fetches the same spend logs, calculates the same totals, renders wallet spend cards.

Both fetch `${API_URL}/litellm/spend?limit=500&lite=true`, iterate logs with `calculateLogCost(log)`, and sum costs.

### The existing shared file

`src/web/static/js/pricing.js` (224 lines) already provides `calculateLogCost`, `formatMoney`, `formatNumber`, `getProvider`, etc. — but balance/spend fetching is not yet extracted there.

---

## Root Cause

`wallets.html` was developed after `models.html` by copying the balance/spend JavaScript. No shared library extraction was performed.

---

## Fix

### 1. Create `src/web/static/js/aria-common.js` with shared functions:

```javascript
/**
 * Shared balance + spend fetching for Aria Blue pages.
 * Depends on pricing.js (AriaModels, calculateLogCost, formatMoney).
 */

/**
 * Fetch provider balances and return { data, totalUSD }.
 */
async function fetchBalances(apiUrl) {
    const response = await fetch(`${apiUrl}/providers/balances`);
    const data = await response.json();
    let totalUSD = 0;

    if (data.kimi?.status === 'ok') {
        totalUSD += data.kimi.available || 0;
    }
    if (data.openrouter?.status === 'ok') {
        const limit = data.openrouter.limit;
        const usage = data.openrouter.usage || 0;
        if (limit !== null && limit !== undefined) {
            const remaining = limit - usage;
            if (remaining > 0) totalUSD += remaining;
        }
    }

    return { data, totalUSD };
}

/**
 * Fetch spend logs and calculate totals.
 * Returns { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount }.
 */
async function fetchSpendSummary(apiUrl, limit = 50) {
    const resp = await fetch(`${apiUrl}/litellm/spend?limit=${limit}&lite=true`);
    const raw = await resp.json();
    const logs = raw.logs || (Array.isArray(raw) ? raw : []);

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const weekStart = new Date(now); weekStart.setDate(now.getDate() - 7);
    const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

    let totalSpend = 0, todaySpend = 0, weekSpend = 0, monthSpend = 0;
    let inputTokens = 0, outputTokens = 0, totalTokens = 0;

    logs.forEach(log => {
        const cost = calculateLogCost(log);
        const logDate = new Date(log.startTime || log.created_at);
        totalSpend += cost;
        inputTokens += log.prompt_tokens || 0;
        outputTokens += log.completion_tokens || 0;
        totalTokens += log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
        if (logDate >= todayStart) todaySpend += cost;
        if (logDate >= weekStart) weekSpend += cost;
        if (logDate >= monthStart) monthSpend += cost;
    });

    return { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount: logs.length };
}
```

### 2. Update `models.html` and `wallets.html`

Add script tag in both templates (after pricing.js):
```html
<script src="/static/js/aria-common.js"></script>
```

Replace inline `loadBalances` / `loadGlobalSpend` / `loadSpend` to call the shared functions and only handle page-specific DOM updates.

**Example — models.html `loadGlobalSpend` simplified:**
```javascript
async function loadGlobalSpend() {
    const container = document.getElementById('spend-cards');
    try {
        const summary = await fetchSpendSummary(API_URL, 50);
        window._allSpendLogs = summary.logs;
        spendData = summary;
        container.innerHTML = `...${formatMoney(summary.totalSpend)}...`;
    } catch (error) { ... }
}
```

**Example — wallets.html `loadSpend` simplified:**
```javascript
async function loadSpend() {
    try {
        const summary = await fetchSpendSummary(API_URL, 50);
        window._walletSpendLogs = summary.logs;
        document.getElementById('spend-total').textContent = formatMoney(summary.totalSpend);
        document.getElementById('spend-today').textContent = formatMoney(summary.todaySpend);
        ...
    } catch (error) { ... }
}
```

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 3 — new `aria-common.js`, modified `models.html`, modified `wallets.html` |
| **Lines changed** | ~200 removed from templates, ~70 added to `aria-common.js` |
| **Breaking changes** | None — same external behavior |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert all 3 files; inline code is restored |

---

## Dependencies

- **S1-03** (pagination) should land first so `aria-common.js` uses the new paginated API shape from the start.
- `pricing.js` must load before `aria-common.js` (both loaded in `base.html`).

---

## Verification

```bash
# 1. New shared file exists
test -f src/web/static/js/aria-common.js && echo "OK" || echo "MISSING"
# Expected: OK

# 2. Shared functions are defined
grep -c "function fetchBalances\|function fetchSpendSummary" src/web/static/js/aria-common.js
# Expected: 2

# 3. Templates import the shared file
grep -c "aria-common.js" src/web/templates/models.html src/web/templates/wallets.html
# Expected: 1 match per file

# 4. Inline duplicate fetch logic is removed
grep -c "fetch.*providers/balances" src/web/templates/models.html
# Expected: 0 (now in aria-common.js)

grep -c "fetch.*providers/balances" src/web/templates/wallets.html
# Expected: 0 (now in aria-common.js)

# 5. Both pages still function
curl -s http://localhost:8000/models | grep -c "balances-grid"
# Expected: 1
curl -s http://localhost:8000/wallets | grep -c "total-balance"
# Expected: 1
```

### Manual Verification
1. Open Models page → balances grid loads, spend cards populate, charts render
2. Open Wallets page → wallet balances load, spend totals populate, chart renders
3. Both pages show identical "total balance" amounts

---

## Prompt for Agent

```
Extract shared balance/spend fetching logic from models.html and wallets.html into a new file.

1. Create src/web/static/js/aria-common.js with two exported functions:
   - `fetchBalances(apiUrl)` → fetches /providers/balances, returns { data, totalUSD }
   - `fetchSpendSummary(apiUrl, limit)` → fetches /litellm/spend, calculates totals using calculateLogCost, returns { logs, totalSpend, todaySpend, weekSpend, monthSpend, inputTokens, outputTokens, totalTokens, requestCount }

2. In src/web/templates/models.html:
   - Add <script src="/static/js/aria-common.js"></script> after the pricing.js script tag
   - Refactor loadBalances() (lines 586-703) to call fetchBalances() for data, keep only DOM rendering
   - Refactor loadGlobalSpend() (lines 707-775) to call fetchSpendSummary(), keep only DOM rendering

3. In src/web/templates/wallets.html:
   - Add <script src="/static/js/aria-common.js"></script> after the pricing.js script tag
   - Refactor loadBalances() (lines 539-632) to call fetchBalances() for data, keep only DOM rendering
   - Refactor loadSpend() (lines 633-690) to call fetchSpendSummary(), keep only DOM rendering

Ensure both pages still render identically. The shared functions must depend only on pricing.js globals (calculateLogCost, formatMoney, etc.).
```
