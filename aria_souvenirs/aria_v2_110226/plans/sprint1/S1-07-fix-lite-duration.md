# S1-07: Fix Spend Log Duration for Lite Logs

**Sprint:** 1 — Data Integrity  
**Priority:** 🟡 MEDIUM  
**Estimate:** 2 points  
**Status:** TODO  

---

## Problem

The spend log table always shows `0.00s` for duration because the `lite=true` endpoint strips `endTime` from responses.

### Frontend — `src/web/templates/models.html:880-883`

```javascript
// src/web/templates/models.html:880-883
// Calculate duration from startTime and endTime
let duration = 0;
if (log.startTime && log.endTime) {
    duration = (new Date(log.endTime) - new Date(log.startTime)) / 1000;
}
```

The duration calculation requires both `startTime` and `endTime`. But `endTime` is never present in lite logs.

### Backend — `src/api/routers/litellm.py:50-62`

The lite response **only includes `startTime`**, not `endTime`:

```python
# src/api/routers/litellm.py:50-62
if lite:
    return [
        {
            "model": log.get("model", ""),
            "prompt_tokens": log.get("prompt_tokens", 0),
            "completion_tokens": log.get("completion_tokens", 0),
            "total_tokens": log.get("total_tokens", 0),
            "spend": log.get("spend", 0),
            "startTime": log.get("startTime"),      # ✓ included
            "status": log.get("status", "success"),
            # endTime NOT included                    # ✗ missing
        }
        for log in logs
    ]
```

So `log.endTime` is always `undefined` on the frontend, making the `if` block never execute, and duration stays at `0`.

### Impact

The spend log table's Duration column is useless — every row shows `0.00s`. Users cannot see how long API calls took.

---

## Root Cause

The `lite` response format was designed to minimize payload size and omitted `endTime` as non-essential. The frontend duration calculation was written assuming full log objects, not lite ones.

---

## Fix

### Option A: Include `endTime` in lite response (preferred — minimal payload increase)

**Before (`src/api/routers/litellm.py:50-62`):**
```python
if lite:
    return [
        {
            "model": log.get("model", ""),
            "prompt_tokens": log.get("prompt_tokens", 0),
            "completion_tokens": log.get("completion_tokens", 0),
            "total_tokens": log.get("total_tokens", 0),
            "spend": log.get("spend", 0),
            "startTime": log.get("startTime"),
            "status": log.get("status", "success"),
        }
        for log in logs
    ]
```

**After:**
```python
if lite:
    return [
        {
            "model": log.get("model", ""),
            "prompt_tokens": log.get("prompt_tokens", 0),
            "completion_tokens": log.get("completion_tokens", 0),
            "total_tokens": log.get("total_tokens", 0),
            "spend": log.get("spend", 0),
            "startTime": log.get("startTime"),
            "endTime": log.get("endTime"),
            "status": log.get("status", "success"),
        }
        for log in logs
    ]
```

Adding `endTime` is a single ISO timestamp string (~24 bytes per log). For 50 logs, that's ~1.2 KB — negligible.

### Option B: Calculate duration server-side (alternative)

If payload size is critical, compute duration in the backend:

```python
"duration_s": round(
    (parse_dt(log.get("endTime")) - parse_dt(log.get("startTime"))).total_seconds(), 2
) if log.get("endTime") and log.get("startTime") else None,
```

And update the frontend to use `log.duration_s` directly. This is more complex and couples frontend to a new field.

**Recommendation: Option A** — simpler, no frontend changes needed beyond what already exists.

---

## Constraints

| Constraint | Value |
|-----------|-------|
| **Files modified** | 1 — `src/api/routers/litellm.py` |
| **Lines changed** | 1 (add `endTime` field to lite response dict) |
| **Breaking changes** | None — additive field |
| **Migration needed** | No |
| **Feature flag** | No |
| **Rollback plan** | Remove the `endTime` line from the lite dict |

---

## Dependencies

- The frontend duration code at `models.html:880-883` already handles `endTime` correctly — no frontend changes needed.
- If **S1-03** (pagination) changes the response shape, the `endTime` field should be included in the updated lite response.

---

## Verification

```bash
# 1. Verify endTime is in the lite response dict
grep -A 10 "if lite:" src/api/routers/litellm.py | grep "endTime"
# Expected: "endTime": log.get("endTime"),

# 2. Verify the API returns endTime in lite mode
curl -s "http://localhost:8000/litellm/spend?limit=1&lite=true" | python3 -c "
import sys, json
data = json.load(sys.stdin)
logs = data if isinstance(data, list) else data.get('logs', [])
if logs:
    log = logs[0]
    print('startTime:', log.get('startTime'))
    print('endTime:', log.get('endTime'))
    print('has_endTime:', 'endTime' in log)
else:
    print('No logs')
"
# Expected:
# startTime: 2026-02-11T...
# endTime: 2026-02-11T...
# has_endTime: True

# 3. Frontend duration code is already correct (no changes needed)
grep -n "log.startTime && log.endTime" src/web/templates/models.html
# Expected: line 882 (unchanged)
```

### Manual Verification
1. Open Models page → scroll to Spend Logs table
2. Duration column should now show actual values (e.g., `1.23s`, `0.45s`) instead of `0.00s`
3. Verify durations are reasonable (most LLM calls take 0.5–30s)

---

## Prompt for Agent

```
Fix the spend log duration display by including endTime in the lite API response.

In src/api/routers/litellm.py, in the lite response dict (lines 50-62), add endTime:

Before the "status" line, add:
    "endTime": log.get("endTime"),

The full lite dict should be:
{
    "model": log.get("model", ""),
    "prompt_tokens": log.get("prompt_tokens", 0),
    "completion_tokens": log.get("completion_tokens", 0),
    "total_tokens": log.get("total_tokens", 0),
    "spend": log.get("spend", 0),
    "startTime": log.get("startTime"),
    "endTime": log.get("endTime"),
    "status": log.get("status", "success"),
}

No frontend changes needed — models.html:880-883 already calculates duration from startTime and endTime when both are present.
```
