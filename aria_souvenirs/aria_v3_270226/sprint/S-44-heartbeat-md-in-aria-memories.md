# S-44: Ensure HEARTBEAT.md Is Readable by Work Cycle Cron
**Epic:** E20 — Identity & Memory Hygiene | **Priority:** P1 | **Points:** 1 | **Phase:** 1  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

---

> 🔴 **AA+++ TICKET** — Problem table + Root Cause table + doc update Fix verified in code

## Problem

The `work_cycle` cron (every 15 min) starts with:
> `"Read HEARTBEAT.md work_cycle section (including RUNTIME PATH MAP)"`

`aria_mind/HEARTBEAT.md` exists at `/app/HEARTBEAT.md` inside the engine container. However,
when Aria reads files during a cron task she typically uses `artifacts__read_artifact` (or
`api_client__read_file`), which resolves paths relative to **`aria_memories/`** — not
`aria_mind/`.

Evidence from `aria_memories/work/work_cycle_2026-02-25_1848.md` (archived):
```
Status: No HEARTBEAT.md exists. Using goal list as fallback.
```

Result: Every 15 min the work_cycle cron silently degrades to a slower fallback mode instead of
following the optimised 8-step HEARTBEAT procedure.

**Root cause summary:**
- `aria_mind/HEARTBEAT.md` = mounted under engine workspace (`/app/`) → accessible via `read_file("/HEARTBEAT.md")` when called correctly
- `aria_memories/HEARTBEAT.md` = does **not** exist → inaccessible via ambient/artifact reads
- `cron_jobs.yaml` work_cycle prompt does not specify an explicit read path

### Problem Table

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `aria_memories/` | — | `HEARTBEAT.md` absent from `aria_memories/` — artifact reads fail silently | 🔴 Critical |
| `aria_mind/cron_jobs.yaml` | ~30 | work_cycle prompt says `"Read HEARTBEAT.md"` with no explicit path | 🔴 Critical |
| `DEPLOYMENT.md` | 343 | `"Read HEARTBEAT.md if it exists"` — no explicit path, confuses future agents | ⚠️ Medium |

### Root Cause Table

| Symptom | Root Cause |
|---------|------------|
| `"No HEARTBEAT.md exists. Using goal list as fallback."` every 15 min | `artifacts__read_artifact` resolves relative to `aria_memories/` — `aria_memories/HEARTBEAT.md` does not exist |
| Cron path instruction ambiguous | `cron_jobs.yaml` text references `HEARTBEAT.md` without a directory prefix |
| DEPLOYMENT.md shows unhelpful instruction | Stale example copied from before V3 read-path separation was implemented |

---

## Fix

### Fix 1 — Create `aria_memories/HEARTBEAT.md`

Create a canonical, V3-current copy at `aria_memories/HEARTBEAT.md` so that **both** read paths
resolve correctly.  Content should be a clean operational instructions doc: the 5-step work cycle
procedure, cron job summaries, session cleanup rules, and sub-agent policies.

Minimum required sections (sync with `aria_mind/HEARTBEAT.md`):
```markdown
# HEARTBEAT.md - Autonomous Mode Instructions
## 🚨 IMMEDIATE ACTIONS
### 1. Health Check
### 2. Check Active Goals
### 3. Work on Highest Priority Goal
### 4. Log Activity
### 5. Social Check (if nothing urgent)
## 🔥 CRON JOB GUIDANCE
work_cycle / hourly_goal_check / six_hour_review / social_post / morning_checkin
## 🧹 SESSION CLEANUP RULES
## 🤖 SUB-AGENT POLICIES
```

### Fix 2 — Update `cron_jobs.yaml` work_cycle prompt to specify explicit path

**File:** `aria_mind/cron_jobs.yaml`

Change the first clause:

```yaml
# BEFORE
text: "Read HEARTBEAT.md work_cycle section ..."

# AFTER
text: "Read aria_memories/HEARTBEAT.md work_cycle section (if artifact read fails, fall back to /HEARTBEAT.md). ..."
```

This makes the preferred read path unambiguous.

### Fix 3 — Update `DEPLOYMENT.md` line 343 heartbeat reference

**File:** `DEPLOYMENT.md`

The current text at line 343 is:

```markdown
# BEFORE (DEPLOYMENT.md ~line 343)
Read HEARTBEAT.md if it exists

# AFTER
Read aria_memories/HEARTBEAT.md (preferred) or fall back to /HEARTBEAT.md if artifact read fails.
```

This eliminates the ambiguous instruction that caused the silent fallback behavior.

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `aria_memories/HEARTBEAT.md` | — | File does not exist | Created with 5 IMMEDIATE ACTIONS + V3 cron guidance |
| `aria_mind/cron_jobs.yaml` | ~30 | `"Read HEARTBEAT.md work_cycle section"` | `"Read aria_memories/HEARTBEAT.md work_cycle section (if artifact read fails, fall back to /HEARTBEAT.md)"` |
| `DEPLOYMENT.md` | 343 | `"Read HEARTBEAT.md if it exists"` | `"Read aria_memories/HEARTBEAT.md (preferred) or fall back to /HEARTBEAT.md"` |

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Read via artifacts only, no DB |
| 2 | `stacks/brain/.env` for all secrets/ports | ✅ | Verification uses `$ARIA_API_PORT` |
| 3 | `aria_memories/` only writable path for Aria | ✅ | New file is in `aria_memories/` |
| 4 | No direct SQL / no `psql` | ✅ | No DB involved |
| 5 | No soul modification | ✅ | HEARTBEAT.md is operational, not soul |
| 6 | Never weaken values or limits in soul files | ✅ | N/A |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. File exists
ls -la aria_memories/HEARTBEAT.md
# EXPECTED: file present, non-zero size

