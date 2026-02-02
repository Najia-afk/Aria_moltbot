---
name: aria-database
description: Query Aria's PostgreSQL database for activity logs, memories, knowledge graph, and user data.
metadata: {"openclaw": {"emoji": "🗄️", "requires": {"env": ["DB_USER"]}}}
---

# aria-database

Query Aria's PostgreSQL database for activity logs, memories, knowledge graph, and user data.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py database <function> '<json_args>'
```

## Functions

### db_query
Execute a read-only SQL query on Aria's database.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py database query '{"sql": "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 10"}'
```

### db_execute
Execute a write SQL statement (INSERT, UPDATE, DELETE).

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py database execute '{"sql": "INSERT INTO activity_log (activity_type, message) VALUES ($1, $2)", "params": ["note", "Test entry"]}'
```

### db_log_activity
Log an activity with type, message, and optional metadata.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py database log_activity '{"activity_type": "observation", "message": "User seems tired today", "metadata": {"mood": "concerned"}}'
```

## Available Tables

| Table | Description |
|-------|-------------|
| `activity_log` | Timestamped activity records |
| `memories` | Long-term memory storage |
| `knowledge_entities` | Knowledge graph nodes |
| `knowledge_relations` | Knowledge graph edges |
| `goals` | User goals and progress |
| `hourly_goals` | Short-term hourly tasks |
| `social_posts` | Social media posts |
| `performance_log` | Performance reviews |
| `pending_tasks` | Complex tasks queue |
| `scheduled_jobs` | Background job schedules |
| `interactions` | User interaction logs |
| `thoughts` | Internal thought records |

## Example Queries

**Recent activities:**
```sql
SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 20
```

**Search memories:**
```sql
SELECT * FROM memories WHERE content ILIKE '%keyword%'
```

**Knowledge graph entities:**
```sql
SELECT * FROM knowledge_entities WHERE type = 'person'
```

**Active goals:**
```sql
SELECT * FROM goals WHERE status = 'active' ORDER BY created_at DESC
```

## Python Module

This skill wraps `/root/.openclaw/workspace/skills/aria_skills/database.py`
