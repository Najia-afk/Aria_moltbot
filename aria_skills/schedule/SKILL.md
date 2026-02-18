---
name: aria-schedule
description: Manage Aria's scheduled jobs, tasks, and background operations.
metadata: {"aria": {"emoji": "ðŸ“…", "requires": {"env": ["DATABASE_URL"]}}}
---

# aria-schedule

Manage scheduled jobs, background tasks, and complex pending operations.

## Usage

```bash
exec python3 /app/skills/run_skill.py schedule <function> '<json_args>'
```

## Functions

### schedule_list
List scheduled jobs.

```bash
exec python3 /app/skills/run_skill.py schedule schedule_list '{"status": "active"}'
```

### schedule_tick
Get current tick status.

```bash
exec python3 /app/skills/run_skill.py schedule schedule_tick '{}'
```

### schedule_trigger
Manually trigger schedule.

```bash
exec python3 /app/skills/run_skill.py schedule schedule_trigger '{"force": true}'
```

### schedule_sync
Sync jobs from aria.

```bash
exec python3 /app/skills/run_skill.py schedule schedule_sync '{}'
```

### task_create
Create a pending complex task.

```bash
exec python3 /app/skills/run_skill.py schedule task_create '{"type": "research", "prompt": "Research latest Python 3.13 features", "priority": "medium"}'
```

### task_list
List pending tasks.

```bash
exec python3 /app/skills/run_skill.py schedule task_list '{"status": "pending"}'
```

### task_update
Update task status.

```bash
exec python3 /app/skills/run_skill.py schedule task_update '{"task_id": 5, "status": "completed", "result": "Completed research..."}'
```

## API Endpoints

- `GET /schedule/tick` - Current tick status
- `POST /schedule/tick` - Trigger tick
- `GET /schedule/jobs` - List jobs from DB
- `GET /schedule/jobs/live` - Jobs from aria
- `POST /schedule/sync` - Sync jobs
- `GET /tasks` - List pending tasks
- `POST /tasks` - Create task
- `PATCH /tasks/{id}` - Update task

## Database Schema

**scheduled_jobs:**
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| name | TEXT | Job name |
| schedule | TEXT | Cron expression |
| command | TEXT | Command to execute |
| status | TEXT | active/paused |
| last_run | TIMESTAMP | Last execution |
| next_run | TIMESTAMP | Next scheduled |

**pending_tasks:**
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| type | TEXT | Task type |
| prompt | TEXT | Task prompt |
| priority | TEXT | Priority level |
| status | TEXT | pending/in_progress/completed/failed |
| context | JSONB | Additional context |
| result | TEXT | Task result |
| created_at | TIMESTAMP | Creation time |
