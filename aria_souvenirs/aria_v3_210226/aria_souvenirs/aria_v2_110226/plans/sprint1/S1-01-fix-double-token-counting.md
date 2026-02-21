# S1-01: Fix Double Token Counting in Usage by Model Chart

**Sprint:** 1 — Financial Data Integrity  
**Priority:** 🔴 HIGH  
**Estimate:** 1 point  
**Status:** TODO  

---

## Problem

Token counts are **triple-counted** in two places in `src/web/templates/models.html`.

At **line 1106**, the "Usage by Model" horizontal bar chart calculates:

```javascript
// src/web/templates/models.html:1106
const tokens = (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
```

Since LiteLLM sets `total_tokens = prompt_tokens + completion_tokens`, this sums to **3× the real count**.

The same bug exists at **line 727** in `loadGlobalSpend()`:

```javascript
// src/web/templates/models.html:727
totalTokens += (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
```

Meanwhile, a **correct** implementation already exists at **line 957** in the "Tokens by Provider" doughnut chart:

```javascript
// src/web/templates/models.html:957
const tokens = log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
```

The two buggy lines inflate token metrics by 3× compared to the correct pattern 7 lines away.

---

## Root Cause

Copy-paste error. The original formula was likely meant to use `||` fallback logic (prefer `total_tokens`, fall back to sum) but was written with `+` instead, adding all three fields together.

---

## Fix

### Before (line 727):
```javascript
totalTokens += (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
```

### After (line 727):
```javascript
totalTokens += log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
```

### Before (line 1106):
```javascript
const tokens = (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
```

### After (line 1106):
```javascript
const tokens = log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
```

Both lines adopt the same pattern already used at line 957.

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 1 — `src/web/templates/models.html` |
| **Lines changed** | 2 (L727, L1106) |
| **Breaking changes** | None |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert the two lines |

---

## Dependencies

- None. Self-contained fix in a single template file.

---

## Verification

```bash
# 1. Verify both buggy lines exist before the fix
grep -n "prompt_tokens.*completion_tokens.*total_tokens" src/web/templates/models.html
# Expected output (before fix):
#   727:                totalTokens += (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
#   1106:            const tokens = (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);

# 2. After fix, verify both lines use the fallback pattern
grep -n "total_tokens ||" src/web/templates/models.html
# Expected output (after fix):
#   727:                totalTokens += log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
#   957:        const tokens = log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));
#   1106:            const tokens = log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));

# 3. Ensure no triple-count pattern remains
grep -c "prompt_tokens.*+.*completion_tokens.*+.*total_tokens" src/web/templates/models.html
# Expected: 0
```

### Manual Verification
1. Open Models page → check "Usage by Model" bar chart values
2. Compare token totals in spend cards vs the Tokens by Provider chart (should now match)
3. If a model logged 100 prompt + 50 completion → chart should show 150, not 300

---

## Prompt for Agent

```
Fix the double/triple token counting bug in src/web/templates/models.html.

Two lines incorrectly sum prompt_tokens + completion_tokens + total_tokens (which triple-counts since total_tokens already equals prompt + completion).

Change line 727 from:
  totalTokens += (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
to:
  totalTokens += log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));

Change line 1106 from:
  const tokens = (log.prompt_tokens || 0) + (log.completion_tokens || 0) + (log.total_tokens || 0);
to:
  const tokens = log.total_tokens || ((log.prompt_tokens || 0) + (log.completion_tokens || 0));

This matches the correct pattern already used at line 957.
Do NOT change any other lines. Only modify these two lines.
```
