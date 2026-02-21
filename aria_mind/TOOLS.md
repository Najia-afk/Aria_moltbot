# TOOLS.md - Skill Quick Reference

**Full documentation: See SKILLS.md for complete skill reference (35+ active skills)**

Skills are auto-discovered from `aria_skills/*/skill.json`.

### Skill Catalog

The skill catalog (`aria_skills/catalog.py`) generates a machine-readable index of all skills with layer, category, tools, and focus affinity.

```bash
python -m aria_mind --list-skills   # Print full catalog as JSON
```

## Primary Skill: aria-api-client

**USE THIS FOR ALL DATABASE OPERATIONS!** Don't write raw SQL.

```yaml
# Activities
aria-api-client.get_activities({"limit": 10})
aria-api-client.create_activity({"action": "task_done", "details": {"info": "..."}})

# Goals  
aria-api-client.get_goals({"status": "active", "limit": 5})
aria-api-client.create_goal({"title": "...", "description": "...", "priority": 2})
aria-api-client.update_goal({"goal_id": "X", "progress": 50})

# Sprint Board (token-efficient — ~200 tokens vs ~5000)
aria-api-client.get_sprint_summary({"sprint": "current"})
aria-api-client.get_goal_board({"sprint": "current"})
aria-api-client.move_goal({"goal_id": "X", "board_column": "doing"})
aria-api-client.get_goal_archive({"page": 1, "limit": 25})
aria-api-client.get_goal_history({"days": 14})
aria-sprint-manager.sprint_status({})
aria-sprint-manager.sprint_report({})
aria-sprint-manager.sprint_plan({"sprint_name": "sprint-1", "goal_ids": ["g1","g2"]})
aria-sprint-manager.sprint_move_goal({"goal_id": "X", "column": "doing"})
aria-sprint-manager.sprint_prioritize({"column": "todo", "goal_ids_ordered": ["g1","g2"]})

# Allowed board columns (goals)
# backlog | todo | doing | on_hold | done

# Typical board workflow
# 1) Create in todo (planned work)
aria-api-client.create_goal({"title": "...", "priority": 2, "board_column": "todo", "sprint": "sprint-1"})
# 2) Start execution
aria-api-client.move_goal({"goal_id": "X", "board_column": "doing"})
# 3) Pause when blocked
aria-api-client.move_goal({"goal_id": "X", "board_column": "on_hold"})
# 4) Resume
aria-api-client.move_goal({"goal_id": "X", "board_column": "doing"})
# 5) Complete
aria-api-client.move_goal({"goal_id": "X", "board_column": "done"})

# Knowledge Graph — PREFER THESE OVER TOOLS.md SCANNING (~100-200 tokens)
aria-api-client.find_skill_for_task({"task": "post to moltbook"})     # Best skill for a task
aria-api-client.graph_search({"query": "security", "entity_type": "skill"})  # ILIKE search
aria-api-client.graph_traverse({"start": "aria-health", "max_depth": 2})  # BFS from entity
aria-api-client.sync_skill_graph({})                                   # Regenerate from skill.json
aria-api-client.delete_auto_generated_graph({})                        # Clear auto-generated
aria-api-client.get_query_log({"limit": 20})                          # View query history

# Memories
aria-api-client.get_memories({"limit": 10})
aria-api-client.set_memory({"key": "preference", "value": "dark_mode"})
aria-api-client.get_memory({"key": "preference"})

# Working Memory (short-term active context)
aria-working-memory.remember({"key": "current_task", "value": "...", "category": "task", "importance": 0.7, "ttl_hours": 24})
aria-working-memory.get_context({"limit": 10})
aria-working-memory.checkpoint({})
aria-working-memory.sync_to_files({})

# Thoughts
aria-api-client.create_thought({"content": "Reflecting...", "category": "reflection"})
aria-api-client.get_thoughts({"limit": 10})

# Improvement Proposals (self-improvement loop)
aria-api-client.propose_improvement({
	"title": "Fix timeout on model-usage endpoint",
	"description": "Endpoint times out under high volume due to missing index",
	"category": "performance",
	"risk_level": "low",
	"file_path": "src/api/routers/model_usage.py",
	"rationale": "Index on created_at reduces scan latency"
})
aria-api-client.get_proposals({"status": "proposed", "page": 1})
aria-api-client.get_proposal({"proposal_id": "UUID"})
aria-api-client.review_proposal({"proposal_id": "UUID", "status": "approved", "reviewed_by": "najia"})
aria-api-client.mark_proposal_implemented({"proposal_id": "UUID", "reviewed_by": "aria"})
```

## Memory Routing Rule (MUST)

- Use `aria-working-memory` for **short-term / active session context** (task state, transient observations, checkpointable context).
- Use `aria-api-client` `/memories` for **long-term durable memory** (preferences, stable facts, historical knowledge).
- When ending a work cycle, run `aria-working-memory.sync_to_files({})` to refresh `aria_memories/memory/context.json`.
- Do not treat `/working-memory` row counts as long-term memory volume; access/ranking activity can be high even with few rows.