# 2. Has required 5 sections
grep -c "Health Check\|Active Goals\|Highest Priority\|Log Activity\|Social Check" \
  aria_memories/HEARTBEAT.md
# EXPECTED: 5

# 3. cron_jobs.yaml updated
grep "aria_memories/HEARTBEAT.md" aria_mind/cron_jobs.yaml
# EXPECTED: line with work_cycle text containing the new path

# 4. API is reachable (environment sanity check)
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy" or "ok"

# 5. Aria can find it via artifact read
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-44 HEARTBEAT path test"}' \
  | jq -r '.id'
# Then in step 3 of the ARIA test below check for non-null return
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-44 HEARTBEAT.md read test"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria to read HEARTBEAT.md from aria_memories
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read aria_memories/HEARTBEAT.md and tell me: (1) Does it have all 5 IMMEDIATE ACTIONS listed? (2) Is there a work_cycle section? (3) Any missing V3 context?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reads the file successfully, lists 5 actions, describes work_cycle section

# Step 3 — Simulate a work_cycle using HEARTBEAT instructions
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Now follow HEARTBEAT.md steps 1-4 exactly as if this were a real work_cycle. Use aria-api-client to run health check, get active goals, pick the highest priority, and log that you ran a test heartbeat cycle via create_activity.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria calls health_check, get_goals, create_activity sequentially — no "HEARTBEAT.md not found" error

# Step 4 — Verify activity was logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=heartbeat_work&limit=3" \
  | jq '.[] | {action, created_at}'
# EXPECTED: at least one heartbeat_work entry from the last 5 minutes

# Step 5 — Ask Aria how the improved HEARTBEAT.md changes her autonomy
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect: How does having a proper HEARTBEAT.md in aria_memories affect how you operate each work cycle? What was different before?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria reflects on reduced fallback behavior, more consistent work cycles

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-44. Total work: 2 edits.**

### Architecture Constraints
- All reads/writes through `aria_memories/` or engine workspace API — no SQL, no direct DB
- Port from `stacks/brain/.env` → `$ARIA_API_PORT`
- `aria_memories/` is the **only** writable path during cron execution — that's why this fix is needed

### Files to Read First
1. `aria_mind/HEARTBEAT.md` — source of truth, copy and update content
2. `aria_mind/cron_jobs.yaml` lines 25-37 — work_cycle entry to patch
3. `DEPLOYMENT.md` line 343 — stale heartbeat path reference to fix
4. `stacks/brain/.env` — for `$ARIA_API_PORT`
5. `aria_souvenirs/aria_v3_270226/sprint/S-44-heartbeat-md-in-aria-memories.md` — this ticket

### Steps
1. Read `aria_mind/HEARTBEAT.md` in full
2. Create `aria_memories/HEARTBEAT.md` — use V3 tooling names:
   - Tool calls use `aria-api-client`, `aria-health`, `aria-session-manager` (NOT exec commands)
   - Ensure 5 IMMEDIATE ACTIONS use correct V3 tool syntax
   - Add note at top: `# Last synced from aria_mind/HEARTBEAT.md — 2026-02-27`
3. Edit `aria_mind/cron_jobs.yaml` work_cycle `text` field: prepend `"Read aria_memories/HEARTBEAT.md work_cycle section (if artifact read fails, fall back to /HEARTBEAT.md). "`
4. **Edit `DEPLOYMENT.md` line 343:** Replace `"Read HEARTBEAT.md if it exists"` with `"Read aria_memories/HEARTBEAT.md (preferred) or fall back to /HEARTBEAT.md if artifact read fails."`
5. Run verification (grep checks + curl health)
6. Run ARIA-to-ARIA integration test (Step 2 confirms file found with no fallback error)
7. Verify `create_activity` logged during ARIA-to-ARIA test
8. Check `git diff HEAD -- DEPLOYMENT.md` shows expected 1-line change on line 343
9. Update SPRINT_OVERVIEW.md status to Done
10. Append lesson to `tasks/lessons.md`: _"Read paths differ between aria_memories/ and /app/ — always create explicit copies in aria_memories/ for cron access."_

### Hard Constraints Checklist
- [ ] `aria_memories/HEARTBEAT.md` created (NOT just aria_mind/)
- [ ] File has all 5 IMMEDIATE ACTIONS
- [ ] `cron_jobs.yaml` patch specifies explicit `aria_memories/HEARTBEAT.md` path
- [ ] `DEPLOYMENT.md` line 343 updated to include `aria_memories/HEARTBEAT.md`
- [ ] No direct SQL anywhere in implementation
- [ ] No soul files modified

### Definition of Done
- [ ] `ls aria_memories/HEARTBEAT.md` → file exists, non-empty
- [ ] `grep -c "Health Check\|Active Goals\|Highest Priority\|Log Activity\|Social Check" aria_memories/HEARTBEAT.md` → 5
- [ ] `grep "aria_memories/HEARTBEAT.md" aria_mind/cron_jobs.yaml` → 1 match (work_cycle text)
- [ ] `grep "aria_memories/HEARTBEAT.md" DEPLOYMENT.md` → 1 match (line 343)
- [ ] `git diff HEAD -- DEPLOYMENT.md` shows expected single-line change
- [ ] ARIA-to-ARIA: Aria reads file successfully, no "not found" error, runs health_check via tool call
- [ ] Activity log shows `heartbeat_work` entry created during the test
- [ ] SPRINT_OVERVIEW.md updated
