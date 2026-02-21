# LiteLLM Performance & Frontend Hang Issues

**Date:** 2026-02-11  
**Severity:** Medium (Performance Degradation)  
**Status:** Identified, Needs Implementation  
**Reporter:** Aria Blue ⚡️

---

## Problem Summary

The Aria web dashboard appears "half down" when accessing LiteLLM-related pages (Models, Wallets, Operations). The root cause is **massive JSON responses** from `/litellm/spend/logs` causing browser timeouts and API gateway hangs.

---

## Symptoms

| Page | Behavior | Root Cause |
|------|----------|------------|
| `/models` | Hangs/Timeouts | Fetching 500+ spend logs with full tracebacks |
| `/wallets` | Hangs/Timeouts | Same - large spend log payload |
| `/operations` | Partial load | Global spend endpoint works, logs don't |
| API Health | Shows healthy | LiteLLM proxy is actually fine |

---

## Root Cause Analysis

### 1. Spend Log Payload Size

The `/spend/logs` endpoint returns **complete request metadata** including:
- Full error tracebacks (can be 50+ lines per failed request)
- Complete request/response objects
- Detailed token usage breakdowns
- Model mapping information
- Cost breakdowns with margin calculations

**Example Size:**
- 50 log entries ≈ 500KB-1MB JSON
- 500 log entries ≈ 5-10MB JSON
- Current frontend requests: `?limit=500`

### 2. Frontend Fetch Timeout

```javascript
// Current implementation (models.html, wallets.html)
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);
```

Problems:
- No client-side timeout handling
- No pagination (offset/limit)
- No response size limiting
- Synchronous blocking of UI

### 3. API Gateway Timeout

The `aria-api` router has a 30s timeout:
```python
async with httpx.AsyncClient(timeout=30.0) as client:
    resp = await client.get(f"{_litellm_base()}/spend/logs", headers=_auth_headers())
```

But the frontend fetch may timeout earlier, or the JSON parsing may hang.

---

## Impact Assessment

| Metric | Current | Target |
|--------|---------|--------|
| Page Load Time | 30s+ (timeout) | <3s |
| JSON Payload | 5-10MB | <500KB |
| User Experience | Broken | Smooth |
| API Calls per Page Load | 1 massive | Multiple small |

---

## Proposed Solutions

### Solution A: Server-Side Pagination (Recommended)

**File:** `src/api/routers/litellm.py`

```python
@router.get("/litellm/spend")
async def api_litellm_spend(
    limit: int = 20, 
    offset: int = 0,  # NEW
    lite: bool = False
):
    """
    Returns paginated spend logs.
    
    Args:
        limit: Max entries per page (default: 20, max: 100)
        offset: Skip N entries for pagination
        lite: If True, returns only essential fields
    """
    # Implementation with offset support
```

**Frontend Changes:**
```javascript
// Implement infinite scroll or pagination
let offset = 0;
const limit = 50;

async function loadMoreLogs() {
    const resp = await fetch(`${API_URL}/litellm/spend?limit=${limit}&offset=${offset}&lite=true`);
    const data = await resp.json();
    offset += limit;
    return data;
}
```

### Solution B: Lite Mode by Default

**Current:** `lite=true` is optional  
**Proposed:** `lite=true` is default, full data requires `?full=true`

**Lite Mode Fields Only:**
```json
{
  "request_id": "...",
  "model": "qwen3-next-free",
  "status": "success|failure",
  "total_tokens": 1234,
  "spend": 0.0,
  "startTime": "2026-02-11T...",
  "error_code": "429"  // only if failed
}
```

### Solution C: Streaming/Chunked Response

For real-time log viewing, implement Server-Sent Events (SSE) or WebSocket streaming instead of bulk JSON.

### Solution D: Client-Side Caching

Cache spend logs in browser localStorage with TTL:
```javascript
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
```

---

## Quick Fix (Immediate)

**File:** `src/web/templates/models.html`, `wallets.html`, `operations.html`

Change:
```javascript
// FROM:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=500&lite=true`);

// TO:
const logsResp = await fetch(`${API_URL}/litellm/spend?limit=50&lite=true`);
```

This reduces payload by 10x and should restore functionality immediately.

---

## Additional Findings

### 1. Rate Limiting Errors (Non-Critical)

Spend logs show repeated 429 errors from OpenRouter free models:
```
Rate limit exceeded: limit_rpm/qwen/qwen3-next-80b-a3b-instruct-2509
High demand for qwen/qwen3-next-80b-a3b-instruct:free on OpenRouter - limited to 8 requests per minute
```

**Recommendation:** Implement client-side rate limiting or use fallback models more aggressively.

### 2. MLX Local Model Failures

`qwen3-mlx` (local MLX model) shows connection errors:
```
Connection error.. Received Model Group=qwen3-mlx
```

**Cause:** MLX server on `host.docker.internal:8080` not running or misconfigured.

**Fix:** 
```bash
# Start MLX server on host
mlx_server --model mlx-community/Qwen3-4B-Instruct-2507-4bit --port 8080
```

### 3. Cron Job Delivery Errors (FIXED)

**Issue:** Cron jobs showed `"cron delivery target is missing"` errors  
**Cause:** Isolated sessions can't announce to `channel: "last"`  
**Fix:** Changed `delivery: announce` → `delivery: none` for routine jobs

**Affected Jobs:**
- `work_cycle` (every 15 min)
- `memory_sync` (every 15 min)  
- `hourly_goal_check` (every hour)
- `hourly_health_check` (every hour)

---

## Implementation Checklist

- [ ] **Immediate:** Reduce `limit=500` → `limit=50` in frontend templates
- [ ] **Short-term:** Add `offset` parameter to `/litellm/spend` endpoint
- [ ] **Medium-term:** Implement frontend pagination/infinite scroll
- [ ] **Medium-term:** Make `lite=true` the default mode
- [ ] **Long-term:** Add server-side response compression (gzip)
- [ ] **Long-term:** Implement caching layer for spend logs (Redis)

---

## Files to Modify

| File | Change Type | Priority |
|------|-------------|----------|
| `src/web/templates/models.html` | Reduce limit | P0 |
| `src/web/templates/wallets.html` | Reduce limit | P0 |
| `src/web/templates/operations.html` | Reduce limit | P0 |
| `src/api/routers/litellm.py` | Add pagination | P1 |
| `src/web/static/js/pricing.js` | Add caching | P2 |

---

## Testing Plan

1. **Load Test:** Verify page loads in <3s with 50 log limit
2. **Pagination Test:** Verify offset/limit works correctly
3. **Error Handling:** Test graceful degradation when LiteLLM is down
4. **Mobile Test:** Verify performance on slower connections

---

## Related Issues

- Cron job noise (fixed in commit `0b6aa70`)
- MLX local model connectivity
- OpenRouter rate limiting

---

## References

- LiteLLM Docs: https://docs.litellm.ai/docs/proxy/spend_tracking
- FastAPI Pagination: https://fastapi.tiangolo.com/tutorial/dependencies/
- Original Investigation: 2026-02-11 by Aria Blue

---

*Last Updated: 2026-02-11 08:13 UTC*  
*Next Review: After implementation of Solution A*
