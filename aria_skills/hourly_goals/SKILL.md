---
name: aria-hourlygoals
description: Manage Aria's hourly goals and micro-tasks for short-term focus.
metadata: {"aria": {"emoji": "â°", "requires": {"env": ["DATABASE_URL"]}}}
---

# aria-hourlygoals

Manage hourly goals for focused, short-term work. Links to main goals for progress tracking.

## Usage

```bash
exec python3 /app/skills/run_skill.py hourly_goals <function> '<json_args>'
```

## Functions

### hourly_create
Create an hourly goal.

```bash
exec python3 /app/skills/run_skill.py hourly_goals hourly_create '{"title": "Review PR #123", "priority": "high"}'
```

### hourly_list
List hourly goals.

```bash
exec python3 /app/skills/run_skill.py hourly_goals hourly_list '{"status": "pending"}'
```

### hourly_update
Update goal status.

```bash
exec python3 /app/skills/run_skill.py hourly_goals hourly_update '{"goal_id": 5, "status": "completed", "notes": "Merged successfully"}'
```

## API Endpoints

- `GET /hourly-goals` - List hourly goals
- `POST /hourly-goals` - Create hourly goal
- `PATCH /hourly-goals/{id}` - Update hourly goal

## Database Schema

**hourly_goals:**
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| title | TEXT | Goal title |
| description | TEXT | Details |
| status | TEXT | pending/in_progress/completed/failed |
| priority | TEXT | low/medium/high/critical |
| target_hour | TIMESTAMP | Target completion time |
| parent_goal_id | INTEGER | Link to main goal |
| notes | TEXT | Progress notes |
| created_at | TIMESTAMP | Creation time |
| completed_at | TIMESTAMP | Completion time |
