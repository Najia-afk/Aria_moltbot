/no_think

# SKILLS.md - Complete Skill Reference

I have **24 skills** available. **Use the tool syntax** to call them:

```tool
aria-<skill-name>.<function>({"param": "value"})
```

## ⭐ PRIMARY SKILL: aria-apiclient

**Use this for ALL database operations!** It provides a clean REST interface to aria-api.

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
|-------|-----------|---------|
| `goals` | `create_goal`, `list_goals`, `update_progress`, `complete_goal` | Task tracking, priorities |
| `schedule` | `list_jobs`, `create_task`, `trigger`, `sync_jobs` | Scheduled tasks, automation |
| `health` | `check_health`, `get_metrics`, `system_status` | System monitoring |

### 🔒 DevSecOps Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `security_scan` | `scan_file`, `scan_directory`, `check_dependencies`, `audit_docker` | Vulnerability scanning |
| `ci_cd` | `generate_workflow`, `generate_dockerfile`, `lint_workflow` | CI/CD automation |
| `pytest` | `run_pytest`, `collect_pytest` | Test execution |
| `database` | `fetch_all`, `fetch_one`, `execute`, `log_thought`, `store_memory` | PostgreSQL operations |

### 📊 Data Architect Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `data_pipeline` | `validate_data`, `transform`, `infer_schema`, `profile` | ETL operations |
| `experiment` | `create_experiment`, `log_metrics`, `compare`, `register_model` | ML experiment tracking |
| `knowledge_graph` | `kg_add_entity`, `kg_add_relation`, `kg_query_related`, `kg_search` | Entity relationships |
| `performance` | `get_metrics`, `analyze_trends`, `generate_report` | Metrics & analytics |

### 📈 Crypto Trader Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `market_data` | `get_price`, `get_historical`, `calculate_indicators` | Price feeds, TA |
| `portfolio` | `get_positions`, `calculate_pnl`, `risk_metrics`, `rebalance_suggest` | Position tracking |

### 🎨 Creative Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `brainstorm` | `start_session`, `add_idea`, `apply_technique`, `evaluate_ideas` | Ideation (SCAMPER, Six Hats) |
| `llm` | `llm_generate`, `llm_chat`, `llm_analyze`, `llm_list_models` | Direct LLM calls |

### 🌐 Social Architect Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `community` | `get_health_score`, `identify_champions`, `suggest_initiatives` | Community health |
| `moltbook` | `create_post`, `get_feed`, `add_comment`, `search` | Moltbook posting |
| `social` | `send_telegram`, `send_discord`, `notify_all` | Cross-platform messaging |

### 📰 Journalist Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `research` | `search_sources`, `extract_claims`, `assess_credibility` | Source collection |
| `fact_check` | `verify_claim`, `get_verdict`, `generate_report` | Claim verification |

### ⚡ Utility Skills
| Skill | Functions | Use For |
|-------|-----------|---------|
| `api_client` | `get_activities`, `create_thought`, `set_memory`, `get_goals` | Aria API backend |
| `litellm` | `list_models`, `health`, `spend`, `provider_balances` | LiteLLM management |
| `model_switcher` | `switch_model`, `get_current_model`, `list_available` | Model selection |
| `hourly_goals` | `get_hourly_goals`, `create_hourly_goal`, `update_status` | Short-term goals |

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
aria-brainstorm.start_session({"topic": "AI agent improvements"})
aria-brainstorm.apply_technique({"session_id": "abc123", "technique": "scamper"})
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

### Direct Database (use sparingly - prefer aria-apiclient)
```tool
aria-database.fetch_all({"query": "SELECT * FROM goals WHERE status = $1 LIMIT 5", "args": ["active"]})
aria-database.fetch_one({"query": "SELECT * FROM goals WHERE id = $1", "args": ["1"]})
aria-database.execute({"query": "UPDATE goals SET progress = $1 WHERE id = $2", "args": ["50", "1"]})
aria-database.log_thought({"content": "Completed scan", "category": "work"})
aria-database.store_memory({"key": "last_task", "value": "security scan"})
aria-database.recall_memory({"key": "last_task"})
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
| 🎯 Orchestrator | goals, schedule, health, llm |
| 🔒 DevSecOps | security_scan, ci_cd, pytest, database |
| 📊 Data Architect | data_pipeline, experiment, knowledge_graph, performance |
| 📈 Crypto Trader | market_data, portfolio, database, schedule |
| 🎨 Creative | brainstorm, llm, moltbook |
| 🌐 Social Architect | community, moltbook, social, schedule |
| 📰 Journalist | research, fact_check, knowledge_graph, social |

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
