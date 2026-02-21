# S2-01: Merge work_cycle + memory_sync Cron Jobs
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
Two cron jobs both run every 15 minutes with overlapping concerns:
1. `work_cycle` (every 15m) — Check goals, pick highest priority, make progress, log activity
2. `memory_sync` (every 15m) — Sync state to `aria_memories/memory/` files for session start context

Running both means **192 cron invocations/day** instead of 96. Each invocation costs tokens (session setup, HEARTBEAT.md read, api_client calls). Merging into a single job that does work_cycle + memory_sync as final step reduces token waste by ~50% on these two jobs.

## Root Cause
The two jobs were created independently — `work_cycle` for task execution, `memory_sync` for state persistence. But `memory_sync` is naturally the final step of any work cycle (persist what you just did). Separate scheduling wastes tokens on redundant session setup.

## Fix

**File:** `aria_mind/cron_jobs.yaml`

**Merge approach:** Add memory sync instruction to end of `work_cycle` text, remove standalone `memory_sync` job.

**BEFORE (work_cycle):**
```yaml
  - name: work_cycle
    every: "15m"
    text: "Read HEARTBEAT.md work_cycle section. Check goals, pick highest priority, make progress, log activity. Use api_client for all data ops."
    agent: main
    session: isolated
    delivery: none
```

**AFTER (merged):**
```yaml
  - name: work_cycle
    every: "15m"
    text: "Read HEARTBEAT.md work_cycle section. Check goals, pick highest priority, make progress, log activity. Use api_client for all data ops. After completing work, sync current state to aria_memories/memory/ files using working_memory.sync_to_files() — write context.json with active goals, recent activities, and system health."
    agent: main
    session: isolated
    delivery: none
```

**REMOVE (memory_sync):**
```yaml
  # REMOVED: Merged into work_cycle
  # - name: memory_sync
  #   every: "15m"
  #   text: "Sync current state to aria_memories/memory/ files..."
  #   agent: main
  #   session: isolated
  #   delivery: none
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Cron config only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Cron injected at container startup — verify after restart |
| 5 | aria_memories writable | ✅ | memory_sync writes to aria_memories/memory/ |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone optimization.

## Verification
```bash
# 1. Check cron_jobs.yaml only has work_cycle, not memory_sync:
grep -n "memory_sync\|work_cycle" aria_mind/cron_jobs.yaml
# EXPECTED: work_cycle present, memory_sync commented out or removed

# 2. Count active cron jobs:
grep -c "^  - name:" aria_mind/cron_jobs.yaml
# EXPECTED: one fewer than before (was ~12, now ~11)

# 3. Verify work_cycle text includes sync instruction:
grep -A5 "work_cycle" aria_mind/cron_jobs.yaml | grep "sync\|memory"
# EXPECTED: sync instruction present in work_cycle text
```

## Prompt for Agent
```
Merge the work_cycle and memory_sync cron jobs into a single job.

**Files to read:**
- aria_mind/cron_jobs.yaml (full file)
- aria_mind/HEARTBEAT.md (search for work_cycle section)

**Constraints:** Constraint 5 (aria_memories writable path) — memory sync writes to aria_memories/.

**Steps:**
1. Read cron_jobs.yaml
2. Add memory sync instruction to end of work_cycle text
3. Comment out or remove the standalone memory_sync job
4. Verify cron_jobs.yaml syntax is valid YAML
5. Run verification commands
```
