/no_think

# SKILLS.md - Complete Skill Reference

I have **24 skills** available. Each skill is a Python implementation that I call via `exec`:

```bash
exec python3 /root/.openclaw/workspace/skills/run_skill.py <skill> <function> '{"param": "value"}'
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
| `database` | `db_query`, `db_execute`, `db_log_activity` | PostgreSQL operations |

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

### Database Operations
```bash
# Query goals
exec python3 /root/.openclaw/workspace/skills/run_skill.py database db_query '{"sql": "SELECT * FROM goals WHERE status = $1 LIMIT 5", "params": ["active"]}'

# Log activity
exec python3 /root/.openclaw/workspace/skills/run_skill.py database db_log_activity '{"activity_type": "task", "message": "Completed security scan"}'
```

### Knowledge Graph
```bash
# Add entity
exec python3 /root/.openclaw/workspace/skills/run_skill.py knowledge_graph kg_add_entity '{"name": "Python", "type": "language", "properties": {"version": "3.11"}}'

# Add relation
exec python3 /root/.openclaw/workspace/skills/run_skill.py knowledge_graph kg_add_relation '{"from_entity": "Aria", "to_entity": "Python", "relation_type": "uses"}'

# Query related
exec python3 /root/.openclaw/workspace/skills/run_skill.py knowledge_graph kg_query_related '{"entity_name": "Aria", "depth": 2}'
```

### Security Scanning
```bash
# Scan directory
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan scan_directory '{"directory": "/root/.openclaw/workspace", "extensions": [".py"]}'

# Check dependencies
exec python3 /root/.openclaw/workspace/skills/run_skill.py security_scan check_dependencies '{"requirements_file": "requirements.txt"}'
```

### Creative Work
```bash
# Start brainstorm
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm start_session '{"topic": "AI agent improvements"}'

# Apply technique
exec python3 /root/.openclaw/workspace/skills/run_skill.py brainstorm apply_technique '{"session_id": "abc123", "technique": "scamper"}'
```

### Market Data
```bash
# Get price
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data get_price '{"symbol": "BTC"}'

# Technical indicators
exec python3 /root/.openclaw/workspace/skills/run_skill.py market_data calculate_indicators '{"symbol": "ETH", "indicators": ["rsi", "macd"]}'
```

### API Client (Centralized Backend)
```bash
# Get recent activities
exec python3 /root/.openclaw/workspace/skills/run_skill.py api_client get_activities '{"limit": 10}'

# Create thought
exec python3 /root/.openclaw/workspace/skills/run_skill.py api_client create_thought '{"content": "Reflecting on today...", "category": "reflection"}'

# Set memory
exec python3 /root/.openclaw/workspace/skills/run_skill.py api_client set_memory '{"key": "user_preference", "value": "dark_mode"}'
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
