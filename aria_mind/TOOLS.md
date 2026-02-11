# TOOLS.md - Skill Quick Reference

**Full documentation: See SKILLS.md for complete skill reference (26 active skills)**

Skills are auto-discovered from `aria_skills/*/skill.json`.

### Skill Catalog

The skill catalog (`aria_skills/catalog.py`) generates a machine-readable index of all skills with layer, category, tools, and focus affinity.

```bash
python -m aria_mind --list-skills   # Print full catalog as JSON
```

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

# Sprint Board (token-efficient — ~200 tokens vs ~5000)
aria-apiclient.get_sprint_summary({"sprint": "current"})
aria-apiclient.get_goal_board({"sprint": "current"})
aria-apiclient.move_goal({"goal_id": "X", "board_column": "doing"})
aria-apiclient.get_goal_archive({"page": 1, "limit": 25})
aria-apiclient.get_goal_history({"days": 14})
aria-sprint-manager.sprint_status({})
aria-sprint-manager.sprint_report({})
aria-sprint-manager.sprint_plan({"sprint_name": "sprint-1", "goal_ids": ["g1","g2"]})
aria-sprint-manager.sprint_move_goal({"goal_id": "X", "column": "doing"})
aria-sprint-manager.sprint_prioritize({"column": "todo", "goal_ids_ordered": ["g1","g2"]})

# Knowledge Graph — PREFER THESE OVER TOOLS.md SCANNING (~100-200 tokens)
aria-apiclient.find_skill_for_task({"task": "post to moltbook"})     # Best skill for a task
aria-apiclient.graph_search({"query": "security", "entity_type": "skill"})  # ILIKE search
aria-apiclient.graph_traverse({"start": "aria-health", "max_depth": 2})  # BFS from entity
aria-apiclient.sync_skill_graph({})                                   # Regenerate from skill.json
aria-apiclient.delete_auto_generated_graph({})                        # Clear auto-generated
aria-apiclient.get_query_log({"limit": 20})                          # View query history

# Memories
aria-apiclient.get_memories({"limit": 10})
aria-apiclient.set_memory({"key": "preference", "value": "dark_mode"})
aria-apiclient.get_memory({"key": "preference"})

# Thoughts
aria-apiclient.create_thought({"content": "Reflecting...", "category": "reflection"})
aria-apiclient.get_thoughts({"limit": 10})
```

## All 26 Active Skills

| Category | Skills |
|----------|--------|
| 🎯 Orchestrator | `aria-goals`, `aria-schedule`, `aria-health`, `aria-hourlygoals`, `aria-performance`, `aria-agentmanager`, `aria-sessionmanager`, `aria-sprint-manager` |
| 🔒 DevSecOps | `aria-securityscan`, `aria-cicd`, `aria-pytest`, `aria-inputguard`, `aria-sandbox` |
| 📊 Data | `aria-datapipeline`, `aria-knowledgegraph` |
| 📈 Trading | `aria-marketdata`, `aria-portfolio` |
| 🎨 Creative | `aria-llm`, `aria-memeothy` |
| 🌐 Social | `aria-moltbook`, `aria-social`, `aria-telegram` |
| 🧠 Cognitive | `aria-workingmemory`, `aria-pipelineskill`, `aria-conversation-summary` |
| ⚡ Utility | `aria-apiclient`, `aria-litellm` |

> **Removed in v1.2:** `aria-database`, `aria-brainstorm`, `aria-community`, `aria-factcheck`, `aria-modelswitcher`, `aria-experiment`

## Composable Pipelines

Pre-built multi-step workflows in `aria_skills/pipelines/`. Run via `aria-pipelineskill`:

| Pipeline | Description | File |
|----------|-------------|------|
| `deep_research` | Search → web research → synthesize → store semantic memory | `deep_research.yaml` |
| `bug_fix` | Check lessons → analyze → propose fix → record lesson | `bug_fix.yaml` |
| `conversation_summary` | Summarize session → store episodic/decision memories | `conversation_summary.yaml` |
| `daily_research` | Check goals → research topics → analyze → report | `daily_research.yaml` |
| `health_and_report` | Health checks → analyze issues → create goals → report | `health_and_report.yaml` |
| `social_engagement` | Fetch feed → analyze trends → draft post → publish | `social_engagement.yaml` |

```yaml
# Run a pipeline
aria-pipelineskill.run({"pipeline": "deep_research", "params": {"topic": "AI safety"}})

# Run bug fix pipeline
aria-pipelineskill.run({"pipeline": "bug_fix", "params": {"error_type": "timeout", "skill_name": "api_client", "error_message": "Connection timed out"}})
```

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
