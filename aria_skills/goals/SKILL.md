---
name: aria-goals
description: Manage user goals, habits, and progress tracking. Create goals with milestones and reminders.
metadata: {"aria": {"emoji": "🎯", "requires": {"env": ["DATABASE_URL"]}}}
---

# aria-goals

Manage user goals, habits, and progress tracking. Create goals with milestones, track progress, and set reminders.

## Usage

```bash
exec python3 /app/skills/run_skill.py goals <function> '<json_args>'
```

## Functions

### list
List goals with optional filtering.

```bash
exec python3 /app/skills/run_skill.py goals list '{"status": "active"}'
```

**Filter options:**
- `status`: "active", "completed", "paused", "all"
- `category`: filter by category name

### create
Create a new goal.

```bash
exec python3 /app/skills/run_skill.py goals create '{"title": "Learn Italian", "category": "learning", "description": "Reach B1 level in Italian", "target_date": "2025-12-31", "milestones": ["Complete A1", "Complete A2", "Complete B1"]}'
```

### update
Update goal progress or details.

```bash
exec python3 /app/skills/run_skill.py goals update '{"goal_id": 1, "progress": 50, "note": "Completed A1 level!"}'
```

### complete_milestone
Mark a milestone as completed.

```bash
exec python3 /app/skills/run_skill.py goals complete_milestone '{"goal_id": 1, "milestone_index": 0}'
```

### get_reminders
Get goals with upcoming deadlines or check-in reminders.

```bash
exec python3 /app/skills/run_skill.py goals get_reminders '{"days_ahead": 7}'
```

## Goal Categories

Common categories:
- `health` - Fitness, wellness, medical
- `work` - Career, professional development
- `learning` - Education, skills, languages
- `personal` - Hobbies, relationships, lifestyle
- `financial` - Savings, investments, budgets

## Database Schema

Goals are stored in the `goals` table with:
- `id`, `title`, `description`
- `category`, `status`, `progress` (0-100)
- `target_date`, `created_at`, `updated_at`
- `milestones` (JSONB array)
- `metadata` (JSONB for extra data)

## Python Module

This skill wraps `/app/skills/aria_skills/goals.py`
