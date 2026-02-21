# S1-02: Fix Pricing Inconsistency (spend vs calculateLogCost)

**Sprint:** 1 — Financial Data Integrity  
**Priority:** 🔴 HIGH  
**Estimate:** 2 points  
**Status:** TODO  

---

## Problem

Cost calculations use **two different sources** on the same page, producing conflicting numbers.

In `src/web/templates/models.html`, the spend summary cards at **line 723** use the AriaModels pricing engine:

```javascript
// src/web/templates/models.html:723
const cost = calculateLogCost(log);
```

But the spend log **table** at **line 878** uses LiteLLM's raw `spend` field:

```javascript
// src/web/templates/models.html:878
const cost = log.spend || 0;
```

`calculateLogCost()` (defined in `src/web/static/js/pricing.js:207`) applies AriaModels pricing from `models.yaml`, while `log.spend` is LiteLLM's internal cost estimate. These frequently differ because:
- AriaModels pricing may include negotiated rates or custom tiers
- LiteLLM may not know about Kimi or local model pricing
- Rounding differences accumulate across hundreds of logs

The result: the summary card shows one total, but summing the table rows gives a different number.

---

## Root Cause

The spend log table was written before `calculateLogCost()` was available in `pricing.js`. It used the raw `log.spend` field as a shortcut. When the summary cards were later updated to use `calculateLogCost()`, the table was not updated to match.

---

## Fix

### Before (line 878):
```javascript
const cost = log.spend || 0;
```

### After (line 878):
```javascript
const cost = (typeof calculateLogCost === 'function') ? calculateLogCost(log) : (log.spend || 0);
```

This uses `calculateLogCost` when `pricing.js` is loaded (which it always is via `base.html`), with a safe fallback to `log.spend` if somehow unavailable.

### Additionally — update the token display on the same line (line 877) for consistency:

**Before (line 877):**
```javascript
const tokens = (log.prompt_tokens || log.promptTokens || 0) + (log.completion_tokens || log.completionTokens || 0);
```

This line is already correct (sums input + output only, no double-count), so it stays as-is. Only the cost line changes.

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 1 — `src/web/templates/models.html` |
| **Lines changed** | 1 (L878) |
| **Breaking changes** | None — fallback preserves old behavior if pricing.js fails |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert L878 to `log.spend \|\| 0` |

---

## Dependencies

- `src/web/static/js/pricing.js` must be loaded before the models template script runs (already guaranteed by `base.html` load order).
- `AriaModels.init()` must have been called (already done at `models.html:1229`).

---

## Verification

```bash
# 1. Verify the buggy line exists before fix
grep -n "log.spend || 0" src/web/templates/models.html
# Expected (before fix):
#   878:            const cost = log.spend || 0;

# 2. After fix, verify calculateLogCost is used in the table
grep -n "calculateLogCost" src/web/templates/models.html
# Expected (after fix):
#   582:// Pricing, calculateLogCost, formatNumber, formatMoney, getProvider, getProviderColor
#   723:                const cost = calculateLogCost(log);
#   878:            const cost = (typeof calculateLogCost === 'function') ? calculateLogCost(log) : (log.spend || 0);

# 3. Ensure no remaining bare "log.spend" usage for cost display
grep -n "log\.spend" src/web/templates/models.html
# Expected: 0 matches (or only in non-cost contexts)
```

### Manual Verification
1. Open Models page → note "Total Spend" in the summary card
2. Scroll to spend log table → manually sum the cost column for the displayed rows
3. Values should now be consistent (both computed via `calculateLogCost`)

---

## Prompt for Agent

```
Fix the pricing inconsistency in src/web/templates/models.html.

The spend log table at line 878 uses `log.spend || 0` (LiteLLM's raw spend), but the summary cards at line 723 use `calculateLogCost(log)` (AriaModels pricing engine). This causes the table totals to disagree with the summary.

Change line 878 from:
  const cost = log.spend || 0;
to:
  const cost = (typeof calculateLogCost === 'function') ? calculateLogCost(log) : (log.spend || 0);

This makes the table use the same pricing engine as the summary cards while providing a safe fallback.
Do NOT modify line 723 or any other lines. Only change line 878.
```
