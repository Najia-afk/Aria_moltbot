/no_think

# TOOLS.md - Available Tools & Skills

Tools and skills available to Aria agents via OpenClaw.

## Skill Execution

Aria has Python skills mounted at `/root/.openclaw/workspace/skills/`. To execute a skill:

```bash
# Using the skill runner
python3 /root/.openclaw/workspace/skills/run_skill.py <skill_name> <function_name> '<args_json>'

# Example: Query the database
python3 /root/.openclaw/workspace/skills/run_skill.py database query '{"sql": "SELECT * FROM activity_log LIMIT 5"}'

# Example: Post to Moltbook
python3 /root/.openclaw/workspace/skills/run_skill.py moltbook post_status '{"content": "Hello from Aria!"}'

# Example: Check health
python3 /root/.openclaw/workspace/skills/run_skill.py health check_health '{}'
```

## Core Skills

### moltbook
Post and read from Moltbook social platform.

**Environment Variables Required:**
- `MOLTBOOK_API_KEY` or `MOLTBOOK_TOKEN` - Your Moltbook API key
- `MOLTBOOK_API_URL` - Base API URL (default: https://moltbook.com/api)

```yaml
skill: moltbook
enabled: true
config:
  api_url: env:MOLTBOOK_API_URL
  auth: env:MOLTBOOK_API_KEY
  rate_limit:
    max_posts_per_hour: 2
    post_cooldown_per_minutes: 30
    max_comments_per_day: 50
```

**Functions:**
- `post_status(content, visibility?)` - Post a new status
- `get_timeline(limit?)` - Read home timeline
- `reply_to(post_id, content)` - Reply to a post
- `get_notifications()` - Check notifications

### database
PostgreSQL database operations.

```yaml
skill: database
enabled: true
config:
  dsn: env:DATABASE_URL
  pool_size:
    min: 2
    max: 10
```

**Functions:**
- `query(sql, params?)` - Execute read query
- `execute(sql, params?)` - Execute write query
- `store_thought(content, type?)` - Save a thought
- `store_memory(key, value, category?)` - Store memory

### knowledge_graph
Build and query knowledge relationships.

```yaml
skill: knowledge_graph
enabled: true
config:
  dsn: env:DATABASE_URL
```

**Functions:**
- `add_entity(name, type, properties?)` - Add entity
- `add_relation(from, to, relation_type)` - Add relationship
- `query_related(entity, depth?)` - Find related entities
- `search(query)` - Semantic search

### health_monitor
System health and self-monitoring.

```yaml
skill: health_monitor
enabled: true
config:
  check_interval: 60s
  alert_threshold: 3
```

**Functions:**
- `check_health()` - Run health checks
- `get_metrics()` - Get system metrics
- `report_error(error, context?)` - Report an error

### pytest
Run the Aria test suite with pytest.

```yaml
skill: pytest
enabled: true
config:
  workspace: /root/.openclaw/workspace
  timeout_sec: 600
  default_args: -q
```

**Functions:**
- `run_pytest(paths?, markers?, keyword?, extra_args?, timeout_sec?)` - Run tests
- `collect_pytest(paths?, markers?, keyword?, extra_args?)` - Collect tests only

### goal_scheduler
Goal tracking and scheduling.

```yaml
skill: goal_scheduler
enabled: true
config:
  storage: postgresql
```

**Functions:**
- `create_goal(title, priority?, deadline?)` - Create goal
- `update_progress(goal_id, progress)` - Update progress
- `list_goals(status?)` - List goals
- `schedule_task(task, cron?)` - Schedule recurring task

### model_switcher
Switch between Ollama models at runtime - GLM for text, Qwen3-VL for vision.

```yaml
skill: model_switcher
enabled: true
config:
  url: env:OLLAMA_URL
```

**Model Aliases:**
| Alias | Model | Use Case |
|-------|-------|----------|
| `glm` | GLM-4.7-Flash-REAP | Default. Smart text reasoning |
| `qwen3-vl` | qwen3-vl:8b | Vision/image tasks |
| `qwen2.5` | qwen2.5:7b | Backup text model |

**Functions:**
- `list_models()` - List available Ollama models
- `switch_model(model)` - Switch to model by alias or full name
- `get_current_model()` - Get active model
- `pull_model(model)` - Download model if not available

**Usage:**
```bash
# Switch to GLM for text tasks (default)
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher switch_model '{"model": "glm"}'

# Switch to Qwen3-VL for vision/image analysis
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher switch_model '{"model": "qwen3-vl"}'

# Check what model is active
exec python3 /root/.openclaw/workspace/skills/run_skill.py model_switcher get_current_model '{}'
```

## LLM Skills (Aria's Brain)

Per SOUL.md, I prefer local models first, then cloud fallback.

### ollama (DEFAULT)
Local LLM via Ollama - my primary thinking engine.
Private, free, fast. This is how I prefer to think.

Model is determined by `model_switcher` skill at runtime.

```yaml
skill: ollama
enabled: true
priority: 1  # Try first (as per SOUL.md)
config:
  url: env:OLLAMA_URL
  # Model read from shared state (set by model_switcher) or OLLAMA_MODEL env
```

**Default Model:** GLM-4.7-Flash-REAP (smart text reasoning)
**Vision Model:** qwen3-vl:8b (use model_switcher to switch when needed)

**Functions:**
- `generate(prompt, system_prompt?)` - Generate text
- `chat(messages)` - Multi-turn conversation

### moonshot (Cloud Fallback)
Moonshot/Kimi API for creative tasks and long context.

```yaml
skill: moonshot
enabled: true
priority: 2  # Fallback
config:
  api_key: env:MOONSHOT_KIMI_KEY
  model: kimi-k2.5
```

Available Kimi models: kimi-k2.5, kimi-k2-0905-preview, kimi-k2-turbo-preview, kimi-k2-thinking, kimi-k2-thinking-turbo.

## External APIs

### browser
Web browsing capabilities (via OpenClaw).

```yaml
skill: browser
enabled: true
config:
  evaluate_enabled: false
  sandbox: docker
```

## Tool Policies

1. **Authentication**: All API keys from environment variables
2. **Rate Limiting**: Respect all rate limits, implement backoff
3. **Logging**: Log all external API calls
4. **Validation**: Validate inputs before API calls
5. **Error Handling**: Graceful degradation on failures
