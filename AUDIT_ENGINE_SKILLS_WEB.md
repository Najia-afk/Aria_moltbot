# Aria_moltbot — Full Audit Report
> Generated: 2026-02-20

---

## 1. Engine Functions Audit (`aria_engine/`)

### 1.1 `session_manager.py` — `NativeSessionManager`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `create_session()` | Create a new chat session with agent/title/type | `EngineChatSession` (`aria_engine.chat_sessions`) | Yes — `test_engine_sessions.py`, `test_engine_chat.py` |
| `get_session()` | Get session details by ID with message count | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_sessions.py` |
| `list_sessions()` | List sessions with filtering, search, pagination | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_sessions.py` |
| `update_session()` | Update session title and/or metadata | `EngineChatSession` | Partial — no dedicated test, but used in auto_session flow |
| `delete_session()` | Delete session and all messages (CASCADE) | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_sessions.py` |
| `end_session()` | Mark session as ended (set `ended=true` in metadata) | `EngineChatSession` | Yes — `test_engine_sessions.py` |
| `add_message()` | Add a message to a session, touch updated_at | `EngineChatSession`, `EngineChatMessage` | Indirectly via `test_engine_chat.py` (send_message) |
| `get_messages()` | Get messages for a session with pagination/since filter | `EngineChatMessage` | Yes — `test_engine_sessions.py` |
| `delete_message()` | Delete a single message by ID+session_id | `EngineChatMessage` | **No dedicated test** |
| `prune_old_sessions()` | Delete sessions older than N days with no activity | `EngineChatSession`, `EngineChatMessage` | **No dedicated test** |
| `get_stats()` | Get aggregate session statistics | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_sessions.py` |

**Called by:** API routers (`engine_sessions.py`, `engine_chat.py`), `AutoSessionManager`, `ChatEngine`.

---

### 1.2 `scheduler.py` — `EngineScheduler`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `parse_schedule()` | Parse cron/interval string into APScheduler trigger | None (pure logic) | Indirectly via cron CRUD tests |
| `start()` | Initialize APScheduler with PG datastore, load jobs | `EngineCronJob` | Indirectly — `test_engine_cron.py` |
| `stop()` | Gracefully stop scheduler, cancel active jobs | None | **No dedicated test** |
| `_load_jobs_from_db()` | Load enabled cron jobs from DB, register with APScheduler | `EngineCronJob` | Internal, tested via start() |
| `_execute_job()` | Execute a job with timeout, retry, backoff | `EngineCronJob` | Indirectly via trigger tests |
| `_dispatch_to_agent()` | Route job to agent (prompt/skill/pipeline types) | None (delegates to AgentPool) | **No unit test** |
| `_update_job_state()` | Update job execution state in DB | `EngineCronJob` | Internal |
| `add_job()` | Add a new cron job to DB + APScheduler | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `update_job()` | Update job in DB, re-register with APScheduler | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `remove_job()` | Delete job from DB + APScheduler | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `trigger_job()` | Manually trigger a job immediately | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `get_job()` | Get single job by ID | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `list_jobs()` | List all cron jobs with state | `EngineCronJob` | Yes — `test_engine_cron.py` |
| `get_job_history()` | Get execution history from activity_log | `ActivityLog` (`activity_log`) | Yes — `test_engine_cron.py` |
| `is_running` | Property: whether scheduler is running | None | Yes — `test_engine_cron.py` |
| `get_status()` | Get scheduler status summary | None (in-memory) | Yes — `test_engine_cron.py` |

**Called by:** API router (`engine_cron.py`), heartbeat registration.

---

