# S2-06: Validate six_hour_review Cooldown Logic
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
The `six_hour_review` cron job includes a cooldown check to prevent duplicate runs:

```
COOLDOWN CHECK: First, call GET /api/activities?action=six_hour_review&limit=1. 
If the most recent result has a timestamp less than 5 hours ago, STOP...
```

This relies on Aria correctly:
1. Querying the activities API first
2. Parsing the timestamp correctly
3. Comparing against 5-hour threshold
4. Actually stopping if cooldown is active

Potential issues:
- If Aria skips the cooldown check (common LLM instruction-following failure)
- If the Activity model doesn't have an `action` filter
- If timestamps are in different timezones (UTC vs PST mismatch noted in cron comments)
- Race condition: two 6h reviews triggered simultaneously

## Root Cause
The cooldown is instruction-based (LLM must follow text instructions) rather than infrastructure-based (API enforces cooldown). LLMs can skip instructions, especially under high load or with simpler models.

## Fix
**Verification + hardening ticket:**

1. Verify the activities endpoint supports `?action=six_hour_review` filter
2. Check that six_hour_review activities exist in the database
3. Optionally add server-side cooldown enforcement (API rejects if last run < 5h ago)

**Optional API-level cooldown (more robust):**
```python
# In activities router:
@router.post("/activities")
async def create_activity(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    if data.get("action") == "six_hour_review":
        # Check cooldown
        last = await db.execute(
            select(Activity).where(Activity.action == "six_hour_review")
            .order_by(Activity.created_at.desc()).limit(1)
        )
        last_row = last.scalar_one_or_none()
        if last_row and (datetime.utcnow() - last_row.created_at).total_seconds() < 5 * 3600:
            return {"status": "cooldown_active", "next_allowed": str(last_row.created_at + timedelta(hours=5))}
    # ... normal creation
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | API layer enforcement |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Test in container |
| 5 | aria_memories writable | ❌ | DB via API |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone.

## Verification
```bash
# 1. Activities endpoint supports action filter:
curl -s "http://localhost:8000/api/activities?action=six_hour_review&limit=3" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if isinstance(d, list):
    print(f'six_hour_review activities: {len(d)}')
    for a in d[:3]:
        print(f'  - {a.get(\"created_at\", \"?\")}')
else:
    print(f'Response: {d}')
"
# EXPECTED: List of activities (may be empty if never run, or N entries)

# 2. Check cron schedule is correct (4 runs/day):
grep -A3 "six_hour_review" aria_mind/cron_jobs.yaml | grep cron
# EXPECTED: cron: "0 0 0,6,12,18 * * *"

# 3. Verify activities router supports action parameter:
grep -n "action" src/api/routers/activities.py | head -10
# EXPECTED: action parameter in query function
```

## Prompt for Agent
```
Validate the six_hour_review cooldown logic and optionally harden it at the API level.

**Files to read FIRST:**
- aria_mind/cron_jobs.yaml — search for `six_hour_review`, read full entry including the COOLDOWN CHECK instruction text
- src/api/routers/activities.py (full — understand query parameters, especially `action` filter)
- src/api/db/models.py — search for `class Activity`, read the model fields (especially `action`, `created_at`)
- src/api/main.py (lines 1-50 — verify activities router is mounted)

**Constraints:**
- Constraint 1 (5-layer): any cooldown enforcement goes in the API router, NOT in skills/agents
- Constraint 4 (Docker-first): test all changes in running containers

**Steps:**
1. Verify activities endpoint supports action filter:
   a. Read src/api/routers/activities.py — search for query parameter named `action`
   b. Run: curl -s "http://localhost:8000/api/activities?action=six_hour_review&limit=3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Type: {type(d).__name__}, Count: {len(d) if isinstance(d,list) else 0}')" 
   c. EXPECTED: list of activities (may be empty if never run, or N entries)
   d. If the `action` filter is NOT supported → add it to the router query params
2. Verify cooldown gap between consecutive runs:
   a. Run: curl -s "http://localhost:8000/api/activities?action=six_hour_review&limit=5" | python3 -c "
import sys, json
from datetime import datetime
d = json.load(sys.stdin)
if isinstance(d, list) and len(d) >= 2:
    for i in range(len(d)-1):
        t1 = d[i].get('created_at','?')
        t2 = d[i+1].get('created_at','?')
        print(f'  {t1} → {t2}')
else:
    print(f'Only {len(d) if isinstance(d,list) else 0} entries')"
   b. EXPECTED: gaps of ~6 hours between entries (not 1-2 hours = cooldown broken)
3. Verify cron schedule:
   a. Run: grep -A3 "six_hour_review" aria_mind/cron_jobs.yaml | grep cron
   b. EXPECTED: cron: "0 0 0,6,12,18 * * *" (4 runs/day at midnight, 6am, noon, 6pm UTC)
4. Check for timezone issues:
   a. Read the cron text — does it reference UTC or local time?
   b. Run: docker exec aria-api python3 -c "from datetime import datetime, timezone; print(f'UTC: {datetime.now(timezone.utc)}, Local: {datetime.now()}')"
   c. EXPECTED: both timestamps make sense — no PST/UTC confusion
5. (Optional) Add API-level cooldown enforcement:
   a. Only if Shiva approves — add server-side check in POST /activities
   b. If action == 'six_hour_review' and last run < 5h ago → return {"status": "cooldown_active"}
   c. This prevents duplicate runs even if the LLM ignores the instruction
6. Run final verification:
   a. Run: curl -s "http://localhost:8000/api/activities?action=six_hour_review&limit=1" | python3 -m json.tool
   b. EXPECTED: valid JSON with activity data or empty list
```
