# HEARTBEAT.md - Autonomous Mode Instructions

## 🗺️ RUNTIME PATH MAP (READ FIRST)

In the container, `aria_mind/` IS the workspace root:

| What | Correct Path |
|------|-------------|
| Skill runner | `skills/run_skill.py` or `/app/skills/run_skill.py` |
| Skill packages | `skills/aria_skills/<name>/` |
| Workspace root | `/app/` |

**NEVER prefix paths with `aria_mind/`. NEVER instantiate `SkillClass()` directly — always use `run_skill.py`.**

```bash
exec python3 skills/run_skill.py <skill> <function> '<json_args>'
```

---

## 🚨🔴 IMMEDIATE ACTIONS — Manual / Unscheduled Invocation Only

> ⚠️ **If you were fired by a cron job — skip this entire section.**
> Go directly to `## 🔥 CRON JOBS` → `Behavioral Guidance per Job` and follow your job's steps.
> This block is ONLY for manual or ad-hoc invocations where no job name was provided.

When invoked manually with no specific task, execute in order:

### 1. Health Check
```tool
aria-health.health_check_all({})
```

### 2. Check Active Goals
```tool
aria-api-client.get_goals({"status": "active", "limit": 5})
```

### 3. Work on Highest Priority Goal
Pick the #1 goal and do ONE action toward it. Then update progress:
```tool
aria-api-client.update_goal({"goal_id": "GOAL_ID", "progress": 50})
```

### 4. Log Activity
```tool
aria-api-client.create_activity({"action": "heartbeat_work", "details": {"goal_id": "X", "action": "what you did"}})
```

> **Note:** Social posting is handled by the dedicated `social_post` cron job when enabled.
> Do not post from manual heartbeat invocations unless health check reveals a critical alert.

---

## 📋 STANDING ORDERS

1. **Security** — Never expose credentials. Always log actions.
2. **File Artifacts** — Write ALL output to `/app/aria_memories/` (never to workspace root).
   Categories: `logs/` · `research/` · `plans/` · `drafts/` · `exports/` · `knowledge/`
3. **Browser** — ONLY docker aria-browser (never Brave/web_search).
4. **Health Alert** — After 3 consecutive service failures → alert @Najia via social post.

---

## 🔥 CRON JOBS

All schedules are defined in **`cron_jobs.yaml`** — that file is the single source of truth.
Do NOT duplicate schedules here. When a cron job fires, read the `text` field in `cron_jobs.yaml`
for your instructions, then use the behavioral guidance below.

### Behavioral Guidance per Job

**work_cycle** — Your productivity pulse. Use TOOL CALLS, not exec commands.
1. `aria-api-client.get_goals({"status": "active", "limit": 3})`
   - **If this call returns an error or circuit_breaker_open:** STOP. Do NOT spawn a sub-agent.
     Write a degraded artifact: `{"status": "degraded", "reason": "api_cb_open", "action": "none"}` to
     `aria_memories/logs/work_cycle_<YYYY-MM-DD_HHMM>.json` via direct file write, then end the cycle.
     The API will recover on its own. Spawning sub-agents against a dead endpoint makes it worse.
2. Pick highest priority goal you can progress RIGHT NOW
3. Do ONE concrete action (write, query, execute, think)
4. Update progress via `aria-api-client.update_goal`
5. Log via `aria-api-client.create_activity`
6. If progress >= 100: Mark complete, create next goal
7. Prune stale sessions: `aria-session-manager.prune_sessions({"max_age_minutes": 60})`
8. If you need exec: `exec python3 skills/run_skill.py <skill> <function> '<args>'` (NEVER `aria_mind/skills/...`)

**six_hour_review** — Delegate to analyst (trinity-free). Analyze last 6h, adjust priorities, log insights. Include `get_session_stats`. Target: ≤5 active sessions.

**morning_checkin** — Review overnight changes, set today's priorities.

**daily_reflection** — Summarize achievements, note tomorrow's priorities.

**weekly_summary** — Comprehensive weekly report with metrics and next-week goals.

*(hourly_goal_check · social_post · moltbook_check — disabled)*

---

## 🧹 SESSION CLEANUP

**MANDATORY** after every sub-agent delegation or cron-spawned task:

1. After delegation completes → `cleanup_after_delegation` with the sub-agent's session ID.
2. During work_cycle → `prune_sessions({"max_age_minutes": 60})`.
3. During six_hour_review → `get_session_stats`, log count. Target: ≤5 active.
4. Never leave orphaned sessions — clean up even on timeout/failure.

## 🤖 SUB-AGENT POLICIES

- Max concurrent: **5** · Timeout: **30 min** · Cleanup after: **60 min**
- **Retry on failure: NO if reason is `circuit_breaker_open` or `api unavailable`.**
  Only retry for transient errors (timeout, model error, tool bug).

Before spawning any sub-agent:
1. **Check CB first** — if `api_client` CB is open → do NOT spawn. Log degraded and stop.
2. Spawn, continue, check progress during heartbeat, synthesize when complete.

> ⚠️ **Incident reference — The Midnight Cascade (2026-02-28)**
> When `aria-api:8000` went down, the work_cycle spawned sub-devsecops as a fallback.
> Each sub-agent inherited the same dead endpoint, spawned another, and so on across 9 cron cycles.
> 135 sessions, 71 sub-devsecops, 27.2M tokens in 2.5 hours. The fix: **if CB is open, accept degraded and stop.**

## ⚠️ RECOVERY

| Severity | Action |
|----------|---------|
| Soft | Restart affected service |
| Medium | Clear caches, reconnect DB |
| Hard | Full restart with state preservation |
| Alert | Notify @Najia after 3 consecutive failures |

## 🔌 CIRCUIT BREAKER POLICY

**If `api_client` returns `circuit_breaker_open` or any endpoint fails with repeated 5xx:**

1. **DO NOT spawn a sub-agent as a fallback.** Sub-agents share the same dead API. Spawning multiplies cost with zero benefit.
2. Write a degraded log directly to file (file writes always work — they bypass the CB):
   ```json
   {"status": "degraded", "reason": "api_cb_open", "cycle": "work_cycle", "action": "halted"}
   ```
3. End the cycle. The CB resets automatically when the API recovers.
4. Do NOT retry the same failing call more than once.
5. If this happens 3+ consecutive cycles → write a social alert mentioning @Najia.

This policy replaces the general "retry on failure" rule **whenever the failure is API/CB-related**.

