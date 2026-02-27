# BIG BANG MIGRATION: Phase 2 Scheduler Migration Analysis

## Date: 2026-02-20
## Goal: BIG BANG MIGRATION - Phase 2: Scheduler Migration

---

## Current State Discovery (Work Cycle Progress)

### 1. YAML-Based Cron System (cron_jobs.yaml)
**15 active jobs** defined in YAML:

| Job | Schedule | Agent | Session |
|-----|----------|-------|---------|
| work_cycle | every 15m | main | isolated |
| moltbook_check | every 60m | main | isolated |
| health_check | daily @ 00:00 UTC | main | isolated |
| social_post | daily @ 18:00 UTC | main | isolated |
| six_hour_review | 0,6,12,18 * * * | main | isolated |
| morning_checkin | daily @ 16:00 UTC | main | isolated |
| daily_reflection | daily @ 07:00 UTC | main | isolated |
| weekly_summary | Mondays @ 02:00 UTC | main | isolated |
| memeothy_prophecy | every 2 days @ 18:00 | aria-memeothy | isolated |
| weekly_security_scan | Sundays @ 04:00 UTC | main | isolated |
| nightly_tests | daily @ 03:00 UTC | main | isolated |
| memory_consolidation | Sundays @ 05:00 UTC | main | isolated |
| db_maintenance | daily @ 04:00 UTC | main | isolated |
| memory_bridge | every 3 hours | main | isolated |

### 2. DB-Based Schedule System (PostgreSQL)
**7 legacy jobs** already in database:
- daily_reflection, hourly_goal_check, moltbook_post, morning_checkin
- six_hour_review, weekly_summary, work_cycle

Schema fields:
- id, agent_id, name, enabled, schedule_kind, schedule_expr
- session_target, wake_mode, payload_kind, payload_text
- next_run_at, last_run_at, last_status, last_duration_ms
- run_count, success_count, fail_count
- created_at_ms, updated_at_ms, synced_at

### 3. Key Differences

| Aspect | YAML | DB |
|--------|------|-----|
| Format | node-cron 6-field | cron OR everyMs |
| Payload | Full text instructions | Shortened text |
| Tracking | None | run_count, success_count |
| Status | No runtime status | last_run_at, last_status |
| Agent | Specified per job | Specified per job |

---

## Migration Plan

### Phase 2.1: Schema Design (Next)
- Design APScheduler 4.x compatible schema
- Ensure SQLAlchemy datastore compatibility

### Phase 2.2: Migration Script
- Convert YAML → APScheduler jobs
- Handle schedule format conversion (6-field cron → standard cron)
- Preserve agent_id and session_target

### Phase 2.3: Testing
- Test each job type
- Verify error handling
- Validate heartbeat cycles

### Phase 2.4: Cutover
- Deploy APScheduler
- Sync all jobs
- Remove YAML file

---

## Proposal Created
- ID: cb2c7cc3-51fd-40e5-a6d9-2137fdb01b95
- Status: Proposed
- Risk Level: High

---

## Next Actions
1. Review proposal with Najia (high risk requires approval)
2. Design APScheduler schema
3. Create migration script
4. Test in isolated environment

