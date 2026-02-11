# Cron Job Improvements Log

**Date:** 2026-02-11  
**Type:** Bug Fix + Configuration  
**Status:** Completed ✅  
**Commit:** `0b6aa70`

---

## Issues Fixed

### 1. "Cron delivery target is missing" Errors

**Problem:** All isolated cron jobs were failing with:
```
"lastError": "cron delivery target is missing"
```

**Root Cause:** Isolated sessions cannot announce to `channel: "last"` because they have no persistent delivery target after completion.

**Solution:** Changed delivery mode from `announce` to `none` for routine jobs.

### 2. Duplicate-Looking Heartbeat Messages

**Problem:** User saw "the same heartbeat several times in logs"

**Root Cause:** 4 jobs running simultaneously with overlapping schedules:
- `work_cycle` (every 15 min)
- `memory_sync` (every 15 min)
- `hourly_goal_check` (every hour)
- `hourly_health_check` (every hour)

All were announcing to the same channel, creating noise.

**Solution:** Same fix - changed to `delivery: none` so jobs run silently and log to database only.

---

## Changes Made

### Updated Jobs (cron_jobs.yaml)

| Job | Before | After |
|-----|--------|-------|
| work_cycle | `delivery: announce` | `delivery: none` |
| memory_sync | `delivery: announce` | `delivery: none` |
| hourly_goal_check | `delivery: announce` | `delivery: none` |
| hourly_health_check | `delivery: announce` | `delivery: none` |

### New Job Added

- `hourly_health_check` was in live cron but missing from `cron_jobs.yaml` - now persisted.

### Jobs Remaining with Announce

These still announce because they're user-facing:
- `six_hour_review` (analysis summary)
- `daily_reflection` (day summary)
- `weekly_summary` (week report)
- `social_post` (Moltbook posts)

---

## Verification

```bash
# Check cron status
openclaw cron list

# All updated jobs now show:
"delivery": {
  "mode": "none"
}
```

---

## Result

- ✅ No more "delivery target is missing" errors
- ✅ Routine jobs run silently (database logging only)
- ✅ User sees only important announcements (social posts, daily/weekly summaries)
- ✅ Logs are cleaner and more actionable

---

## Notes for Future

- Use `delivery: none` for routine/maintenance tasks
- Use `delivery: announce` for user-facing summaries only
- Consider adding `delivery: error` mode (announce only on failure)

---

*Logged by: Aria Blue ⚡️*
