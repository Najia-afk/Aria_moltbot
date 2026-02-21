# S1-03: Fix LiteLLM Spend Endpoint Pagination

**Sprint:** 1 — Performance  
**Priority:** 🔴 HIGH  
**Estimate:** 5 points  
**Status:** TODO  

---

## Problem

The frontend fetches **all spend logs at once** with `limit=500`, causing 5–10 MB JSON responses and timeouts.

### Backend — `src/api/routers/litellm.py:42-63`

The spend endpoint fetches **all logs** from LiteLLM, then slices in memory:

```python
# src/api/routers/litellm.py:42-48
@router.get("/litellm/spend")
async def api_litellm_spend(limit: int = 20, lite: bool = False):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_litellm_base()}/spend/logs", headers=_auth_headers())
            logs = resp.json()
            if isinstance(logs, list):
                logs = logs[:limit]
```

There is **no `offset` parameter** — no pagination support at all. The upstream LiteLLM call at line 45 fetches the entire log table every time.

### Frontend — `src/web/templates/models.html:712`

```javascript
// src/web/templates/models.html:712
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

Same at **line 944**:
```javascript
// src/web/templates/models.html:944
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

### Frontend — `src/web/templates/wallets.html:637`

```javascript
// src/web/templates/wallets.html:637
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

Same at **line 699**:
```javascript
// src/web/templates/wallets.html:699
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

Four separate 500-row fetches across two pages, each pulling the full log table server-side.

---

## Root Cause

The LiteLLM proxy endpoint was written as a simple pass-through with no pagination design. The `limit` parameter only truncates *after* fetching everything. No `offset` parameter exists.

---

## Fix

### 1. Backend: Add offset parameter — `src/api/routers/litellm.py`

**Before (lines 42-48):**
```python
@router.get("/litellm/spend")
async def api_litellm_spend(limit: int = 20, lite: bool = False):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_litellm_base()}/spend/logs", headers=_auth_headers())
            logs = resp.json()
            if isinstance(logs, list):
                logs = logs[:limit]
```

**After:**
```python
@router.get("/litellm/spend")
async def api_litellm_spend(limit: int = 50, offset: int = 0, lite: bool = False):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{_litellm_base()}/spend/logs", headers=_auth_headers())
            logs = resp.json()
            if isinstance(logs, list):
                total = len(logs)
                logs = logs[offset:offset + limit]
```

Also update the return to include pagination metadata. After the `if lite:` block and the plain return, wrap results:

**Before (line 63, plain return):**
```python
            return logs
```

**After:**
```python
            return {"logs": logs, "total": total, "offset": offset, "limit": limit}
```

And wrap the lite return similarly:

**Before (lines 50-62):**
```python
                if lite:
                    return [
                        {
                            "model": log.get("model", ""),
                            ...
                        }
                        for log in logs
                    ]
```

**After:**
```python
                if lite:
                    lite_logs = [
                        {
                            "model": log.get("model", ""),
                            ...
                        }
                        for log in logs
                    ]
                    return {"logs": lite_logs, "total": total, "offset": offset, "limit": limit}
```

### 2. Frontend: Reduce default limit from 500 to 50

**models.html line 712:**
```javascript
// Before:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
// After:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=50&lite=true`);
```

**models.html line 944:**
```javascript
// Before:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
// After:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=50&lite=true`);
```

**wallets.html line 637:**
```javascript
// Before:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
// After:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=50&lite=true`);
```

**wallets.html line 699:**
```javascript
// Before:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
// After:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=50&lite=true`);
```

### 3. Frontend: Update callers for new response shape

Since the API now returns `{ logs: [...], total, offset, limit }` instead of a bare array, update all callers:

```javascript
// Before:
const logsData = await logsResp.json();
allLogs = Array.isArray(logsData) ? ... : [];

// After:
const logsData = await logsResp.json();
const logsArray = logsData.logs || (Array.isArray(logsData) ? logsData : []);
```

This maintains backward compatibility with old API responses.

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 3 — `src/api/routers/litellm.py`, `src/web/templates/models.html`, `src/web/templates/wallets.html` |
| **Lines changed** | ~25 |
| **Breaking changes** | API response shape changes from array to `{logs, total, offset, limit}` — frontends updated in same PR |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Revert all 3 files; API falls back to bare array, frontends fall back to 500 |

---

## Dependencies

- Must update frontend and backend in the same deployment to avoid shape mismatch.
- `src/api/routers/model_usage.py:193` also calls `_fetch_litellm_spend_logs(limit=5000)` — out of scope for this ticket but should be a follow-up.

---

## Verification

```bash
# 1. Verify backend has offset parameter
grep -n "offset" src/api/routers/litellm.py
# Expected: offset parameter on the spend endpoint function signature

# 2. Verify no limit=500 remains in frontend templates
grep -rn "limit=500" src/web/templates/
# Expected: 0 matches

# 3. Default limit is now 50
grep -n "limit=50" src/web/templates/models.html src/web/templates/wallets.html
# Expected: matches showing limit=50

# 4. API returns pagination metadata
curl -s "http://localhost:8000/litellm/spend?limit=5&offset=0&lite=true" | python3 -c "import sys,json; d=json.load(sys.stdin); print('total:', d.get('total'), 'offset:', d.get('offset'), 'limit:', d.get('limit'), 'logs:', len(d.get('logs',[])))"
# Expected: total: <N> offset: 0 limit: 5 logs: 5
```

### Manual Verification
1. Open Models page → network tab → verify spend request is `?limit=50` not 500
2. Response size should be <500 KB instead of 5–10 MB
3. Page load time should improve noticeably

---

## Prompt for Agent

```
Add pagination support to the LiteLLM spend endpoint and reduce frontend fetch sizes.

1. In src/api/routers/litellm.py:
   - Add `offset: int = 0` parameter to `api_litellm_spend` (line 42)
   - Change default `limit` from 20 to 50
   - Slice logs as `logs[offset:offset + limit]` instead of `logs[:limit]`
   - Return `{"logs": <data>, "total": <len>, "offset": <offset>, "limit": <limit>}` instead of bare array
   - Apply the same wrapper to both the lite and full return paths

2. In src/web/templates/models.html:
   - Line 712: change `limit=500` to `limit=50`
   - Line 944: change `limit=500` to `limit=50`
   - Update JSON parsing to handle `data.logs || data` for backward compat

3. In src/web/templates/wallets.html:
   - Line 637: change `limit=500` to `limit=50`
   - Line 699: change `limit=500` to `limit=50`
   - Update JSON parsing to handle `data.logs || data` for backward compat

Do NOT change the upstream LiteLLM proxy call at line 45 (that's a separate optimization).
```