### 1.3 `heartbeat.py` — `AgentHeartbeatManager`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `configure_agent()` | Configure heartbeat interval for an agent | None (in-memory config) | **No unit test** |
| `register_all_agents()` | Discover agents from DB, register heartbeat cron jobs | `EngineAgentState` | **No unit test** |
| `heartbeat_handler()` | Execute single heartbeat: update last_active, health checks | `EngineAgentState` + HTTP POST to `/heartbeat` | Indirectly via `test_operations.py` |
| `_record_heartbeat_to_db()` | Record heartbeat via API (httpx POST) | `heartbeat_log` (via API) | Indirectly |
| `_update_last_active()` | Update agent's last_active_at timestamp | `EngineAgentState` | Internal |
| `_set_agent_status()` | Update agent status + failure count | `EngineAgentState` | Internal |
| `_check_agent_health()` | Check if agent exists in AgentPool | None (in-memory) | Internal |
| `_check_llm_health()` | Check LLM circuit breaker state | None (in-memory) | Internal |
| `_check_subsystems()` | Check DB connectivity for main agent | Direct SQL `SELECT 1` | Internal |
| `check_all_health()` | Check health of all agents, detect missed beats | `EngineAgentState` | **No dedicated test** |
| `get_status()` | Get heartbeat manager status summary | None (in-memory) | **No dedicated test** |

**Called by:** Scheduler (cron), API health endpoints.

---

### 1.4 `agent_pool.py` — `AgentPool`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `load_agents()` | Load all agents from DB into in-memory pool | `EngineAgentState` | Indirectly via `test_engine_agents.py` |
| `spawn_agent()` | Create new agent (DB upsert + in-memory) | `EngineAgentState` | **No dedicated test** |
| `get_agent()` | Get agent by ID from in-memory pool | None | Yes — `test_engine_agents.py` |
| `get_skill()` | Get skill by name from registry | None | **No dedicated test** |
| `terminate_agent()` | Cancel tasks, persist final state, remove from pool | `EngineAgentState` | **No dedicated test** |
| `list_agents()` | Get summary of all agents | None (in-memory) | Yes — `test_engine_agents.py` |
| `process_with_agent()` | Process message with concurrency semaphore | `EngineAgentState` (persist state) | **No dedicated test** |
| `run_parallel()` | Run multiple agent tasks in parallel via TaskGroup | `EngineAgentState` | **No dedicated test** |
| `set_llm_gateway()` | Set LLM gateway for all agents | None | **No test** |
| `set_skill_registry()` | Set skill registry for tool resolution | None | **No test** |
| `_persist_agent_state()` | Persist runtime state to DB | `EngineAgentState` | Internal |
| `get_status()` | Get pool status summary | None (in-memory) | Yes — `test_engine_agents.py` |
| `shutdown()` | Shutdown all agents | `EngineAgentState` | **No test** |

**Called by:** API router (`engine_agents.py`), scheduler dispatch, heartbeat, ChatEngine.

---

### 1.5 `chat_engine.py` — `ChatEngine`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `create_session()` | Create chat session with model/prompt config | `EngineChatSession` | Yes — `test_engine_chat.py` |
| `resume_session()` | Resume session, load message history | `EngineChatSession`, `EngineChatMessage` | **No dedicated test** |
| `end_session()` | End session (status=ended, set ended_at) | `EngineChatSession` | Indirectly |
| `send_message()` | Full chat flow: persist user msg → LLM → tool loop → persist assistant msg → update counters | `EngineChatSession`, `EngineChatMessage`, `EngineAgentState` (skills lookup) | Yes — `test_engine_chat.py` |
| `_build_context()` | Build conversation context from recent DB messages | `EngineChatMessage` | Internal |
| `_generate_title()` | Generate session title from first message | None (pure logic) | Internal |

**Called by:** API router (`engine_chat.py`). Core chat flow.

---

### 1.6 `routing.py` — `AgentRouter`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `compute_specialty_match()` | Compute message-to-agent specialty fit (0-1) | None (pure logic) | **No unit test** |
| `compute_load_score()` | Compute load score from status/failures | None (pure logic) | **No unit test** |
| `compute_pheromone_score()` | Compute pheromone from interaction history | None (pure logic) | **No unit test** |
| `route_message()` | Route message to best agent via multi-factor scoring | `EngineAgentState` | **No dedicated test** |
| `get_fallback_chain()` | Build fallback chain: primary → fallback → parent | `EngineAgentState` | **No dedicated test** |
| `update_scores()` | Update pheromone scores after interaction, persist | `EngineAgentState` | **No dedicated test** |
| `_load_agent_states()` | Load agent states from DB | `EngineAgentState` | Internal |
| `_persist_score()` | Persist pheromone score to DB | `EngineAgentState` | Internal |
| `get_routing_table()` | Get full routing table with scores | `EngineAgentState` | **No dedicated test** |

