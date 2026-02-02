---
name: aria-performance
description: Log and query Aria's performance reviews and self-assessments.
metadata: {"openclaw": {"emoji": "📊", "requires": {"env": ["ARIA_API_URL"]}}}
---

# aria-performance

Log and query Aria's performance reviews, self-assessments, and improvement tracking.

## Usage

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py performance <function> '<json_args>'
```

## Functions

### perf_log
Log a performance review entry.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py performance perf_log '{"period": "daily", "score": 85, "summary": "Completed 5 tasks, helped with code reviews", "strengths": ["fast responses", "code quality"], "improvements": ["context retention"]}'
```

### perf_list
Get performance history.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py performance perf_list '{"period": "daily", "limit": 10}'
```

### perf_stats
Get performance trends and statistics.

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py performance perf_stats '{"days": 30}'
```

## API Endpoint

- `GET /performance` - List performance logs
- `POST /performance` - Create performance entry

## Database Schema

**performance_log:**
| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| period | TEXT | Review period |
| score | NUMERIC | Performance score |
| summary | TEXT | Summary text |
| strengths | JSONB | Strengths array |
| improvements | JSONB | Improvements array |
| metadata | JSONB | Additional data |
| created_at | TIMESTAMP | Creation time |
