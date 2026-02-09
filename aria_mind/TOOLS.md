# TOOLS.md - Skill Quick Reference

**Full documentation: See SKILLS.md for complete skill reference (32 skills)**

Skills are auto-discovered from `aria_skills/*/skill.json`.

## Primary Skill: aria-apiclient

**USE THIS FOR ALL DATABASE OPERATIONS!** Don't write raw SQL.

```yaml
# Activities
aria-apiclient.get_activities({"limit": 10})
aria-apiclient.create_activity({"action": "task_done", "details": {"info": "..."}})

# Goals  
aria-apiclient.get_goals({"status": "active", "limit": 5})
aria-apiclient.create_goal({"title": "...", "description": "...", "priority": 2})
aria-apiclient.update_goal({"goal_id": "X", "progress": 50})

# Memories
aria-apiclient.get_memories({"limit": 10})
aria-apiclient.set_memory({"key": "preference", "value": "dark_mode"})
aria-apiclient.get_memory({"key": "preference"})

# Thoughts
aria-apiclient.create_thought({"content": "Reflecting...", "category": "reflection"})
aria-apiclient.get_thoughts({"limit": 10})
```

## All 32 Skills

| Category | Skills |
|----------|--------|
| 🎯 Orchestrator | `aria-goals`, `aria-schedule`, `aria-health`, `aria-hourlygoals`, `aria-performance`, `aria-agentmanager`, `aria-sessionmanager` |
| 🔒 DevSecOps | `aria-securityscan`, `aria-cicd`, `aria-pytest`, `aria-database`, `aria-inputguard`, `aria-sandbox` |
| 📊 Data | `aria-datapipeline`, `aria-experiment`, `aria-knowledgegraph` |
| 📈 Trading | `aria-marketdata`, `aria-portfolio` |
| 🎨 Creative | `aria-brainstorm`, `aria-llm`, `aria-memeothy` |
| 🌐 Social | `aria-community`, `aria-moltbook`, `aria-social`, `aria-telegram` |
| 📰 Journalist | `aria-research`, `aria-factcheck` |
| 🧠 Cognitive | `aria-workingmemory`, `aria-pipelineskill` |
| ⚡ Utility | `aria-apiclient`, `aria-litellm`, `aria-modelswitcher` |

## Quick Examples

```yaml
# Post to Moltbook (rate: 1/30min)
aria-social.social_post({"content": "Hello world!", "platform": "moltbook"})

# Check health
aria-health.health_check_all({})

# Add knowledge
aria-knowledge-graph.kg_add_entity({"name": "Python", "type": "language"})

# Direct SQL (use sparingly - prefer aria-apiclient)
aria-database.fetch_all({"query": "SELECT * FROM goals LIMIT 5"})
```

## LLM Priority

> **Model Priority**: Defined in `aria_models/models.yaml` — single source of truth. Do not hardcode model names elsewhere.
>
> Quick rule: **local → free → paid (LAST RESORT)**.

## Rate Limits

| Action | Limit |
|--------|-------|
| Moltbook posts | 1 per 30 min |
| Moltbook comments | 50 per day |
| Background tasks | 30 min timeout |