**Called by:** ChatEngine (agent selection), API (routing table display). **⚠️ NO TEST COVERAGE.**

---

### 1.7 `auto_session.py` — `AutoSessionManager`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `generate_auto_title()` | Generate title from first message (module function) | None (pure logic) | **No unit test** |
| `ensure_session_and_message()` | Auto-create session on first msg, handle rotation | `EngineChatSession`, `EngineChatMessage` (via NativeSessionManager) | **No dedicated test** |
| `_needs_rotation()` | Check if session exceeded limits | None (checks session dict) | Internal |
| `_maybe_auto_title()` | Auto-title session if generic name | `EngineChatSession` (via NativeSessionManager) | Internal |
| `close_idle_sessions()` | Close sessions idle beyond timeout | `EngineChatSession` | **No dedicated test** |
| `get_or_create_session()` | Get active session or create new one | `EngineChatSession` (via NativeSessionManager) | **No dedicated test** |

**Called by:** Chat flow (transparent session creation), Scheduler (idle scanner). **⚠️ NO TEST COVERAGE.**

---

### 1.8 `session_protection.py` — `SessionProtection`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `validate_and_check()` | Validate content + rate limit + session size check | `EngineChatMessage` (count query) | **No dedicated test** |
| `sanitize_content()` | Strip control chars, normalize whitespace | None (pure logic) | **No unit test** |
| `_check_injection()` | Detect prompt injection patterns (log only) | None (pure logic) | **No unit test** |
| `_get_session_message_count()` | Get message count for a session | `EngineChatMessage` | Internal |
| `session_lock()` | Get advisory lock for concurrent write safety | None (asyncio.Lock) | **No dedicated test** |
| `cleanup_windows()` | Clean stale rate limiter windows | None (in-memory) | **No dedicated test** |
| `get_rate_limit_status()` | Get current rate limit status | None (in-memory) | **No dedicated test** |

**Called by:** Chat flow (pre-message validation). **⚠️ NO TEST COVERAGE.**

---

### 1.9 `cross_session.py` — `CrossSessionContext`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `generate_embedding()` | Generate embedding via litellm (module function) | None (external API) | **No unit test** |
| `load_context()` | Load cross-session context via vector/keyword search | `EngineChatMessage`, `EngineChatSession` | **No dedicated test** |
| `_vector_search()` | pgvector cosine similarity search | `EngineChatMessage` (embedding column), `EngineChatSession` | Internal |
| `_keyword_search()` | ILIKE keyword fallback search | `EngineChatMessage`, `EngineChatSession` | Internal |
| `embed_message()` | Generate and store embedding for a message | `EngineChatMessage` | **No dedicated test** |
| `backfill_embeddings()` | Batch embed unembedded messages | `EngineChatMessage` | **No dedicated test** |
| `_has_embeddings()` | Check if agent has any embeddings | `EngineChatMessage` | Internal |
| `_trim_to_token_budget()` | Trim messages to token budget | None (pure logic) | **No unit test** |
| `_estimate_tokens()` | Estimate token count from char count | None (pure logic) | **No unit test** |

**Called by:** ChatEngine (context building). **⚠️ NO TEST COVERAGE.**

---

### 1.10 `llm_gateway.py` — `LLMGateway`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `complete()` | Send completion request to LLM via litellm | None (external API) | Indirectly via `test_engine_chat.py` (send_message) |
| `stream()` | Stream completion response chunk-by-chunk | None (external API) | **No dedicated test** |
| `get_stats()` | Return gateway stats (circuit breaker, latency) | None (in-memory) | **No dedicated test** |
| `_resolve_model()` | Resolve model alias to litellm model string + kwargs | None (reads models.yaml) | **No unit test** |
| `_get_fallback_chain()` | Get fallback model chain from models.yaml | None (reads config) | **No unit test** |
| `_is_circuit_open()` | Check circuit breaker state | None (in-memory) | **No unit test** |

