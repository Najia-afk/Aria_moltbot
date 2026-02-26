# aria-agent-manager

Runtime agent lifecycle management for Aria.

## Purpose
- Spawn, list, monitor, and terminate managed agent sessions.
- Produce performance summaries and prune stale sessions.
- Aria chooses at spawn time whether a sub-agent is ephemeral or persistent.

## Main Tools
- `list_agents` — list active agent sessions
- `spawn_agent` — create a raw session (engine table)
- `spawn_focused_agent` — spawn → task → response, with `persistent` flag:
  - `persistent=false` (default): ephemeral, auto-closes after response
  - `persistent=true`: session stays open for multi-turn follow-ups
- `send_to_agent` — send follow-up message to a persistent sub-agent session
- `terminate_agent` — close any session (engine or legacy)
- `get_agent_stats` — usage metrics for a session
- `prune_stale_sessions` — bulk cleanup
- `get_performance_report` — aggregate metrics
- `get_agent_health` — active agents, uptime, performance

## Delegation Pattern
```python
# One-shot (ephemeral)
result = spawn_focused_agent(task="...", focus="research", tools=[...])
# Session auto-closes after response

# Multi-turn (persistent)
result = spawn_focused_agent(task="...", focus="analyst", tools=[...], persistent=True)
session_id = result["session_id"]
follow_up = send_to_agent(session_id=session_id, message="Now refine that...")
terminate_agent(session_id=session_id)
```
