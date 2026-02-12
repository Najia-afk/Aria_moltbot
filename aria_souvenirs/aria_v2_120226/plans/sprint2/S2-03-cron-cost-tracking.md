# S2-03: Add Cron Cost Tracking to Activities
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Aria's cron token waste analysis (documented in `aria_memories/bugs/cron_token_waste_critical_analysis.md`) identified ~$133/month in unnecessary spending. However, there's no way to **measure actual spend per cron job** because:
1. No per-job token tracking exists
2. LiteLLM logs model usage globally, not per-cron-job
3. We can't verify optimization impact without measurement

## Root Cause
The cron system dispatches jobs through OpenClaw, which creates sessions. LiteLLM logs token usage per session, but there's no correlation between cron job name and token spend. We need to bridge this gap.

## Fix

**Approach:** After each cron job completes, log an activity with the cron job name and estimated token usage from the session. This leverages existing infrastructure (activities API) without new tables.

**Implementation:**
Each cron job's text instruction should include a final step to log its execution cost. We add this to the cron job text pattern:

**Example addition to cron text:**
```
After completing this task, log execution via api_client: POST /activities with action='cron_execution', details={'job': 'work_cycle', 'estimated_tokens': <your_in+out_tokens>}.
```

**Alternatively (better):** Create a `/api/activities/cron-summary` endpoint that aggregates cron execution activities by job name over the last 24h/7d/30d.

**File:** `src/api/routers/activities.py`

**ADD new endpoint:**
```python
@router.get("/activities/cron-summary")
async def get_cron_summary(
    days: int = 7,
    db: AsyncSession = Depends(get_db)
):
    """Aggregate cron job execution count and estimated tokens over N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(
            Activity.action,
            func.count().label("executions"),
            func.avg(Activity.metadata["estimated_tokens"].as_float()).label("avg_tokens")
        )
        .where(Activity.action == "cron_execution")
        .where(Activity.created_at >= cutoff)
        .group_by(Activity.action)
    )
    return [dict(r._mapping) for r in result.all()]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | New endpoint in API layer (Layer 3) |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Test in container |
| 5 | aria_memories writable | ❌ | DB writes via API |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S2-01 (merge crons) should complete first so we track the post-merge job list.

## Verification
```bash
# 1. Endpoint exists:
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/activities?action=cron_execution&limit=5"
# EXPECTED: 200

# 2. Create a test cron activity:
curl -s -X POST http://localhost:8000/api/activities -H "Content-Type: application/json" -d '{"action":"cron_execution","details":{"job":"work_cycle","estimated_tokens":150}}'
# EXPECTED: 200/201

# 3. Query cron activities:
curl -s "http://localhost:8000/api/activities?action=cron_execution&limit=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Cron activities: {len(d) if isinstance(d,list) else d}')"
# EXPECTED: Cron activities: N (at least 1)
```

## Prompt for Agent
```
Add cron job cost tracking via the activities API.

**Files to read:**
- src/api/routers/activities.py (full — understand activity schema)
- src/api/db/models.py (search for Activity model)
- aria_mind/cron_jobs.yaml (understand job inventory)
- aria_memories/bugs/cron_token_waste_critical_analysis.md (cost data)

**Constraints:** 5-layer architecture, Docker-first.

**Steps:**
1. Read activities router to understand how activities are created/queried
2. Add instruction to 2-3 key cron jobs to log cron_execution activity after completion
3. Optionally add a cron-summary aggregation endpoint
4. Test by creating a cron_execution activity and querying it
5. Run verification commands
```