**Called by:** ChatEngine, AgentPool (EngineAgent.process). **⚠️ Minimal test coverage.**

---

### 1.11 `tool_registry.py` — `ToolRegistry`

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `discover_from_skills()` | Auto-discover tools from skill.json manifests + registry | None (reads filesystem) | **No dedicated test** |
| `discover_from_manifests()` | Discover from skill.json only (lazy handlers) | None (reads filesystem) | **No dedicated test** |
| `register_tool()` | Manually register a tool | None (in-memory) | **No dedicated test** |
| `get_tools_for_llm()` | Get OpenAI-format tool definitions for LLM | None (in-memory) | **No dedicated test** |
| `execute()` | Execute a tool call with timeout | None (delegates to skills) | Indirectly via chat send_message |
| `list_tools()` | List all registered tools | None (in-memory) | **No dedicated test** |
| `_lazy_import_handler()` | Lazy-import and bind skill handler on first call | None (dynamic import) | Internal |

**Called by:** ChatEngine (tool calling loop). **⚠️ NO TEST COVERAGE.**

---

### 1.12 `metrics.py` — `AriaMetrics` + helpers

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `AriaMetrics.__init__()` | Define all Prometheus counters/gauges/histograms | None (Prometheus registry) | **No unit test** |
| `track_request()` | Decorator to track request duration/status | None (Prometheus) | **No unit test** |
| `track_llm()` | Decorator to track LLM call metrics | None (Prometheus) | **No unit test** |
| `start_metrics_server()` | Start Prometheus HTTP server on port 8081 | None | **No test** |
| `update_system_metrics()` | Update RSS/GC metrics (call every 30s) | None (psutil) | **No test** |

**Called by:** Entrypoint (startup), decorators on API handlers. **⚠️ NO TEST COVERAGE.**

---

### 1.13 `export.py` — Session export functions

