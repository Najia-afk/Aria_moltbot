# S7-04: Dashboard Activity Timeline Server-Side Aggregation

## Summary
The activity timeline chart only shows the current day because the frontend fetches `activities?limit=500` and does client-side date bucketing. With 2,561+ activities (most from today), the 500-row cap means older days get zero counts. Fix: add a server-side `/activities/timeline` aggregation endpoint that returns daily counts directly.

## Priority / Points
- **Priority**: P1-High
- **Story Points**: 5
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] New API endpoint `GET /activities/timeline?days=7` returns daily activity counts
- [ ] Dashboard chart fetches from `/activities/timeline` instead of client-side bucketing
- [ ] Chart shows activity for all 7 days (not just today)
- [ ] Response is lightweight (~200 bytes vs 500+ activity records)

## Technical Details

### Current broken flow (dashboard.html ~line 385):
```javascript
const raw = await fetch(`${API_URL}/activities?limit=500`);
// Client-side bucketing over 500 rows — only today fills up
```

### New server-side endpoint:
```python
@router.get("/activities/timeline")
async def activity_timeline(days: int = 7, db = Depends(get_db)):
    """Daily activity counts for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date(Activity.created_at).label("day"),
            func.count(Activity.id).label("count")
        )
        .where(Activity.created_at >= cutoff)
        .group_by(func.date(Activity.created_at))
        .order_by(func.date(Activity.created_at))
    )
    return [{"day": str(r.day), "count": r.count} for r in result.all()]
```

### Dashboard update:
```javascript
const resp = await fetch(`${API_URL}/activities/timeline?days=7`);
const timeline = await resp.json();
// Use timeline directly for chart labels + data
```

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/activities.py | Add `/activities/timeline` endpoint |
| src/web/templates/dashboard.html | Fetch from /activities/timeline, remove client-side bucketing |

## Verification
```bash
curl -s 'http://localhost:8000/activities/timeline?days=7' | python3 -m json.tool
# Should return: [{"day": "2026-02-05", "count": 12}, {"day": "2026-02-06", "count": 45}, ...]
```

## Dependencies
- None (independent)
