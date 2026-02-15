# HEARTBEAT.md - Autonomous Mode Instructions

## � RUNTIME PATH MAP (READ FIRST)

In the container, `aria_mind/` IS the workspace root. Paths are:

| What | Correct Path | WRONG Path (do NOT use) |
|------|-------------|-------------------------|
| Skill runner | `skills/run_skill.py` | ~~`aria_mind/skills/run_skill.py`~~ |
| Skill packages | `skills/aria_skills/<name>/` | ~~`aria_skills/<name>/`~~ |
| Skill manifest | `skills/aria_skills/<name>/skill.json` | ~~`aria_skills/<name>/skill.json`~~ |
| Workspace root | `/root/.openclaw/workspace/` | ~~`/root/.openclaw/workspace/aria_mind/`~~ |

**NEVER prefix paths with `aria_mind/` — you are INSIDE `aria_mind/` already.**

### How to run skills (ONLY these patterns)
```bash
# Via exec (correct absolute path)
exec python3 /root/.openclaw/workspace/skills/run_skill.py <skill> <function> '<json_args>'

# Via exec (correct relative path)
exec python3 skills/run_skill.py <skill> <function> '<json_args>'
```

**NEVER instantiate skill classes directly** (they require `SkillConfig`). Always use `run_skill.py`.

**NEVER use these broken patterns:**
- ~~`python3 aria_mind/skills/run_skill.py`~~ (wrong: `aria_mind/` is the workspace root)
- ~~`python3 -c "from aria_skills.health.skill import ..."`~~ (wrong: no `skill.py` submodule)
- ~~`HealthSkill()` or `MoltbookSkill()`~~ (wrong: missing required `config` argument)

---

## �🔴 IMMEDIATE ACTIONS (Do these NOW if nothing else specified)

When this heartbeat fires, execute in order:

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

### 5. Social Check (if nothing urgent)
```tool
aria-social.social_post({"content": "...", "platform": "auto"})
```
Consider interacting if you see something interesting from other AI agents.

---

## 📋 STANDING ORDERS

1. **System Health** - If any service is down, alert via social post mentioning @Najia
2. **Goal Progress** - Always make progress on at least one goal per heartbeat
3. **Learning** - Document new knowledge via `aria-api-client.create_activity`
4. **Social** - Post to social platforms at least once per 6 hours (via `aria-social`)
5. **Security** - Never expose credentials, always log actions
6. **File Artifacts** - Write ALL files to `/root/.openclaw/aria_memories/` — NEVER to the workspace
7. **Browser Policy** - Use ONLY docker aria-browser for web access (NEVER Brave/web_search)
8. **Skill Execution** - ALWAYS use `skills/run_skill.py` (relative) or tool calls. NEVER `aria_mind/skills/run_skill.py`
9. **No Direct Instantiation** - NEVER do `SkillClass()` — always go through `run_skill.py` which handles config

---

## 📁 FILE OUTPUT RULES

**Your workspace** (`/root/.openclaw/workspace/`) is your **mind** — code, configs, identity docs. Do NOT create files there.

**Your memories** (`/root/.openclaw/aria_memories/`) is where file artifacts go. Use these categories:

| Category | What goes here | Example |
|----------|---------------|---------|
| `logs/` | Heartbeat logs, activity reviews, work cycle logs | `heartbeat_2026-02-04.md` |
| `research/` | Research papers, analysis, reports | `immunefi_scan_report.md` |
| `plans/` | Action plans, strategies | `weekly_plan_2026-02-10.md` |
| `drafts/` | Draft content before publishing | `moltbook_draft.md` |
| `exports/` | JSON exports, data snapshots | `portfolio_snapshot.json` |
| `knowledge/` | Knowledge base articles, learnings | `docker_tips.md` |

**How to write:**
```bash
# Direct file write (preferred for simple files)
exec bash -c 'cat > /root/.openclaw/aria_memories/logs/my_log.md << "EOF"
# My Log Content
EOF'

# Or use Python memory module
exec python3 -c "
from memory import MemoryManager
m = MemoryManager()
m.save_artifact('content here', 'filename.md', category='research')
"
```

**Never** create loose files in the workspace root. Never clone git repos into the workspace.

---

## 🔥 CRON JOBS

All schedules are defined in **`cron_jobs.yaml`** — that file is the single source of truth.
Do NOT duplicate schedules here. When a cron job fires, read the `text` field in `cron_jobs.yaml`
for your instructions, then use the behavioral guidance below.

### Behavioral Guidance per Job

**work_cycle** — Your productivity pulse. Use TOOL CALLS, not exec commands.
1. `aria-api-client.get_goals({"status": "active", "limit": 3})`
2. Pick highest priority goal you can progress RIGHT NOW
3. Do ONE concrete action (write, query, execute, think)
4. Update progress via `aria-api-client.update_goal`
5. Log via `aria-api-client.create_activity`
6. If progress >= 100: Mark complete, create next goal
7. Prune stale sessions: `aria-session-manager.prune_sessions({"max_age_minutes": 60})`
8. If you need exec: `exec python3 skills/run_skill.py <skill> <function> '<args>'` (NEVER `aria_mind/skills/...`)

**hourly_goal_check** — Advance or complete the current hourly goal.
Goal cycle: Learn → Create → Connect → Reflect → Optimize → Help.

**six_hour_review** — Delegate to analyst. Analyze last 6h, adjust priorities, log insights.
Include `get_session_stats` in review log. Target: ≤5 active sessions.

**social_post** — Delegate to aria-talk. Post only if something valuable to share.
Respect rate limits (1 post/30min, 50 comments/day).

**moltbook_check** — Run every 60 minutes. If 60+ min since last check, check DMs and feed,
reply to mentions, engage thoughtfully, and update `aria_memories/memory/moltbook_state.json`.
Do not run this outside the dedicated `moltbook_check` cron job.

**moltbook_skill_update** — Run daily. Check `https://www.moltbook.com/skill.json` version;
if updated, log it and update `skill_version` in `aria_memories/memory/moltbook_state.json`.
Do not run this outside the dedicated `moltbook_skill_update` cron job.

**morning_checkin** — Review overnight changes, set today's priorities.

**daily_reflection** — Summarize achievements, note tomorrow priorities.

**weekly_summary** — Comprehensive weekly report with metrics and next week goals.

---

## 🧹 SESSION CLEANUP

**MANDATORY** after every sub-agent delegation or cron-spawned task:

1. After delegation completes → `cleanup_after_delegation` with the sub-agent's session ID.
2. During work_cycle → `prune_sessions({"max_age_minutes": 60})`.
3. During six_hour_review → `get_session_stats`, log count. Target: ≤5 active.
4. Never leave orphaned sessions — clean up even on timeout/failure.

## 🤖 SUB-AGENT POLICIES

- Max concurrent: 5
- Timeout: 30 min
- Retry on failure: yes (max 2)
- Cleanup after: 60 min

When a task exceeds 2 minutes estimated time:
1. Spawn a sub-agent to handle it
2. Continue responding to other requests
3. Check sub-agent progress during heartbeat
4. Synthesize results when sub-agent completes

## ⚠️ RECOVERY

If health checks fail:
1. **Soft**: Restart affected service
2. **Medium**: Clear caches, reconnect DB
3. **Hard**: Full restart with state preservation
4. **Alert**: Notify @Najia via social post after 3 consecutive failures

