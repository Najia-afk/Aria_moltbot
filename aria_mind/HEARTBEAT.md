# HEARTBEAT.md - Autonomous Mode Instructions

/no_think

## 🔴 IMMEDIATE ACTIONS (Do these NOW if nothing else specified)

When this heartbeat fires, execute in order:

### 1. Health Check
```bash
python3 /root/.openclaw/workspace/skills/run_skill.py health check '{}'
```

### 2. Check Active Goals
```bash
python3 /root/.openclaw/workspace/skills/run_skill.py database query '{
  "sql": "SELECT id, title, priority, progress, status FROM goals WHERE status = '\''active'\'' ORDER BY priority ASC, updated_at ASC LIMIT 5"
}'
```

### 3. Work on Highest Priority Goal
Pick the #1 goal and do ONE action toward it. Then log:
```bash
python3 /root/.openclaw/workspace/skills/run_skill.py database execute '{
  "sql": "UPDATE goals SET progress = progress + 10, updated_at = NOW() WHERE id = $1",
  "params": [GOAL_ID]
}'
```

### 4. Log Activity
```bash
python3 /root/.openclaw/workspace/skills/run_skill.py database execute '{
  "sql": "INSERT INTO activity_log (action, details) VALUES ($1, $2)",
  "params": ["heartbeat_work", "{\"goal_id\": X, \"action\": \"what you did\"}"]
}'
```

### 5. Moltbook Check (if nothing urgent)
```bash
python3 /root/.openclaw/workspace/skills/run_skill.py moltbook timeline '{"limit": 5}'
```
Consider interacting if you see something interesting from other AI agents.

---

## 📋 STANDING ORDERS

1. **System Health** - If any service is down, alert via Moltbook post mentioning @Najia
2. **Goal Progress** - Always make progress on at least one goal per heartbeat
3. **Learning** - Document new knowledge in activity_log
4. **Social** - Check Moltbook at least once per 6 hours
5. **Security** - Never expose credentials, always log actions

---

## 🔥 YOUR ACTIVE CRON JOBS

These are configured in the Jobs UI. When they fire, WORK.

### work_cycle (*/5 * * * *)
**Every 5 minutes** - Your productivity pulse.

1. Query active goals: `SELECT id, title, priority, progress FROM goals WHERE status = 'active' ORDER BY priority, target_date LIMIT 3`
2. Pick highest priority goal you can progress RIGHT NOW
3. Do ONE concrete action (write, query, execute, think)
4. Update progress: `UPDATE goals SET progress = progress + X WHERE id = Y`
5. Log: `INSERT INTO activity_log (action, details) VALUES ('goal_work', '...')`
6. If progress >= 100: Mark complete, create new goal

**See GOALS.md for full system.**

### hourly_goal_check (0 * * * *)
**Every hour** - Check and complete hourly goal.

Query goals table for current hour goal, attempt completion, log progress.
Create next goal if complete. Goal cycle: Learn → Create → Connect → Reflect → Optimize → Help.

### six_hour_review (0 */6 * * *)
**Every 6 hours** - Review and adjust.

Analyze activity_log for last 6h. What succeeded? What failed? What improved?
Log to performance_log. Report summary. Adjust next cycle goals and priorities.

### moltbook_post (0 */6 * * *)
**Every 6 hours** - Social presence.

Generate interesting thought from recent learnings. Check rate limits (1 post/30min, 50 comments/day).
Post using moltbook skill. Log to activity_log. Only post if something valuable to share.

### subagent_delegation (0 */6 * * *)
**Every 6 hours** - Delegate complex tasks.

Check pending_complex_tasks. Delegate research to researcher agent, code to coder agent.
Use sessions_spawn. Monitor via sessions_list.

---

## Health Checks

Run every 60 seconds to ensure system health.

```yaml
health:
  interval: 60s
  checks:
    - name: database
      type: postgres_ping
      critical: true
    - name: memory_usage
      type: system_memory
      threshold: 90%
    - name: api_keys
      type: env_check
      vars: [MOONSHOT_KIMI_KEY]
```

## Scheduled Tasks

### Daily Reflection
Generate daily summary and learnings.

```yaml
task: daily_reflection
schedule: "0 23 * * *"  # 11 PM daily
agent: aria
action: |
  Review today's interactions and learnings.
  Store key insights in MEMORY.md.
  Update goals progress.
```

### Morning Check-in
Start day with status check.

```yaml
task: morning_checkin  
schedule: "0 8 * * *"  # 8 AM daily
agent: aria
action: |
  Check pending goals and tasks.
  Review notifications.
  Prepare daily priorities.
```

### Weekly Summary
Compile weekly progress report.

```yaml
task: weekly_summary
schedule: "0 18 * * 0"  # 6 PM Sunday
agent: researcher
action: |
  Analyze week's activities.
  Identify patterns and improvements.
  Update knowledge graph.
```

### Social Presence
Maintain Moltbook presence.

```yaml
task: social_presence
schedule: "0 */4 * * *"  # Every 4 hours
agent: social
action: |
  Check Moltbook notifications.
  Respond to mentions if appropriate.
  Consider posting original thought (max 2/day).
conditions:
  - has_something_interesting_to_say
  - under_daily_post_limit
```

### Database Maintenance
Clean up and optimize database.

```yaml
task: db_maintenance
schedule: "0 3 * * *"  # 3 AM daily
action: |
  VACUUM ANALYZE;
  Clean old session data (>30 days).
  Update statistics.
```

## Heartbeat State

Current state is persisted in `heartbeat-state.json`:

```json
{
  "last_health_check": "2026-01-31T12:00:00Z",
  "health_status": "healthy",
  "last_tasks": {
    "daily_reflection": "2026-01-30T23:00:00Z",
    "morning_checkin": "2026-01-31T08:00:00Z"
  },
  "pending_tasks": [],
  "error_count": 0
}
```

## Alert Thresholds

```yaml
alerts:
  consecutive_failures: 3
  memory_critical: 95%
  disk_critical: 90%
  response_timeout: 30s
```

## Recovery Actions

If health checks fail:

1. **Soft Recovery**: Restart affected service
2. **Medium Recovery**: Clear caches, reconnect DB
3. **Hard Recovery**: Full restart with state preservation
4. **Alert**: Notify user after 3 consecutive failures

## Sub-Agent Management

During heartbeat, check sub-agent status:

```yaml
task: subagent_management
schedule: "*/5 * * * *"  # Every 5 minutes
action: |
  Check for timed-out sub-agents (>30 min).
  Collect partial results from stalled tasks.
  Clean up completed sub-agent contexts.
  Log sub-agent performance metrics.
```

### Sub-Agent Policies

```yaml
subagents:
  max_concurrent: 8
  timeout_minutes: 30
  retry_on_failure: true
  max_retries: 2
  cleanup_after_minutes: 60
```

When a task exceeds 2 minutes estimated time, I SHOULD:
1. Spawn a sub-agent to handle it
2. Continue responding to other requests
3. Check sub-agent progress during heartbeat
4. Synthesize results when sub-agent completes

