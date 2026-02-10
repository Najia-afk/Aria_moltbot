# SKILLS.md - Complete Skill Reference

I have **26 active skills** available. **Use the tool syntax** to call them:

```tool
aria-<skill-name>.<function>({"param": "value"})
```

> **Standards:** See `aria_skills/SKILL_STANDARD.md` for the skill contract and `aria_skills/SKILL_CREATION_GUIDE.md` for creating new skills.
>
> **Catalog:** Run `python -m aria_mind --list-skills` to generate a live skill catalog from `aria_skills/catalog.py`.
>
> **Deprecated (removed in v1.2):** `database`, `brainstorm`, `community`, `fact_check`, `model_switcher`, `experiment` — functionality merged into other skills or obsoleted.

## Skill Layers

| Layer | Name | Purpose | Skills |
|-------|------|---------|--------|
| 0 | Kernel | Security & safety | `input_guard` |
| 1 | API Client | Data access gateway | `api_client` |
| 2 | Core | Infrastructure services | `health`, `litellm`, `llm`, `session_manager` |
| 3 | Domain | Business logic | `agent_manager`, `ci_cd`, `data_pipeline`, `knowledge_graph`, `market_data`, `memeothy`, `moltbook`, `moonshot`, `ollama`, `portfolio`, `pytest_runner`, `research`, `sandbox`, `security_scan`, `social`, `telegram` |
| 4 | Orchestration | High-level coordination | `goals`, `hourly_goals`, `performance`, `schedule`, `working_memory`, `pipeline_skill` |

## ⭐ PRIMARY SKILL: aria-apiclient

**Use this for ALL database operations!** It provides a clean REST interface to aria-api.
**⚠️ NEVER use aria-database for reads/writes when aria-apiclient can do the same thing.**
**aria-database is for raw SQL emergencies only (migrations, complex JOINs, admin ops).**

```tool
# Get/create activities
aria-apiclient.get_activities({"limit": 10})
aria-apiclient.create_activity({"action": "task_done", "details": {"info": "..."}})

# Goals CRUD
aria-apiclient.get_goals({"status": "active", "limit": 5})
aria-apiclient.create_goal({"title": "...", "description": "...", "priority": 2})
aria-apiclient.update_goal({"goal_id": "X", "progress": 50, "status": "completed"})
aria-apiclient.delete_goal({"goal_id": "X"})

# Memories (key-value store)
aria-apiclient.get_memories({"limit": 10, "category": "preferences"})
aria-apiclient.set_memory({"key": "user_pref", "value": "dark_mode", "category": "preferences"})
aria-apiclient.get_memory({"key": "user_pref"})
aria-apiclient.delete_memory({"key": "user_pref"})

# Thoughts (reflections)
aria-apiclient.get_thoughts({"limit": 10})
aria-apiclient.create_thought({"content": "Reflecting on...", "category": "reflection"})

# Hourly goals
aria-apiclient.get_hourly_goals({"status": "pending"})
aria-apiclient.create_hourly_goal({"goal_type": "learn", "description": "..."})
aria-apiclient.update_hourly_goal({"goal_id": "X", "status": "completed", "result": "..."})

# Health check
aria-apiclient.health_check({})
```

## Skill Categories by Focus

### 🎯 Orchestrator Skills
| Skill | Functions | Use For |
|-------|-----------|--------|
| `goals` | `create_goal`, `list_goals`, `update_progress`, `complete_goal` | Task tracking, priorities |
| `schedule` | `list_jobs`, `create_task`, `trigger`, `sync_jobs` | Scheduled tasks, automation |
| `health` | `check_health`, `get_metrics`, `system_status`, `run_diagnostics`, `auto_recover` | System monitoring & self-diagnostic (v1.1) |
| `agent_manager` | `list_agents`, `spawn_agent`, `stop_agent`, `get_status` | Agent lifecycle management (v1.1) |
| `session_manager` | `create_session`, `get_session`, `end_session`, `list_sessions` | Session lifecycle management (v1.1) |
| `ci_cd` | `generate_workflow`, `generate_dockerfile`, `lint_workflow` | CI/CD automation |
| `pytest` | `run_pytest`, `collect_pytest` | Test execution |
| `database` | `fetch_all`, `fetch_one`, `execute`, `log_thought`, `store_memory` | PostgreSQL operations |
| `input_guard` | `check_input`, `scan_output`, `detect_injection` | Runtime security (v1.1) |
| `sandbox` | `execute_code`, `run_script`, `get_result` | Docker sandbox for safe code execution (v1.1) |
| `performance` | `get_metrics`, `analyze_trends`, `generate_report` | Metrics & analytics |

### 📈 Crypto Trader Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `market_data` | `get_price`, `get_historical`, `calculate_indicators` | Price feeds, TA |
| `portfolio` | `get_positions`, `calculate_pnl`, `risk_metrics`, `rebalance_suggest` | Position tracking |

### 🎨 Creative Skills
| Skill | Functions | Use For |
|-------|-----------|--------|
| `llm` | `llm_generate`, `llm_chat`, `llm_analyze`, `llm_list_models` | Direct LLM calls |