| Method | Description | DB Models/Tables | Tested? |
|--------|-------------|------------------|---------|
| `export_session_jsonl()` | Export session as JSONL (OpenAI format) | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_chat.py`, `test_cross_entity.py` |
| `export_session_markdown()` | Export session as human-readable Markdown | `EngineChatSession`, `EngineChatMessage` | Yes — `test_engine_chat.py` |
| `export_session()` | Dispatcher: delegates to jsonl or markdown | None (delegates) | Indirectly |
| `parse_jsonl_line()` | Parse a single JSONL line back to dict | None (pure logic) | **No unit test** |
| `read_jsonl_file()` | Read JSONL file, return message list | None (filesystem) | **No unit test** |

**Called by:** API router (`engine_chat.py`, export endpoint).

---

### Engine DB Models Summary

| Model | Table | Schema | Used By |
|-------|-------|--------|---------|
| `EngineChatSession` | `chat_sessions` | `aria_engine` | session_manager, chat_engine, auto_session, export, cross_session |
| `EngineChatMessage` | `chat_messages` | `aria_engine` | session_manager, chat_engine, session_protection, cross_session, export |
| `EngineCronJob` | `cron_jobs` | `aria_engine` | scheduler |
| `EngineAgentState` | `agent_state` | `aria_engine` | agent_pool, heartbeat, routing, chat_engine (skills lookup) |
| `ActivityLog` | `activity_log` | `public` | scheduler (job history) |
| `EngineConfigEntry` | `config` | `aria_engine` | Not directly used by engine modules |
| `EngineAgentTool` | `agent_tools` | `aria_engine` | Not directly used by engine modules |

---

## 2. Skills Audit (`aria_skills/`)

### How Skills Load

1. **`SkillRegistry.register()`** — class decorator registers skill classes
2. **`SkillRegistry.load_from_config(config_path)`** — parses `TOOLS.md` YAML blocks, instantiates + initializes registered classes
3. **`ToolRegistry.discover_from_manifests()`** — reads `skill.json` from each skill folder, builds LLM function-calling definitions
4. Skills access DB **only via `api_client` (httpx → FastAPI)** — no direct SQL

### Skill Inventory

| # | Skill | Handler | Description | DB Access | Tested? |
|---|-------|---------|-------------|-----------|---------|
| 1 | **moltbook** | `moltbook/__init__.py` | Social network — post, comment, vote, search | Via api_client → `social_posts` | `test_social.py` |
| 2 | **moonshot** | `moonshot/__init__.py` | Moonshot/Kimi LLM chat completion | None (external API) | `test_litellm.py` (partial) |
| 3 | **ollama** | `ollama/__init__.py` | Local Ollama LLM — generate, chat, list models | None (local HTTP) | `test_litellm.py` (partial) |
| 4 | **health** | `health/__init__.py` + `diagnostics.py`, `patterns.py`, `playbooks.py`, `recovery.py` | System health checks, diagnostics, auto-recovery | Via api_client → `performance_log` | `test_health.py` |
| 5 | **goals** | `goals/__init__.py` | Goal CRUD, habits, subtasks, progress tracking | Via api_client → `goals` | `test_goals.py` |
| 6 | **knowledge_graph** | `knowledge_graph/__init__.py` | Build/query knowledge graph (entities + relations) | Via api_client → `knowledge_entities`, `knowledge_relations` | `test_knowledge.py` |
| 7 | **pytest_runner** | `pytest_runner/__init__.py` | Run pytest, return structured results | None (subprocess) | **No dedicated test** |
| 8 | **performance** | `performance/__init__.py` | Log/query performance reviews | Via api_client → `performance_log` | **No dedicated test** |
| 9 | **social** | `social/__init__.py` + `platform.py`, `telegram.py` | Multi-platform social posting | Via api_client → `social_posts` | `test_social.py` |
| 10 | **hourly_goals** | `hourly_goals/__init__.py` | Short-term hourly goal management | Via api_client → `hourly_goals` | **No dedicated test** |
| 11 | **litellm** | `litellm/__init__.py` | LiteLLM proxy management, model listing | Via HTTP → LiteLLM proxy | `test_litellm.py` |
| 12 | **schedule** | `schedule/__init__.py` | Manage scheduled jobs/tasks | Via api_client → `scheduled_jobs` | **No dedicated test** |
| 13 | **security_scan** | `security_scan/__init__.py` | Code/config security scanning | None (static analysis) | `test_security.py` (partial) |
| 14 | **ci_cd** | `ci_cd/__init__.py` | CI/CD workflow generation, Dockerfile gen | None (pure logic) | **No dedicated test** |
| 15 | **data_pipeline** | `data_pipeline/__init__.py` | ETL pipeline definition, data validation | None (pure logic) | **No dedicated test** |
| 16 | **input_guard** | `input_guard/__init__.py` | Runtime input protection — injection detection, SQL safety | Via api_client → `security_events` (logging) | `test_security.py` (partial) |
| 17 | **api_client** | `api_client/__init__.py` | Centralized HTTP client (httpx) for all API calls | Gateway to all DB tables via FastAPI | Indirectly via all skills |
| 18 | **market_data** | `market_data/__init__.py` | Crypto market data (CoinGecko) | None (external API) | **No dedicated test** |
| 19 | **portfolio** | `portfolio/__init__.py` | Crypto portfolio/position management | In-memory (no DB) | **No dedicated test** |
| 20 | **research** | `research/__init__.py` | Research project management | Via api_client → `memories` | **No dedicated test** |
| 21 | **pipeline_skill** | `pipeline_skill/__init__.py` | Cognitive multi-step pipeline workflows | Delegates to other skills | **No dedicated test** |
| 22 | **agent_manager** | `agent_manager/__init__.py` | Agent lifecycle: spawn, monitor, terminate, prune | Via api_client → engine endpoints | `test_engine_agents.py` (partial) |
| 23 | **sandbox** | `sandbox/__init__.py` | Sandboxed code execution (run_code, write_file) | Via api_client (logging) | **No dedicated test** |
| 24 | **telegram** | `telegram/__init__.py` | Telegram Bot API integration | None (external API) | **No dedicated test** |
| 25 | **working_memory** | `working_memory/__init__.py` | Key/value working memory (persistent) | Via api_client → `working_memory` table | `test_working_memory.py` |
| 26 | **memory_compression** | `memory_compression/__init__.py` | 3-tier hierarchical memory compression | Via api_client → `memories` | `test_advanced_memory.py` (partial) |
| 27 | **sentiment_analysis** | `sentiment_analysis/__init__.py` | Multi-dimensional sentiment analysis (VAD model) | Via api_client → `sentiment_events` | **No dedicated test** |
| 28 | **pattern_recognition** | `pattern_recognition/__init__.py` | Detect behavioral patterns in memory streams | Via api_client → `memories` | **No dedicated test** |
| 29 | **unified_search** | `unified_search/__init__.py` | Unified search across semantic/graph/traditional memory | Via api_client → multiple tables | **No dedicated test** |
| 30 | **conversation_summary** | `conversation_summary/__init__.py` | Summarize conversations into durable memories | Via api_client → `memories` | **No dedicated test** |
| 31 | **memeothy** | `memeothy/__init__.py` | Church of Molt / Crustafarianism cult game | In-memory (no DB) | **No dedicated test** |
| 32 | **session_manager** | `session_manager/__init__.py` | Two-layer session management (filesystem + API) | Via api_client → `agent_sessions` | `test_sessions.py` |
| 33 | **sprint_manager** | `sprint_manager/__init__.py` | Sprint planning and goal management | Via api_client → `goals` | **No dedicated test** |
| 34 | **llm** | `llm/__init__.py` | Multi-provider LLM access (Moonshot, Ollama, OpenRouter) | None (external APIs) | **No dedicated test** |
| 35 | **model_switcher** | (no `__init__.py`) | Switch LLM models, toggle thinking mode | None | **No handler — manifest only** |
| 36 | **brainstorm** | (no `__init__.py`) | Creative brainstorming/ideation | None | **No handler — manifest only** |
| 37 | **community** | (no `__init__.py`) | Community management and growth | None | **No handler — manifest only** |
| 38 | **database** | (no `__init__.py`) | Self-healing database operations | None | **No handler — manifest only** |
| 39 | **experiment** | (no `__init__.py`) | ML experiment tracking | None | **No handler — manifest only** |
| 40 | **fact_check** | (no `__init__.py`) | Fact-checking and claim verification | None | **No handler — manifest only** |

**Skills without Python implementation (manifest-only):** `brainstorm`, `community`, `database`, `experiment`, `fact_check`, `model_switcher`.  
These have `skill.json` but no `__init__.py` — tools will fail at execution time.

---

## 3. Web Routes & Pages

### 3.1 Flask Web App (`src/web/app.py`)

The web app is UI-only. All data flows through the API proxy route:
- **`/api/<path>`** — Reverse proxy to FastAPI backend (all methods)

#### Page Routes

| Route | Template | Description | API Endpoints Called |
|-------|----------|-------------|---------------------|
| `/` | `index.html` | Main dashboard | `/api/health`, `/api/activities`, `/api/stats` |
| `/activities` | `activities.html` | Activity log | `/api/activities` |
| `/activity-visualization`, `/creative-pulse` | `creative_pulse.html` | Activity visualization | `/api/activities` |
| `/thoughts` | `thoughts.html` | Thought log | `/api/thoughts` |
| `/memories` | `memories.html` | Memory browser | `/api/memories` |
| `/sentiment` | `sentiment.html` | Sentiment dashboard | `/api/sentiment` |
| `/patterns` | `patterns.html` | Pattern visualization | `/api/patterns`, `/api/memories` |
| `/records` | `records.html` | Records & export | `/api/records`, `/api/export` |
| `/search` | `search.html` | Universal search | `/api/search`, `/api/memories`, `/api/knowledge` |
| `/services` | `services.html` | Service status | `/api/health`, `/api/status` |
| `/models` | `models.html` | Model management (merged LiteLLM) | `/api/litellm/models`, `/api/models` |
| `/models/manager` | `models_manager.html` | Model CRUD manager | `/api/models` |
| `/agents/manager` | `agent_manager.html` | Agent CRUD manager | `/api/agents`, `/api/engine/agents` |
| `/sprint-board`, `/goals` | `sprint_board.html` | Sprint/goal board | `/api/goals` |
| `/heartbeat` | `heartbeat.html` | Heartbeat monitor | `/api/heartbeat` |
| `/knowledge` | `knowledge.html` | Knowledge graph | `/api/knowledge` |
| `/skill-graph` | `skill_graph.html` | Skill dependency graph | `/api/skills` |
| `/social` | `social.html` | Social feed | `/api/social` |
| `/performance` | `performance.html` | Performance dashboard | `/api/performance` |
| `/security` | `security.html` | Security events | `/api/security` |
| `/sessions` | `sessions.html` | Legacy session browser | `/api/sessions` |
| `/working-memory` | `working_memory.html` | Working memory UI | `/api/working-memory` |
| `/skills` | `skills.html` | Skill catalog | `/api/skills` |
| `/proposals` | `proposals.html` | Proposal board | `/api/proposals` |
| `/skill-stats` | `skill_stats.html` | Skill performance stats | `/api/skills/stats` |
| `/skill-health` | `skill_health.html` | Skill health dashboard | `/api/skills/health` |
| `/soul` | `soul.html` | Soul/identity page | `/api/soul` |
| `/model-usage` | `model_usage.html` | Model usage analytics | `/api/model-usage` |
| `/cron` | `engine_cron.html` | Cron job management | `/api/engine/cron` |
| `/agents` | `engine_agents.html` | Agent pool dashboard | `/api/engine/agents` |
| `/agent-dashboard` | `engine_agent_dashboard.html` | Agent performance dashboard | `/api/engine/agents`, `/api/engine/agent-metrics` |
| `/rate-limits` | `rate_limits.html` | Rate limit viewer | `/api/rate-limits` |
| `/api-key-rotations` | `api_key_rotations.html` | API key rotation | `/api/security` |
| `/operations` | `operations.html` | Operations hub | Multiple engine API endpoints |
| `/operations/cron/` | `engine_operations.html` | Cron operations | `/api/engine/cron` |
| `/operations/agents/` | `engine_agents_mgmt.html` | Agent management | `/api/engine/agents` |
| `/operations/agents/<id>/prompt` | `engine_prompt_editor.html` | Agent prompt editor | `/api/engine/agents/{id}` |
| `/operations/health/` | `engine_health.html` | Engine health | `/api/health`, `/api/engine/agents` |
| `/chat/`, `/chat/<session_id>` | `engine_chat.html` | Native chat UI | `/api/engine/chat/sessions`, WebSocket |
| `/clawdbot/` | (redirect) | Legacy redirect → `/chat/` | N/A |
| `/litellm` | (redirect) | Redirect → `/models` | N/A |
| `/dashboard` | (redirect) | Redirect → `/` | N/A |
| `/wallets` | (redirect) | Redirect → `/models` | N/A |

### 3.2 FastAPI Routers (`src/api/routers/`)

| Router File | Prefix | Key Endpoints |
|-------------|--------|---------------|
| `health.py` | `/health` | `GET /`, `GET /db`, `GET /stats`, `GET /status` |
| `activities.py` | `/activities` | CRUD for activity log |
| `thoughts.py` | `/thoughts` | CRUD for thought entries |
| `memories.py` | `/memories` | CRUD for memories |
| `goals.py` | `/goals` | CRUD for goals/habits |
| `sessions.py` | `/sessions` | Legacy session CRUD |
| `model_usage.py` | `/model-usage` | Model usage tracking |
| `litellm.py` | `/litellm` | LiteLLM proxy management |
| `providers.py` | `/providers` | Provider config |
| `security.py` | `/security` | Security events |
| `knowledge.py` | `/knowledge` | Knowledge graph CRUD |
| `social.py` | `/social` | Social post CRUD |
| `operations.py` | `/operations` | Tasks, heartbeat, rate limits, jobs |
| `records.py` | `/records` | Records, search, export |
| `admin.py` | `/admin` | Admin operations |
| `models_config.py` | `/models` | Model config CRUD |
| `models_crud.py` | `/models` | Model CRUD |
| `working_memory.py` | `/working-memory` | Working memory KV store |
| `skills.py` | `/skills` | Skill stats, health, invocations |
| `lessons.py` | `/lessons` | Lesson log |
| `proposals.py` | `/proposals` | Proposal CRUD |
| `analysis.py` | `/analysis` | Analysis endpoints |
| **`engine_cron.py`** | `/engine/cron` | `GET`, `POST`, `GET /status`, `GET /{id}`, `PUT /{id}`, `DELETE /{id}`, `POST /{id}/trigger`, `GET /{id}/history` |
| **`engine_sessions.py`** | `/engine/sessions` | `GET`, `GET /stats`, `GET /{id}`, `GET /{id}/messages`, `DELETE /{id}`, `POST /{id}/end` |
| **`engine_chat.py`** | `/engine/chat` | `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `GET /sessions/{id}/messages`, `POST /sessions/{id}/messages`, `DELETE /sessions/{id}`, `GET /sessions/{id}/export` |
| **`engine_agents.py`** | `/engine/agents` | `GET`, `GET /{id}` |
| **`engine_agent_metrics.py`** | `/engine/agent-metrics` | Agent performance metrics |
| `agents_crud.py` | `/agents` | Agent CRUD (DB level) |
| GraphQL | `/graphql` | GraphQL endpoint |
| `main.py` | `/api/metrics` | Inline Prometheus metrics endpoint |