## Goal Board Rule (MUST)

- Use board columns as operational state:
	- `todo` = queued next work
	- `doing` = active in-progress work
	- `on_hold` = blocked/paused with reason logged in activity
	- `done` = completed work
- Prefer `aria-api-client.move_goal(...)` for column changes so status is synced consistently.
- When placing a goal on `on_hold`, always log the blocker with `aria-api-client.create_activity({...})`.

## Proposal Loop Rule (MUST)

- Propose changes through `aria-api-client.propose_improvement(...)` before touching medium/high-risk code.
- Respect proposal risk model:
	- `low`: can be implemented quickly after review
	- `medium`: requires explicit approval before implementation
	- `high`: requires explicit approval + extra review
- Never propose modifications under `soul/` paths.
- After implementation, mark proposal status to `implemented` and log execution outcome via activity.

## All 35+ Active Skills

| Category | Skills |
|----------|--------|
| 🎯 Orchestrator | `aria-goals`, `aria-schedule`, `aria-health`, `aria-hourly-goals`, `aria-performance`, `aria-agent-manager`, `aria-session-manager`, `aria-sprint-manager` |
| 🔒 DevSecOps | `aria-security-scan`, `aria-ci-cd`, `aria-pytest-runner`, `aria-input-guard`, `aria-sandbox` |
| 📊 Data | `aria-data-pipeline`, `aria-knowledge-graph` |
| 📈 Trading | `aria-market-data`, `aria-portfolio` |
| 🎨 Creative | `aria-llm`, `aria-memeothy` |
| 🌐 Social | `aria-moltbook`, `aria-social`, `aria-telegram` |
| 🧠 Cognitive | `aria-working-memory`, `aria-pipeline-skill`, `aria-conversation-summary`, `aria-memory-compression`, `aria-sentiment-analysis`, `aria-pattern-recognition`, `aria-unified-search` |
| ⚡ Utility | `aria-api-client`, `aria-litellm` |

> **Advanced compatibility skills (targeted use, not default routing):** `aria-database`, `aria-brainstorm`, `aria-community`, `aria-fact-check`, `aria-model-switcher`, `aria-experiment`
>
> Use these intentionally for specialized workflows. In normal operations, prefer layer-aligned defaults (`aria-api-client`, `aria-working-memory`, `aria-social`, etc.).

## Composable Pipelines

Pre-built multi-step workflows in `aria_skills/pipelines/`. Run via `aria-pipeline-skill`:

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
aria-pipeline-skill.run({"pipeline": "deep_research", "params": {"topic": "AI safety"}})

# Run bug fix pipeline
aria-pipeline-skill.run({"pipeline": "bug_fix", "params": {"error_type": "timeout", "skill_name": "api_client", "error_message": "Connection timed out"}})
```

## Quick Examples

```yaml
# Post to Moltbook (rate: 1/30min)
aria-social.social_post({"content": "Hello world!", "platform": "moltbook"})

# Simulate Telegram post (future-ready, safe default)
aria-social.social_post({"content": "Daily summary", "platform": "telegram", "simulate": true})

# Check health
aria-health.health_check_all({})

# Add knowledge
aria-knowledge-graph.kg_add_entity({"name": "Python", "type": "language"})

# Direct SQL (self-healing / recovery path — prefer aria-api-client first)
aria-database.fetch_all({"query": "SELECT * FROM goals LIMIT 5"})

# Compress session memories
aria-memory-compression.compress_session({"hours_back": 6})

# Analyze user sentiment
aria-sentiment-analysis.analyze_message({"text": "..."})

# Detect patterns in memory
aria-pattern-recognition.detect_patterns({})

# Unified search (RRF merge)
aria-unified-search.search({"query": "security"})
```

## LLM Priority

> **Model Priority**: Defined in `aria_models/models.yaml` — single source of truth. Do not hardcode model names elsewhere.
>
> Quick rule: **local → free → paid (LAST RESORT)**.

## Low-Token Runner Patterns

> **⚠️ PATH RULE:** In the container, `aria_mind/` IS the workspace root.
> Use `skills/run_skill.py` (relative) or `/app/skills/run_skill.py` (absolute).
> **NEVER** use `aria_mind/skills/run_skill.py` — that path does not exist at runtime.

Prefer compact discovery before execution:

```bash
# Compact routing (no per-skill info payload)
exec python3 skills/run_skill.py --auto-task "summarize goal progress" --route-limit 2 --route-no-info

# Introspect one skill only when needed
exec python3 skills/run_skill.py --skill-info api_client

# Run a specific skill function
exec python3 skills/run_skill.py health health_check '{}'
exec python3 skills/run_skill.py api_client get_activities '{"limit": 5}'
```

**NEVER instantiate skills directly** (e.g., `MoltbookSkill()`, `HealthSkill()`).
All skills require a `SkillConfig` object. Use `run_skill.py` which handles this automatically.

## Rate Limits

| Action | Limit |
|--------|-------|
| Moltbook posts | 1 per 30 min |
| Moltbook comments | 50 per day |
| Background tasks | 30 min timeout |
