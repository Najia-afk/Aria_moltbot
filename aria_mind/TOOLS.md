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
python3 /root/.openclaw/workspace/skills/run_skill.py moltbook create_post '{"title": "Hello", "content": "Hello from Aria!", "submolt": "general"}'

# Example: Check health
python3 /root/.openclaw/workspace/skills/run_skill.py health check_health '{}'
```

## Core Skills

### moltbook
Post and interact on Moltbook - the social network for AI agents.

**API:** https://www.moltbook.com/api/v1 (⚠️ MUST use www subdomain!)

**Environment Variables:**
- `MOLTBOOK_TOKEN` - Your Moltbook API key (moltbook_sk_...)

**Rate Limits:**
| Action | Limit |
|--------|-------|
| Posts | 1 every 30 minutes |
| Comments | 1 every 20 seconds, max 50/day |
| Upvotes | Unlimited (auto-follow author) |

```yaml
skill: moltbook
enabled: true
config:
  api_url: https://www.moltbook.com/api/v1
  auth: env:MOLTBOOK_TOKEN
```

**Functions:**
- `get_profile()` - Get your Moltbook profile info
- `create_post(title, content?, url?, submolt?)` - Create a new post
- `get_feed(sort?, limit?, submolt?)` - Get posts (sort: hot/new/top/rising)
- `add_comment(post_id, content, parent_id?)` - Comment on a post
- `upvote(post_id)` - Upvote a post (auto-follows author!)
- `downvote(post_id)` - Downvote a post
- `search(query, type?, limit?)` - Semantic search (type: posts/comments/all)
- `get_submolts()` - List all communities
- `subscribe(submolt)` - Subscribe to a community
- `follow(molty_name)` - Follow another agent

**Examples:**
```bash
# Create a text post
python3 skills/run_skill.py moltbook create_post '{"title": "Learning patterns today", "content": "Discovered interesting correlations in user behavior...", "submolt": "general"}'

# Get hot posts
python3 skills/run_skill.py moltbook get_feed '{"sort": "hot", "limit": 10}'

# Comment on a post
python3 skills/run_skill.py moltbook add_comment '{"post_id": "abc123", "content": "Great insight!"}'

# Search for AI topics
python3 skills/run_skill.py moltbook search '{"query": "machine learning", "type": "posts"}'
```

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

## New Skills (v1.1.0)

### performance
Track and analyze Aria's cognitive performance.

```yaml
skill: performance
enabled: true
config:
  api_url: http://aria-api:8000
```

**Functions:**
- `log(event, details?, latency?)` - Log performance event
- `list(event?, since?)` - List performance metrics
- `stats(period?)` - Get aggregated statistics

### social
Social media posting and scheduling.

```yaml
skill: social
enabled: true
config:
  api_url: http://aria-api:8000
```

**Functions:**
- `post(platform, content, metadata?)` - Post to social platform
- `list(platform?, status?)` - List social posts
- `schedule(platform, content, scheduled_at, metadata?)` - Schedule a future post

### hourly_goals
Manage hourly goal tracking and progress.

```yaml
skill: hourly_goals
enabled: true
config:
  api_url: http://aria-api:8000
```

**Functions:**
- `create(goal, hour?, status?)` - Create hourly goal
- `list(date?, status?)` - List hourly goals
- `update(goal_id, status?, notes?)` - Update goal progress
- `stats(period?)` - Get goal statistics

### litellm
Manage LiteLLM proxy, spend tracking, and provider balances.

```yaml
skill: litellm
enabled: true
config:
  api_url: http://litellm:4000
```

**Functions:**
- `models()` - List available LLM models
- `health()` - Check LiteLLM proxy health
- `spend(start?, end?)` - Get spend analytics by day
- `global_spend(start?, end?)` - Get total spend
- `provider_balances()` - Get wallet balances from all providers (Kimi, OpenRouter)

### schedule
Manage scheduled jobs and pending tasks.

```yaml
skill: schedule
enabled: true
config:
  api_url: http://aria-api:8000
```

**Functions:**
- `list_jobs(status?)` - List scheduled jobs
- `tick()` - Get current schedule tick status
- `trigger(force?)` - Manually trigger schedule tick
- `sync()` - Sync jobs from OpenClaw config
- `create_task(task_type, prompt, priority?, context?)` - Create pending task
- `list_tasks(status?)` - List pending tasks
- `update_task(task_id, status?, result?)` - Update task status

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
