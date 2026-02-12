# S2-08: Full Cron Audit & Documentation
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P0 | **Points:** 3 | **Phase:** 2

## Problem
After Sprint 2 optimizations (merge, patches, tracking), we need a comprehensive audit documenting the final state of all cron jobs with:
- Actual schedule vs. documented schedule
- Estimated daily token cost per job
- Expected behavior vs. actual behavior
- Any remaining optimization opportunities

## Root Cause
Cron jobs are the #1 source of token waste in Aria. Without a clear audit trail, optimizations drift and costs creep back up.

## Fix
Create a comprehensive cron audit document.

**File:** `aria_memories/knowledge/cron_audit_2026-02-12.md`

**Template:**
```markdown
# Cron Job Audit — 2026-02-12

## Summary
| Metric | Before (2026-02-11) | After (2026-02-12) | Change |
|--------|---------------------|---------------------|--------|
| Total jobs | 13 | ~11 | -2 |
| Daily runs | 316 | ~100 | -68% |
| Est. daily cost | $4.45 | $1.28 | -71% |
| Est. monthly cost | $133 | $38 | -71% |

## Job Inventory

| Job | Schedule | Runs/Day | Est. Tokens | Est. Cost/Day | Model | Status |
|-----|----------|----------|-------------|---------------|-------|--------|
| work_cycle | every 15m | 96 | ~200/run | $X | main/kimi | Active |
| health_check | 0,6,12,18 UTC | 4 | ~100/run | $X | main/kimi | Active |
| social_post | 18 UTC | 1 | ~500 | $X | main→aria-talk | Active |
| six_hour_review | 0,6,12,18 UTC | 4 | ~1000/run | $X | main→analyst | Active |
| morning_checkin | 16 UTC | 1 | ~500 | $X | main/kimi | Active |
| daily_reflection | 7 UTC | 1 | ~500 | $X | main/kimi | Active |
| weekly_summary | Mon 2 UTC | 0.14 | ~2000 | $X | main/kimi | Active |
| memeothy_prophecy | every 2 days 18 UTC | 0.5 | ~500 | $X | aria-memeothy | Active |
| weekly_security_scan | Sun 4 UTC | 0.14 | ~500 | $X | main/kimi | Active |
| nightly_tests | 3 UTC | 1 | ~200 | $X | main/kimi | Active |
| memory_consolidation | Sun 5 UTC | 0.14 | ~500 | $X | main/kimi | Active |
| db_maintenance | 4 UTC | 1 | ~100 | $X | main/kimi | Active |

## Removed Jobs
- exploration_pulse — removed (was $2.60/day, 100% error rate)
- memory_sync — merged into work_cycle
- hourly_goal_check — disabled (was creating noise goals)
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Documentation only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ❌ | No code changes |
| 5 | aria_memories writable | ✅ | Writing to aria_memories/knowledge/ |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
S2-01 through S2-07 should be complete — this documents the final state.

## Verification
```bash
# 1. Audit document exists:
cat aria_memories/knowledge/cron_audit_2026-02-12.md | head -5
# EXPECTED: markdown header

# 2. Count active jobs in YAML:
grep -c "^  - name:" aria_mind/cron_jobs.yaml
# EXPECTED: matches count in audit document

# 3. No exploration_pulse:
grep "exploration_pulse" aria_mind/cron_jobs.yaml
# EXPECTED: no output (or commented out)

# 4. YAML valid:
python3 -c "import yaml; yaml.safe_load(open('aria_mind/cron_jobs.yaml')); print('Valid')"
# EXPECTED: Valid
```

## Prompt for Agent
```
Create a comprehensive cron job audit document.

**Files to read:**
- aria_mind/cron_jobs.yaml (full — current state)
- aria_memories/bugs/cron_token_waste_critical_analysis.md (historical costs)
- aria_memories/bugs/cron_patches_applied_2026-02-12.md (patches applied)

**Constraints:** Constraint 5 (write to aria_memories/).

**Steps:**
1. Read cron_jobs.yaml and count all active jobs
2. Calculate estimated daily runs per job
3. Estimate token cost per job (based on task complexity)
4. Write audit document to aria_memories/knowledge/cron_audit_2026-02-12.md
5. Include before/after comparison
6. List remaining optimization opportunities
```
