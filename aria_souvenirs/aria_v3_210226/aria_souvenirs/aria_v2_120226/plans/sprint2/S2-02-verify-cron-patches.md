# S2-02: Verify Cron Patch Persistence After Container Restart
**Epic:** Sprint 2 — Cron & Token Optimization | **Priority:** P0 | **Points:** 2 | **Phase:** 2

## Problem
On 2026-02-12, three critical cron patches were applied (documented in `aria_memories/bugs/cron_patches_applied_2026-02-12.md`):
1. `exploration_pulse` — reduced from every 15m to every 2h (saving ~$2.60/day)
2. `db_maintenance` — delivery mode fixed to `none` + `bestEffort: true`
3. `hourly_health_check` — reduced from hourly to every 6 hours

These patches were applied as runtime changes. If the `cron_jobs.yaml` file wasn't updated, they'll be lost on next container restart because `openclaw-entrypoint.sh` re-injects crons from the YAML file at startup.

## Root Cause
Cron patches applied via `cron.update()` or `cron.remove()` modify the running OpenClaw state but not the YAML definition file. The YAML file is the definitive source — container restarts re-inject from YAML.

**Current cron_jobs.yaml status:**
- `exploration_pulse` is **NOT in** cron_jobs.yaml (was removed or never added as standalone)
- `hourly_health_check` still has `cron: "0 0 * * * *"` (hourly) — **NOT patched to 6h**
- `db_maintenance` already has `delivery: silent` — partially correct

## Fix

**File:** `aria_mind/cron_jobs.yaml`

1. Change `hourly_health_check` from hourly to every 6 hours:

**BEFORE:**
```yaml
  - name: hourly_health_check
    cron: "0 0 * * * *"
```

**AFTER:**
```yaml
  - name: health_check
    cron: "0 0 0,6,12,18 * * *"
```

2. Verify `exploration_pulse` is NOT in the YAML (should not re-appear).

3. Verify `db_maintenance` has correct delivery mode.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ❌ | Config file only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml SSOT | ❌ | No model references |
| 4 | Docker-first | ✅ | Crons injected at container startup |
| 5 | aria_memories writable | ❌ | Config only |
| 6 | No soul modification | ❌ | Not touching soul |

## Dependencies
None — standalone patch verification.

## Verification
```bash
# 1. No exploration_pulse in YAML:
grep -n "exploration_pulse" aria_mind/cron_jobs.yaml
# EXPECTED: no output (not present)

# 2. Health check is every 6 hours:
grep -A2 "health_check" aria_mind/cron_jobs.yaml | grep cron
# EXPECTED: cron: "0 0 0,6,12,18 * * *" (4 runs/day, not 24)

# 3. db_maintenance has correct delivery:
grep -A5 "db_maintenance" aria_mind/cron_jobs.yaml | grep delivery
# EXPECTED: delivery: silent (or none)

# 4. YAML is valid:
python3 -c "import yaml; yaml.safe_load(open('aria_mind/cron_jobs.yaml')); print('YAML valid')"
# EXPECTED: YAML valid

# 5. Count total active jobs:
grep -c "^  - name:" aria_mind/cron_jobs.yaml
# EXPECTED: ~11 jobs (after S2-01 merge)
```

## Prompt for Agent
```
Verify and persist cron optimization patches in cron_jobs.yaml.

**Files to read:**
- aria_mind/cron_jobs.yaml (full file)
- aria_memories/bugs/cron_patches_applied_2026-02-12.md (full file — patch details)
- aria_memories/bugs/cron_token_waste_critical_analysis.md (optimization recommendations)

**Constraints:** Docker-first — changes take effect on container restart.

**Steps:**
1. Read cron_jobs.yaml and patch log
2. Verify exploration_pulse is NOT in YAML
3. Change hourly_health_check to 6-hourly schedule
4. Rename to health_check (drop "hourly" since it's no longer hourly)
5. Verify db_maintenance delivery mode
6. Validate YAML syntax
7. Run verification commands
```
