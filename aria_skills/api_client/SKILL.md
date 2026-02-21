---
name: aria-apiclient
description: Centralized HTTP client for aria-api interactions
metadata: {"aria": {"emoji": "🔌", "requires": {"env": ["ARIA_API_URL"]}}}
---

# Aria API Client 🔌

Centralized HTTP client for all aria-api interactions. Skills should use this instead of direct database access when available.

## Usage

```bash
exec python3 /app/skills/run_skill.py api_client <function> '{"param": "value"}'
```

## Functions

### Activities
- `get_activities` - Get recent activities (limit: int)
- `create_activity` - Log an activity (action: str, skill: str, details: obj, success: bool)

### Thoughts
- `get_thoughts` - Get recent thoughts (limit: int)
- `create_thought` - Create a thought (content: str, category: str, metadata: obj)

### Memories
- `get_memories` - Get memories (limit: int, category: str)
- `get_memory` - Get memory by key (key: str)
- `set_memory` - Create/update memory (key: str, value: str, category: str)
- `delete_memory` - Delete memory (key: str)

### Goals
- `get_goals` - Get goals (limit: int, status: str)
- `create_goal` - Create goal (title: str, description: str, priority: int, due_date: str)
- `update_goal` - Update goal (goal_id: str, status: str, progress: int)
- `delete_goal` - Delete goal (goal_id: str)

### Hourly Goals
- `get_hourly_goals` - Get today's hourly goals (status: str)
- `create_hourly_goal` - Create hourly goal (hour_slot: int, goal_type: str, description: str)
- `update_hourly_goal` - Update hourly goal (goal_id: int, status: str)

### Knowledge Graph
- `get_knowledge_graph` - Get full graph
- `get_entities` - Get entities (limit: int, entity_type: str)
- `create_entity` - Create entity (name: str, entity_type: str, properties: obj)
- `create_relation` - Create relation (from_entity: str, to_entity: str, relation_type: str)

### Social
- `get_social_posts` - Get posts (limit: int, platform: str)
- `create_social_post` - Create post (content: str, platform: str, visibility: str)

### Heartbeats
- `get_heartbeats` - Get heartbeat logs (limit: int)
- `get_latest_heartbeat` - Get most recent heartbeat
- `create_heartbeat` - Log heartbeat (beat_number: int, status: str, details: obj)

### Performance
- `get_performance_logs` - Get performance logs (limit: int)
- `create_performance_log` - Create log (review_period: str, successes: str, failures: str, improvements: str)

### Tasks
- `get_tasks` - Get pending tasks (status: str)
- `create_task` - Create task (task_type: str, description: str, agent_type: str, priority: str)
- `update_task` - Update task (task_id: str, status: str, result: str)

### Schedule
- `get_schedule` - Get schedule status
- `trigger_schedule_tick` - Trigger manual tick
- `get_jobs` - Get scheduled jobs (live: bool)
- `sync_jobs` - Sync jobs from aria

## Configuration

| Env Variable | Description | Default |
|--------------|-------------|---------|
| `ARIA_API_URL` | Base URL for aria-api | `http://aria-api:8000/api` |
| `ARIA_API_TIMEOUT` | Request timeout (seconds) | `30` |

## Examples

```bash
# Get recent activities
exec python3 /app/skills/run_skill.py api_client get_activities '{"limit": 10}'

# Create a thought
exec python3 /app/skills/run_skill.py api_client create_thought '{"content": "This is my thought", "category": "reflection"}'

# Set a memory
exec python3 /app/skills/run_skill.py api_client set_memory '{"key": "user_preference", "value": "dark_mode", "category": "settings"}'

# Create a goal
exec python3 /app/skills/run_skill.py api_client create_goal '{"title": "Learn Rust", "priority": 2}'
```
