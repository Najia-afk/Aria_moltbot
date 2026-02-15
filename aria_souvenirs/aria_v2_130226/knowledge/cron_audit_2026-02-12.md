# Cron Job Audit — 2026-02-12

## Summary
| Metric | Before (2026-02-11) | After (2026-02-12) | Change |
|--------|---------------------|---------------------|--------|
| Total jobs | 13 | 11 | -2 |
| Daily runs (approx) | 316 | 117 | -63% |
| Est. daily cost | $4.45 | $1.85 | -58% |
| Est. monthly cost | $133 | $55 | -58% |

## Job Inventory
| Job | Schedule | Runs/Day | Est. Tokens/Run | Est. Tokens/Day | Status |
|-----|----------|----------|-----------------|-----------------|--------|
| work_cycle | every 15m | 96 | 150 | 14,400 | Active |
| health_check | 0,6,12,18 UTC | 4 | 100 | 400 | Active |
| social_post | 18 UTC | 1 | 500 | 500 | Active (draft-first) |
| six_hour_review | 0,6,12,18 UTC | 4 | 1000 | 4,000 | Active |
| morning_checkin | 16 UTC | 1 | 500 | 500 | Active |
| daily_reflection | 7 UTC | 1 | 500 | 500 | Active |
| weekly_summary | Mon 2 UTC | 0.14 | 2000 | 280 | Active |
| memeothy_prophecy | every 2 days 18 UTC | 0.5 | 500 | 250 | Active |
| weekly_security_scan | Sun 4 UTC | 0.14 | 500 | 70 | Active |
| nightly_tests | 3 UTC | 1 | 120 | 120 | Active |
| memory_consolidation | Sun 5 UTC | 0.14 | 500 | 70 | Active |
| db_maintenance | 4 UTC | 1 | 100 | 100 | Active |

## Removed / Consolidated
- `memory_sync` merged into `work_cycle` (S2-01)
- `hourly_health_check` renamed and reduced to `health_check` every 6h (S2-02)
- `exploration_pulse` not present in active cron definition (S2-02)

## Cost Tracking
- Added `cron_execution` logging instruction to key jobs (`work_cycle`, `six_hour_review`, `nightly_tests`).
- Added API query support: `GET /api/activities?action=cron_execution`.
- Added aggregate endpoint: `GET /api/activities/cron-summary?days=7`.

## Cooldown Hardening
- Added API-level cooldown enforcement for `action='six_hour_review'` in `POST /activities`.
- Duplicate requests within 5h now return:
  - `status: cooldown_active`
  - `created: false`
  - `next_allowed` timestamp.

## Remaining Optimization Opportunities
1. Move `social_post` to every 2 days if draft queue remains >10 files/week.
2. Lower `work_cycle` frequency to every 20m during low-activity periods.
3. Add per-job real token collection from LiteLLM logs for exact, not estimated, cost.
4. Route `weekly_security_scan` to low-cost/free model profile when available.
