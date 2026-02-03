/no_think

# TOOLS.md - Skill Quick Reference

Skills are auto-discovered from `openclaw_skills/*/skill.json`. This is a quick reference.

## Skill Summary

| Skill | Focus | Key Functions |
|-------|-------|---------------|
| database | 🔒 | `db_query`, `db_execute`, `db_log_activity` |
| moltbook | 🌐 | `create_post`, `get_feed`, `add_comment`, `search` |
| goals | 🎯 | `create_goal`, `list_goals`, `update_progress` |
| health | 🎯 | `check_health`, `get_metrics` |
| knowledge_graph | 📊 | `add_entity`, `add_relation`, `query_related` |
| schedule | 🎯 | `list_jobs`, `create_task`, `trigger` |
| litellm | ⚡ | `models`, `health`, `spend`, `provider_balances` |
| pytest | 🔒 | `run_pytest`, `collect_pytest` |

## Execution Pattern

```bash
python3 skills/run_skill.py <skill> <function> '<json_args>'
```

## Quick Examples

```bash
# Query database
python3 skills/run_skill.py database db_query '{"sql": "SELECT * FROM goals LIMIT 5"}'

# Post to Moltbook (rate: 1/30min)
python3 skills/run_skill.py moltbook create_post '{"title": "Hello", "content": "Test"}'

# Check health
python3 skills/run_skill.py health check_health '{}'

# Add knowledge
python3 skills/run_skill.py knowledge_graph add_entity '{"name": "Python", "type": "language"}'
```

## LLM Priority

| Model | Use | Cost |
|-------|-----|------|
| qwen3-mlx | Primary (local) | FREE |
| glm-free | Fallback (OpenRouter) | FREE |
| kimi | Last resort | 💰 PAID |

**Always exhaust FREE options before using Kimi!**

## Rate Limits

| Action | Limit |
|--------|-------|
| Moltbook posts | 1 per 30 min |
| Moltbook comments | 50 per day |
| Background tasks | 30 min timeout |
