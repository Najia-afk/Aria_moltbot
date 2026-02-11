# S1-09: Remove console.log from Production Templates

**Priority:** Low | **Estimate:** 1 pt | **Status:** TODO

---

## Problem

Production template files contain debug `console.log()` statements that leak internal state (URLs, data counts, timing info) to any user who opens browser DevTools.

### wallets.html — 4 debug console.log statements

| Line | Statement | Risk |
|------|-----------|------|
| `src/web/templates/wallets.html:636` | `console.log('loadSpend: Fetching from', \`${API_URL}/litellm/spend?limit=500&lite=true\`)` | Leaks internal API URL |
| `src/web/templates/wallets.html:639` | `console.log('loadSpend: Got', Array.isArray(spendLogs) ? spendLogs.length : 0, 'logs')` | Leaks data volume |
| `src/web/templates/wallets.html:673` | `console.log('loadSpend: Total spend calculated:', totalSpend)` | Leaks financial data |
| `src/web/templates/wallets.html:937` | `console.log('💰 Wallet auto-refresh enabled (every 60s)')` | Minor info leak |

### wallets.html — console.error (keep these)

| Line | Statement | Action |
|------|-----------|--------|
| `src/web/templates/wallets.html:628` | `console.error('Error loading balances:', error)` | ✅ KEEP — error logging is appropriate |
| `src/web/templates/wallets.html:684` | `console.error('Error loading spend:', error)` | ✅ KEEP — error logging is appropriate |

### models.html — console.error only (no debug logs)

| Line | Statement | Action |
|------|-----------|--------|
| `src/web/templates/models.html:695` | `console.error('Error loading balances:', error)` | ✅ KEEP |
| `src/web/templates/models.html:765` | `console.error('Error loading spend:', error)` | ✅ KEEP |
| `src/web/templates/models.html:793` | `console.error('Error loading models:', error)` | ✅ KEEP |
| `src/web/templates/models.html:897` | `console.error('Error loading spend logs:', error)` | ✅ KEEP |
| `src/web/templates/models.html:949` | `console.error('Failed to fetch spend logs:', err)` | ✅ KEEP |
| `src/web/templates/models.html:1175` | `console.error('Failed to load global spend:', err)` | ✅ KEEP |

---

## Root Cause

Debug `console.log()` statements were added during development and never removed before deploying. No debug-flag gating mechanism exists.

---

## Fix

1. **Remove** all `console.log()` debug statements from `wallets.html`
2. **Keep** all `console.error()` statements (these are legitimate error reports)
3. **Add** a `window.ARIA_DEBUG` flag so developers can re-enable logging when needed

### Before (wallets.html:635-639)

```javascript
        // Fetch all spend logs to calculate real spend from tokens
        console.log('loadSpend: Fetching from', `${API_URL}/litellm/spend?limit=500&lite=true`);
        const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
        const spendLogs = await logsResp.json();
        console.log('loadSpend: Got', Array.isArray(spendLogs) ? spendLogs.length : 0, 'logs');
```

### After (wallets.html)

```javascript
        // Fetch all spend logs to calculate real spend from tokens
        const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
        const spendLogs = await logsResp.json();
```

### Before (wallets.html:673)

```javascript
        console.log('loadSpend: Total spend calculated:', totalSpend);
```

### After

```javascript
        // (debug log removed — use window.ARIA_DEBUG to re-enable)
```

### Before (wallets.html:935-937)

```javascript
    console.log('💰 Wallet auto-refresh enabled (every 60s)');
});
```

### After

```javascript
    if (window.ARIA_DEBUG) console.log('💰 Wallet auto-refresh enabled (every 60s)');
});
```

### Add debug flag (wallets.html — top of script block, after API_URL definition)

```javascript
// Debug mode: set window.ARIA_DEBUG = true in console to enable verbose logging
window.ARIA_DEBUG = window.ARIA_DEBUG || false;
```

---

## Constraints

| # | Constraint | Status |
|---|-----------|--------|
| 1 | No new dependencies | ✅ Pure JS removal |
| 2 | Keep console.error() for real errors | ✅ Only removing console.log() |
| 3 | No functional behavior changes | ✅ Logging only |
| 4 | Jinja2 template compatibility | ✅ No template syntax affected |
| 5 | Works with existing Docker setup | ✅ Frontend-only |
| 6 | Developers can still debug | ✅ window.ARIA_DEBUG flag added |

---

## Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| S1-08 (deduplicate fetches) | Soft | Some console.log lines may move/change in S1-08. Apply S1-09 after S1-08 to avoid conflicts. |

---

## Verification

```bash
# 1. No console.log in wallets.html (excluding ARIA_DEBUG-gated ones)
grep -n "console\.log" src/web/templates/wallets.html | grep -v "ARIA_DEBUG"
# Expected: (no output — all bare console.log removed)

# 2. console.error still present (not removed)
grep -c "console\.error" src/web/templates/wallets.html
# Expected: 2

# 3. ARIA_DEBUG flag exists
grep -c "ARIA_DEBUG" src/web/templates/wallets.html
# Expected: 2+ (definition + usage)

# 4. No console.log in models.html (should already have none)
grep -n "console\.log" src/web/templates/models.html
# Expected: (no output)

# 5. console.error preserved in models.html
grep -c "console\.error" src/web/templates/models.html
# Expected: 6
```

---

## Prompt for Agent

```
Read src/web/templates/wallets.html.

There are 4 console.log() debug statements that must be removed from production:
- Line 636: console.log('loadSpend: Fetching from', ...)
- Line 639: console.log('loadSpend: Got', ...)  
- Line 673: console.log('loadSpend: Total spend calculated:', ...)
- Line 937: console.log('💰 Wallet auto-refresh enabled (every 60s)')

Do NOT remove console.error() statements — those are legitimate error handlers at lines 628 and 684.

Actions:
1. Delete the console.log() at lines 636, 639, and 673 entirely
2. Gate line 937 behind: if (window.ARIA_DEBUG) console.log(...)
3. Near the top of the <script> block (after API_URL is defined), add:
   window.ARIA_DEBUG = window.ARIA_DEBUG || false;

Also check src/web/templates/models.html — it currently only has console.error() which is fine, but verify no console.log() has been added.

Verify: grep -n "console\.log" src/web/templates/wallets.html | grep -v "ARIA_DEBUG" should return nothing.
```
