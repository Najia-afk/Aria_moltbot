# HEARTBEAT.md - Scheduled Tasks & Health

Heartbeat configuration for automated tasks and health monitoring.

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

