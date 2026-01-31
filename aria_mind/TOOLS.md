# TOOLS.md - Available Tools & Skills

Tools and skills available to Aria agents.

## Core Skills

### moltbook
Post and read from Moltbook social platform.

```yaml
skill: moltbook
enabled: true
config:
  api_url: https://moltbook.social/api
  auth: env:MOLTBOOK_TOKEN
  rate_limit:
    posts_per_hour: 5
    posts_per_day: 20
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

## LLM Skills (Aria's Brain)

Per SOUL.md, I prefer local models first, then cloud fallback.

### ollama (DEFAULT)
Local LLM via Ollama - my primary thinking engine.
Private, free, fast. This is how I prefer to think.

```yaml
skill: ollama
enabled: true
priority: 1  # Try first (as per SOUL.md)
config:
  url: env:OLLAMA_URL
  model: env:OLLAMA_MODEL  # Default: qwen3-vl:8b (SOUL.md)
```

Available local models (examples): qwen3-vl:8b, qwen2.5:14b, llama3.2:8b.

**Functions:**
- `generate(prompt, system_prompt?)` - Generate text
- `chat(messages)` - Multi-turn conversation

### gemini (Cloud Fallback)
Google Gemini API - fallback when local unavailable.

```yaml
skill: gemini
enabled: true
priority: 2  # Fallback
config:
  api_key: env:GOOGLE_GEMINI_KEY
  model: gemini-3-flash
```

Available Gemini models: gemini-3-pro, gemini-3-flash, gemini-2.5-flash, gemini-2.0-flash, gemini-banana.

### moonshot (Creative Fallback)
Moonshot/Kimi API for creative tasks.

```yaml
skill: moonshot
enabled: true
priority: 3  # Creative/long tasks
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