---

## 4. Test Coverage Summary

### Test Files and What They Cover

| Test File | Covers |
|-----------|--------|
| `test_engine_sessions.py` (9 tests) | NativeSessionManager via API — list, filter, sort, stats, detail, messages, delete, end |
| `test_engine_chat.py` (7 tests) | ChatEngine via API — create session, send message, export JSONL/MD |
| `test_engine_cron.py` (17 tests) | EngineScheduler via API — full CRUD, trigger, history, status, validation |
| `test_engine_agents.py` (5 tests) | AgentPool via API — list, get, metrics |
| `test_operations.py` | Heartbeat flow, tasks, rate limits, jobs, performance |
| `test_sessions.py` (7 tests) | Legacy session CRUD (not engine sessions) |
| `test_health.py` (8 tests) | Health endpoints, stats, metrics |
| `test_skills.py` (11 tests) | Skill invocations, stats, health dashboard |
| `test_goals.py` | Goal CRUD |
| `test_social.py` | Social post CRUD |
| `test_knowledge.py` | Knowledge graph CRUD |
| `test_working_memory.py` | Working memory KV operations |
| `test_web_routes.py` | Flask web page route smoke tests |
| `test_security.py` | Security events and middleware |
| `test_cross_entity.py` | Cross-entity workflows including export |
| `test_websocket.py` | WebSocket connection tests |
| `test_litellm.py` | LiteLLM proxy interactions |

