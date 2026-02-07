---
name: aria-sessionmanager
description: Manage OpenClaw sessions — list, prune stale sessions, delete by ID, and clean up after sub-agent delegations.
metadata: {"openclaw": {"emoji": "🧹", "always": true}}
---

# aria-sessionmanager

Session management for OpenClaw. Prevents session bloat from cron jobs, sub-agent delegations, and completed tasks accumulating stale sessions.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager <function> '<json_args>'
```

## Functions

### list_sessions
List all active sessions with metadata.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager list_sessions '{}'
```

**Returns:**
```json
{
  "session_count": 16,
  "sessions": [
    {"id": "abc123", "agentId": "main", "updatedAt": "2026-02-04T18:00:00Z"},
    {"id": "def456", "agentId": "aria-deep", "updatedAt": "2026-02-04T12:00:00Z"}
  ]
}
```

### delete_session
Delete a specific session by ID.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager delete_session '{"session_id": "abc123"}'
```

### prune_sessions
Prune stale sessions older than a threshold.

```bash
# Dry run — preview what would be deleted
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager prune_sessions '{"max_age_minutes": 60, "dry_run": true}'

# Actually prune
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager prune_sessions '{"max_age_minutes": 60}'
```

**Returns:**
```json
{
  "total_sessions": 16,
  "pruned_count": 14,
  "kept_count": 2,
  "dry_run": false,
  "deleted_ids": ["abc123", "def456", "..."],
  "threshold_minutes": 60
}
```

### get_session_stats
Get summary statistics about current sessions.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager get_session_stats '{}'
```

**Returns:**
```json
{
  "total_sessions": 16,
  "stale_sessions": 14,
  "active_sessions": 2,
  "by_agent": {"main": 10, "aria-deep": 3, "aria-talk": 2, "aria-memeothy": 1},
  "stale_threshold_minutes": 60
}
```

### cleanup_after_delegation
Clean up a session after a standalone sub-agent delegation completes. **Aria should call this automatically after every delegated task returns.**

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py session_manager cleanup_after_delegation '{"session_id": "delegation-xyz"}'
```

## Automatic Cleanup Rules

Aria MUST follow these session hygiene rules:

1. **After sub-agent delegation**: When a delegated task to aria-deep, aria-talk, or any sub-agent completes, immediately call `cleanup_after_delegation` with the sub-agent's session ID.
2. **During work_cycle**: Run `prune_sessions` with `max_age_minutes: 60` to clean up stale cron sessions.
3. **Before session review**: Run `get_session_stats` to check for bloat before reporting.
