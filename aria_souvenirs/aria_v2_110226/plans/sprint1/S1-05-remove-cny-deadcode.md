# S1-05: Remove Hardcoded CNY_TO_USD + Dead Code

**Sprint:** 1 — Code Quality  
**Priority:** 🟡 MEDIUM  
**Estimate:** 2 points  
**Status:** TODO  

---

## Problem

A hardcoded exchange rate constant sits in the codebase, no longer needed, and could produce wrong results if triggered.

### `src/web/static/js/pricing.js:206`

```javascript
// src/web/static/js/pricing.js:206
const CNY_TO_USD = 0.137;
```

This constant was used when the Kimi API returned balances in CNY. The Kimi international API (`api.moonshot.ai`) now returns USD directly. The constant is **declared but unreferenced** in `pricing.js` itself.

### `src/web/templates/wallets.html:552`

However, `wallets.html` **does use it** at line 552:

```javascript
// src/web/templates/wallets.html:552
const availableUSD = currency === 'CNY' ? available * CNY_TO_USD : available;
```

This code path only triggers if `kimi.currency === 'CNY'`, which no longer happens with the international API. But if it *did* trigger (e.g., fallback to domestic API), it would use a stale exchange rate of `0.137` (actual rate fluctuates daily, currently ~0.137–0.140).

### `models.html` already handles Kimi correctly

In `src/web/templates/models.html:596-600`, Kimi balance is treated as already USD:

```javascript
// src/web/templates/models.html:596-597
// Kimi balance (already in USD)
if (balanceData.kimi) {
    const kimi = balanceData.kimi;
    if (kimi.status === 'ok') {
        const available = kimi.available || 0;
        totalUSD += available;  // No CNY conversion
```

So `models.html` already assumes USD, while `wallets.html` has a dead CNY branch — inconsistency.

---

## Root Cause

The Kimi API was switched from the domestic endpoint (CNY) to the international endpoint (USD) during the migration to `api.moonshot.ai`. The `CNY_TO_USD` constant and the conversion branch in `wallets.html` were not cleaned up.

---

## Fix

### 1. Remove from `src/web/static/js/pricing.js`

**Before (line 206):**
```javascript
const CNY_TO_USD = 0.137;
```

**After:**
```javascript
// (line removed entirely)
```

### 2. Remove CNY branch from `src/web/templates/wallets.html`

**Before (lines 550-553):**
```javascript
                const available = kimi.available || 0;
                const currency = kimi.currency || 'USD';
                const availableUSD = currency === 'CNY' ? available * CNY_TO_USD : available;
                totalUSD += availableUSD;
```

**After:**
```javascript
                const available = kimi.available || 0;
                totalUSD += available;
```

This matches the simpler pattern already used in `models.html:600-601`.

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 2 — `src/web/static/js/pricing.js`, `src/web/templates/wallets.html` |
| **Lines changed** | 1 deleted, 3 simplified to 2 |
| **Breaking changes** | None — CNY code path was dead (Kimi API returns USD) |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert both files to restore the constant and branch |

---

## Dependencies

- If **S1-04** (consolidate JS) lands first, the wallets.html `loadBalances` may already be refactored. In that case, ensure the shared `fetchBalances()` in `aria-common.js` does not include a CNY branch.
- Confirm Kimi API key is configured for the international endpoint (`api.moonshot.ai`), not the domestic one (`api.moonshot.cn`).

---

## Verification

```bash
# 1. Verify CNY_TO_USD is gone from pricing.js
grep -n "CNY_TO_USD" src/web/static/js/pricing.js
# Expected: 0 matches

# 2. Verify CNY_TO_USD is gone from wallets.html
grep -n "CNY_TO_USD" src/web/templates/wallets.html
# Expected: 0 matches

# 3. Verify no CNY_TO_USD anywhere in src/
grep -rn "CNY_TO_USD" src/
# Expected: 0 matches

# 4. Verify wallets.html still handles Kimi balance
grep -n "kimi.available" src/web/templates/wallets.html
# Expected: 1 match showing `const available = kimi.available || 0;`

# 5. Verify Kimi API returns USD
curl -s http://localhost:8000/providers/balances | python3 -c "import sys,json; d=json.load(sys.stdin); print('currency:', d.get('kimi',{}).get('currency','N/A'))"
# Expected: currency: USD
```

### Manual Verification
1. Open Wallets page → Kimi balance shows correctly in USD
2. No console errors about undefined `CNY_TO_USD`

---

## Prompt for Agent

```
Remove the dead CNY_TO_USD exchange rate constant and its usage.

1. In src/web/static/js/pricing.js, delete line 206:
   const CNY_TO_USD = 0.137;

2. In src/web/templates/wallets.html, simplify lines 550-553 from:
   const available = kimi.available || 0;
   const currency = kimi.currency || 'USD';
   const availableUSD = currency === 'CNY' ? available * CNY_TO_USD : available;
   totalUSD += availableUSD;
   to:
   const available = kimi.available || 0;
   totalUSD += available;

The Kimi international API (api.moonshot.ai) returns USD directly. The CNY conversion is dead code. Removing it matches the pattern already used in models.html:600-601.

Also remove any remaining references to CNY_TO_USD anywhere in src/.
```
