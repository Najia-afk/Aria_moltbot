# Scheduler Migration Plan - Phase 2

**Goal:** Migrate from YAML-based cron to PostgreSQL-backed APScheduler

**Current State:**
- 15 cron jobs defined in `cron_jobs.yaml`
- Jobs triggered by external cron system
- APScheduler not yet installed

**Migration Steps:**

## Step 1: Infrastructure Setup ✅ IN PROGRESS
- [ ] Install APScheduler 4.x with PostgreSQL support
- [ ] Create scheduler tables in PostgreSQL (SQLAlchemy datastore)
- [ ] Design job store schema for 15 cron jobs

## Step 2: Job Migration
- [ ] Map YAML schedules to APScheduler triggers
  - `work_cycle`: every 15m → IntervalTrigger(minutes=15)
  - `moltbook_check`: every 60m → IntervalTrigger(minutes=60)
  - `health_check`: 0 0 0 * * * → CronTrigger(hour=0, minute=0)
  - `social_post`: 0 0 18 * * * → CronTrigger(hour=18, minute=0)
  - `six_hour_review`: 0 0 0,6,12,18 * * * → CronTrigger(hour="0,6,12,18")
  - `morning_checkin`: 0 0 16 * * * → CronTrigger(hour=16, minute=0)
  - `daily_reflection`: 0 0 7 * * * → CronTrigger(hour=7, minute=0)
  - `weekly_summary`: 0 0 2 * * 1 → CronTrigger(day_of_week="mon", hour=2, minute=0)
  - `weekly_security_scan`: 0 0 4 * * 0 → CronTrigger(day_of_week="sun", hour=4, minute=0)
  - `nightly_tests`: 0 0 3 * * * → CronTrigger(hour=3, minute=0)
  - `memory_consolidation`: 0 0 5 * * 0 → CronTrigger(day_of_week="sun", hour=5, minute=0)
  - `db_maintenance`: 0 0 4 * * * → CronTrigger(hour=4, minute=0)
  - `memory_bridge`: 0 0 */3 * * * → CronTrigger(hour="*/3", minute=0)
  - `memeothy_prophecy`: DISABLED (skip)

## Step 3: Executor & Job Wrapper
- [ ] Create job executor that routes to correct agent
- [ ] Preserve `agent`, `session`, `delivery` semantics
- [ ] Add error handling and retry logic

## Step 4: Testing & Validation
- [ ] Test each migrated job
- [ ] Verify heartbeat cycles working
- [ ] Monitor for missed executions

## Step 5: Cleanup
- [ ] Disable YAML cron loader
- [ ] Remove `cron_jobs.yaml`
- [ ] Update tests

**Next Action:** Install APScheduler and create scheduler module