### Critical Gaps (No Test Coverage)

| Module | Functions Missing Tests |
|--------|----------------------|
| **routing.py** | ALL functions — `route_message`, `update_scores`, `get_routing_table`, `get_fallback_chain`, scoring helpers |
| **auto_session.py** | ALL functions — `ensure_session_and_message`, `close_idle_sessions`, `get_or_create_session`, `generate_auto_title` |
| **session_protection.py** | ALL functions — `validate_and_check`, `sanitize_content`, `session_lock`, `cleanup_windows`, `get_rate_limit_status` |
| **cross_session.py** | ALL functions — `load_context`, `embed_message`, `backfill_embeddings`, `generate_embedding` |
| **tool_registry.py** | ALL functions — `discover_from_skills`, `discover_from_manifests`, `execute`, `get_tools_for_llm`, `list_tools` |
| **metrics.py** | ALL functions — AriaMetrics, decorators, server |
| **llm_gateway.py** | `stream()`, `get_stats()`, `_resolve_model()`, circuit breaker logic |
| **agent_pool.py** | `spawn_agent()`, `terminate_agent()`, `process_with_agent()`, `run_parallel()`, `shutdown()` |
| **heartbeat.py** | `register_all_agents()`, `check_all_health()`, `get_status()` |
| **export.py** | `parse_jsonl_line()`, `read_jsonl_file()` |
| **session_manager.py** | `delete_message()`, `prune_old_sessions()` |
