````skill
---
name: aria-sessionmanager
description: Two-layer session management â€” filesystem delete (live) + PG mark ended (history).
metadata: {"aria": {"emoji": "ðŸ§¹", "always": true}}
---

# aria-sessionmanager

Two-layer session management for aria:
1. **Filesystem** (aria-api volume): reads sessions.json, removes keys, archives .jsonl transcripts
2. **aria-api PG**: PATCHes session status to ended (keeps history on /sessions dashboard)

Sessions live on the filesystem at /app/agents/{agent}/sessions/sessions.json.
The skill operates directly on these files â€” no WebSocket or REST API needed for the live delete.

## Architecture

```
aria-api (Node.js)
  â””â”€ /app/agents/
       â”œâ”€ main/sessions/sessions.json    â† index (keyâ†’session map)
       â”‚                 abc123.jsonl     â† transcript
       â”‚                 abc123.jsonl.deleted.2026-02-15T... â† archived
       â”œâ”€ analyst/sessions/...
       â”œâ”€ aria-talk/sessions/...
       â””â”€ aria-memeothy/sessions/...

aria-api (FastAPI)
  â””â”€ PG: agent_sessions table
       â”œâ”€ metadata->>'aria_session_id' â† maps to filesystem session UUID
       â”œâ”€ status: active â†’ ended           â† PATCH /api/sessions/{id}
       â””â”€ syncs from shared volume every 30s
```

## Usage

```bash
exec python3 /app/skills/run_skill.py session_manager <function> '<json_args>'
```

## Functions

### list_sessions
List all active sessions from the filesystem. Scans all agent dirs by default.

```bash
# All agents
exec python3 /app/skills/run_skill.py session_manager list_sessions '{}'

# Specific agent
exec python3 /app/skills/run_skill.py session_manager list_sessions '{"agent": "main"}'
```

**Returns:**
```json
{
  "session_count": 16,
  "sessions": [
    {
      "id": "abc123", "sessionId": "abc123",
      "key": "agent:main:cron:abc123",
      "agentId": "main", "session_type": "cron",
      "label": "heartbeat", "updatedAt": "2026-02-15T18:00:00+00:00",
      "contextTokens": 500, "model": "gpt-4o"
    }
  ]
}
```

### delete_session
Two-layer delete: removes from filesystem + marks ended in PG.

```bash
exec python3 /app/skills/run_skill.py session_manager delete_session '{"session_id": "abc123"}'
```

**What happens:**
1. Removes all keys matching sessionId from sessions.json
2. Renames abc123.jsonl â†’ abc123.jsonl.deleted.<timestamp> (matches aria-api pattern)
3. Best-effort PATCH to aria-api: {"status": "ended"} (keeps history)

**Returns:**
```json
{
  "deleted": "abc123",
  "removed_keys": ["agent:main:cron:abc123"],
  "transcript_archived": true,
  "pg_status_updated": true,
  "message": "Session abc123 removed from aria-api (1 keys, transcript=archived), PG marked ended"
}
```

### prune_sessions
Prune stale sessions older than a threshold. Each pruned session gets the full two-layer delete.

```bash
# Dry run â€” preview what would be deleted
exec python3 /app/skills/run_skill.py session_manager prune_sessions '{"max_age_minutes": 60, "dry_run": true}'

# Actually prune
exec python3 /app/skills/run_skill.py session_manager prune_sessions '{"max_age_minutes": 60}'
```

**Returns:**
```json
{
  "total_sessions": 16,
  "pruned_count": 14,
  "kept_count": 2,
  "dry_run": false,
  "deleted_ids": ["abc123", "def456"],
  "errors": [],
  "threshold_minutes": 60
}
```

### get_session_stats
Get summary statistics about current sessions.

```bash
exec python3 /app/skills/run_skill.py session_manager get_session_stats '{}'
```

**Returns:**
```json
{
  "total_sessions": 16,
  "stale_sessions": 14,
  "active_sessions": 2,
  "by_agent": {"main": 10, "analyst": 3, "aria-talk": 2, "aria-memeothy": 1},
  "stale_threshold_minutes": 60
}
```

### cleanup_after_delegation
Clean up a session after a sub-agent delegation completes. Wrapper around delete_session.

```bash
exec python3 /app/skills/run_skill.py session_manager cleanup_after_delegation '{"session_id": "delegation-xyz"}'
```

## Automatic Cleanup Rules

Aria MUST follow these session hygiene rules:

1. **After sub-agent delegation**: call cleanup_after_delegation with the sub-agent's session ID.
2. **During work_cycle**: Run prune_sessions with max_age_minutes: 60 to clean up stale cron sessions.
3. **Before session review**: Run get_session_stats to check for bloat before reporting.

## Database (PG) â€” For Reference

The agent_sessions table in aria-api PG stores history:
- status: active â†’ ended (PATCH sets ended_at automatically)
- metadata->>'aria_session_id': maps to the filesystem session UUID
- Indexed: idx_agent_sessions_aria_sid, idx_agent_sessions_status
- Auto-synced from shared volume every 30s by aria-api

Aria can query /api/sessions on the dashboard to see historical data.
The skill does **NOT** delete PG rows â€” it only marks them ended.
````
