/no_think

# TOOLS.md - Skill Quick Reference

**Full documentation: See SKILLS.md for complete skill reference (24 skills)**

Skills are auto-discovered from `openclaw_skills/*/skill.json`.

## Execution Pattern

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py <skill> <function> '{"param": "value"}'
```

## All 24 Skills

| Category | Skills |
|----------|--------|
| 🎯 Orchestrator | `goals`, `schedule`, `health` |
| 🔒 DevSecOps | `security_scan`, `ci_cd`, `pytest`, `database` |
| 📊 Data | `data_pipeline`, `experiment`, `knowledge_graph`, `performance` |
| 📈 Trading | `market_data`, `portfolio` |
| 🎨 Creative | `brainstorm`, `llm` |
| 🌐 Social | `community`, `moltbook`, `social` |
| 📰 Journalist | `research`, `fact_check` |
| ⚡ Utility | `api_client`, `litellm`, `model_switcher`, `hourly_goals` |

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
