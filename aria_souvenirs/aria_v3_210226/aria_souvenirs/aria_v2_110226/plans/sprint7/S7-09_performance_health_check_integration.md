# S7-09: Performance Page Health Check Integration

## Summary
The Performance page only shows manual performance reviews, not automated health checks from the heartbeat system. The heartbeat generates health data regularly, but it goes to `heartbeat_log` table — the Performance page only queries `performance_reviews`. Fix: integrate heartbeat health data into the performance dashboard.

## Priority / Points
- **Priority**: P2-Medium
- **Story Points**: 3
- **Sprint**: 7 — Dashboard Data Fixes

## Acceptance Criteria
- [ ] Performance page shows recent heartbeat health metrics
- [ ] Health check history visible (last 24h of heartbeat data)
- [ ] System uptime / response time trends displayed
- [ ] Performance reviews still shown separately

## Technical Details
- `heartbeat_log` table contains periodic health check results
- `performance_reviews` table is for manual reviews (empty or sparse)
- Performance page should merge both sources or show heartbeat data as primary

### New endpoint or modification:
```python
@router.get("/performance/health-history")
async def health_history(hours: int = 24, db = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(HeartbeatLog)
        .where(HeartbeatLog.created_at >= cutoff)
        .order_by(HeartbeatLog.created_at.desc())
        .limit(100)
    )
    return [row_to_dict(r) for r in result.scalars().all()]
```

## Files to Modify
| File | Change |
|------|--------|
| src/api/routers/performance.py | Add health history endpoint using heartbeat_log |
| src/web/templates/performance.html | Show heartbeat health data + manual reviews |

## Dependencies
- None (independent)