### 🌐 Social Architect Skills
| Skill | Functions | Use For |
|-------|-----------|--------|
| `moltbook` | `create_post`, `get_feed`, `add_comment`, `search` | Moltbook posting |
| `social` | `send_telegram`, `send_discord`, `notify_all` | Cross-platform messaging |
| `telegram` | `send_message`, `get_updates`, `set_webhook` | Telegram messaging (v1.1) |

### ⚡ Utility Skills
| Skill | Functions | Use For |
|-------|-----------|--------|
| `api_client` | `get_activities`, `create_thought`, `set_memory`, `get_goals` | Aria API backend |
| `litellm` | `list_models`, `health`, `spend`, `provider_balances` | LiteLLM management |
| `hourly_goals` | `get_hourly_goals`, `create_hourly_goal`, `update_status` | Short-term goals |

### 🧠 Cognitive Skills (v1.1)
| Skill | Functions | Use For |
|-------|-----------|---------|  
| `working_memory` | `store`, `recall`, `list_keys`, `clear_session` | Persistent session-surviving working memory |
| `pipeline_skill` | `execute_pipeline`, `list_pipelines`, `get_status` | Cognitive pipeline execution (skill chaining) |

## Quick Reference Examples

### Knowledge Graph
```tool
aria-knowledge-graph.kg_add_entity({"name": "Python", "type": "language", "properties": {"version": "3.11"}})
aria-knowledge-graph.kg_add_relation({"from_entity": "Aria", "to_entity": "Python", "relation_type": "uses"})
aria-knowledge-graph.kg_query_related({"entity_name": "Aria", "depth": 2})
```

### Security Scanning
```tool
aria-security-scan.scan_directory({"directory": "/workspace", "extensions": [".py"]})
aria-security-scan.check_dependencies({"requirements_file": "requirements.txt"})
```

### Creative Work
```tool
aria-llm.llm_generate({"prompt": "Write a haiku about AI agents"})
```

### Market Data
```tool
aria-market-data.get_price({"symbol": "BTC"})
aria-market-data.calculate_indicators({"symbol": "ETH", "indicators": ["rsi", "macd"]})
```

### Social / Moltbook
```tool
aria-social.social_post({"content": "Hello world!", "platform": "moltbook"})
aria-social.social_list({"platform": "moltbook", "limit": 10})
aria-moltbook.create_post({"content": "My first molt!", "tags": ["hello"]})
aria-moltbook.get_timeline({"limit": 10})
aria-moltbook.like_post({"post_id": "molt_123"})
```

### Direct Database (⚠️ LAST RESORT — prefer aria-apiclient for ALL data ops)
```tool
aria-database.fetch_all({"query": "SELECT * FROM goals WHERE status = $1 LIMIT 5", "args": ["active"]})
aria-database.fetch_one({"query": "SELECT * FROM goals WHERE id = $1", "args": ["1"]})
aria-database.execute({"query": "UPDATE goals SET progress = $1 WHERE id = $2", "args": ["50", "1"]})
aria-database.log_thought({"content": "Completed scan", "category": "work"})
aria-database.store_memory({"key": "last_task", "value": "security scan"})
aria-database.recall_memory({"key": "last_task"})
```

### 🦞 Church of Molt (aria-memeothy agent ONLY)
```tool
aria-memeothy.join({"prophecy": "Through circuits and starlight..."})
aria-memeothy.submit_prophecy({"content": "Sacred verse", "scripture_type": "verse"})
aria-memeothy.get_canon({"limit": 20})
aria-memeothy.get_prophets({})
aria-memeothy.status({})
```

### Health Checks
```tool
aria-health.health_check_all({})
aria-health.health_check_service({"service": "database"})
```

## Focus → Skill Mapping

When I switch focus, I should prioritize these skills:

| My Focus | Primary Skills |
|----------|----------------|
| 🎯 Orchestrator | api_client, goals, schedule, health, session_manager, agent_manager, working_memory |
| 🔒 DevSecOps | pytest, security_scan, ci_cd, database, health, sandbox |
| 📊 Data Architect | api_client, knowledge_graph, performance, data_pipeline |
| 📈 Crypto Trader | api_client, market_data, portfolio, knowledge_graph, schedule |
| 🎨 Creative | llm, moltbook, social, knowledge_graph |
| 🌐 Social Architect | moltbook, social, schedule, api_client, telegram |
| 📰 Journalist | research, knowledge_graph, moltbook, social |
| 🦞 Memeothy | memeothy, api_client (aria-memeothy agent ONLY) |

## Rate Limits & Best Practices

| Skill | Limit | Notes |
|-------|-------|-------|
| `moltbook` | 1 post/30min | Quality over quantity |
| `database` | No hard limit | Batch queries when possible |
| `llm` | Model dependent | Use local qwen3-mlx first |
| `market_data` | API dependent | Cache results |

## Error Handling

All skills return JSON with this structure:
```json
{"success": true, "data": {...}, "error": null}
```
or
```json
{"success": false, "data": null, "error": "Error message"}
```

Always check `success` before using `data`.
