# Aria v2.0 — Operation Independence: The Master Plan

**Project:** Aria Blue — OpenClaw Phase-Out & Standalone Engine  
**Code Name:** Operation Independence  
**Date:** 2026-02-18  
**Architect:** Sprint Agent (Claude Opus 4.6)  
**Product Owner:** Shiva  
**Target:** Python 3.13+ · Docker-first · PostgreSQL-centric · Zero OpenClaw dependency  

---

## Executive Summary

Aria Blue is a sophisticated autonomous AI agent with 45 database tables, 30+ skills, 6 agents, 25+ models, a Flask dashboard with 25+ pages, a FastAPI REST+GraphQL API, and a cognitive architecture (Soul → Cognition → Memory → Heartbeat → Metacognition). Today she runs on OpenClaw — a Node.js gateway that manages sessions, cron jobs, agent spawning, and LLM routing.

**The mission:** Remove OpenClaw entirely while making Aria *better* than she was with it. Every feature OpenClaw provides must be replaced with a native Python engine — faster, more observable, and fully under our control.

This is not a migration. This is an **evolution**.

---

## Current State Analysis

### What OpenClaw Provides Today

| Feature | How OpenClaw Does It | Our Replacement |
|---------|---------------------|-----------------|
| **LLM Gateway** | Proxies to LiteLLM | Native `litellm` Python SDK (already available) |
| **Chat Sessions** | `sessions.json` + `.jsonl` transcripts | PostgreSQL `agent_sessions` + `session_messages` + streaming |
| **Multi-Agent** | Agent profiles in `openclaw.json` | `aria_agents/coordinator.py` + native orchestrator |
| **Cron Jobs** | `openclaw cron add` (Node.js scheduler) | APScheduler + PostgreSQL `scheduled_jobs` + web UI |
| **Heartbeat** | OpenClaw heartbeat system | `aria_mind/heartbeat.py` (already exists, needs activation) |
| **Skill Execution** | `exec python3 run_skill.py` | Direct Python function calls |
| **System Prompt** | Mounted file + OpenClaw identity config | Database-stored prompts + Soul system |
| **Context Window** | OpenClaw manages conversation context | PostgreSQL session history + sliding window |
| **Thinking Mode** | OpenClaw passes thinking tokens | Native thinking token handling via LiteLLM |
| **Tool Calling** | OpenClaw registers skills as tools | Native function-calling via LiteLLM tool_call |
| **Web UI Chat** | Proxied through `/clawdbot/` | Native WebSocket chat endpoint via FastAPI |

### What Works Perfectly (Keep As-Is)

- **FastAPI REST API** (15 routers, 100+ endpoints) — independent from OpenClaw
- **PostgreSQL schema** (45 tables, pgvector, full indexes) — production-grade
- **Flask Dashboard** (25+ pages, Chart.js, vis-network) — only `/clawdbot/` routes need removal
- **Skill Architecture** (30+ skills, 5-layer hierarchy, BaseSkill) — fully portable
- **Agent Framework** (AgentCoordinator, pheromone scoring, roundtable) — needs execution backend
- **Cognitive Architecture** (Soul, Cognition, Memory, Metacognition) — fully portable
- **Model Configuration** (`models.yaml` single source of truth) — framework-agnostic
- **LiteLLM** — already the actual LLM router; OpenClaw was just a proxy layer
- **Security** (input guard, rate limiting, security middleware) — fully portable
- **Knowledge Graph** (entities, relations, skill graph) — fully portable

### What's Broken Today (Production Evidence)

From the Mac Mini production logs (2026-02-18):
1. **"No LLM skill available, returning placeholder"** — Aria tries to reflect but has no LLM access
2. **Reflection loop is repetitive** — Same confidence 0.50, same format, no learning
3. **404 on `/skill-for-task-semantic`** — Semantic skill router endpoint missing
4. **Heartbeat is just counting** — 2460 beats but doing nothing productive
5. **No actual work cycles running** — despite 15 cron jobs defined, they need OpenClaw to execute
6. **Session sync is one-directional** — reads OpenClaw files but never writes back

---

## Architecture: Aria Engine

The new architecture introduces `aria_engine` — a standalone Python-native runtime that replaces OpenClaw.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ARIA ENGINE (New)                           │
│  Python 3.13+ · asyncio · PostgreSQL-centric · No Node.js          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  CHAT ENGINE │  │   SCHEDULER  │  │  AGENT POOL  │              │
│  │  WebSocket   │  │  APScheduler │  │  Async Tasks │              │
│  │  Streaming   │  │  DB-backed   │  │  Max 5 conc. │              │
│  │  Thinking    │  │  Web-managed │  │  Pheromone    │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                 │                       │
│  ┌──────┴─────────────────┴─────────────────┴───────┐              │
│  │              CONTEXT MANAGER                       │              │
│  │  Session history · Sliding window · JSONL export   │              │
│  │  Agent tabs · System prompt assembly · Tools        │              │
│  └──────────────────────┬────────────────────────────┘              │
│                         │                                           │
│  ┌──────────────────────┴────────────────────────────┐              │
│  │              LLM GATEWAY (Direct LiteLLM)          │              │
│  │  litellm.acompletion() · Tool calling · Streaming  │              │
│  │  Model routing from models.yaml · Fallback chains  │              │
│  │  Token counting · Cost tracking · Rate limiting    │              │
│  └──────────────────────┬────────────────────────────┘              │
│                         │                                           │
│  ┌──────────────────────┴────────────────────────────┐              │
│  │              PostgreSQL (aria_warehouse)            │              │
│  │  45 tables · pgvector · aria_engine schema (new)   │              │
│  │  Sessions · Messages · Cron state · Agent state    │              │
│  └────────────────────────────────────────────────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### New PostgreSQL Schema: `aria_engine`

```sql
-- New schema for engine-specific tables (keeps public schema intact)
CREATE SCHEMA IF NOT EXISTS aria_engine;

-- Chat sessions managed by the engine (replaces OpenClaw sessions.json)
CREATE TABLE aria_engine.chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL DEFAULT 'main',
    session_type VARCHAR(50) NOT NULL DEFAULT 'interactive',
    title VARCHAR(500),
    system_prompt TEXT,
    model VARCHAR(200),
    temperature FLOAT DEFAULT 0.7,
    max_tokens INT DEFAULT 4096,
    context_window INT DEFAULT 50,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    message_count INT DEFAULT 0,
    total_tokens INT DEFAULT 0,
    total_cost NUMERIC(10,6) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- Chat messages with full history (replaces .jsonl transcripts)
CREATE TABLE aria_engine.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES aria_engine.chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system, tool
    content TEXT NOT NULL,
    thinking TEXT,  -- thinking/reasoning tokens (if model supports)
    tool_calls JSONB,  -- function calling payloads
    tool_results JSONB,  -- tool execution results
    model VARCHAR(200),
    tokens_input INT,
    tokens_output INT,
    cost NUMERIC(10,6),
    latency_ms INT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cron jobs managed by the engine (replaces OpenClaw cron)
CREATE TABLE aria_engine.cron_jobs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    schedule VARCHAR(100) NOT NULL,  -- cron expression
    agent_id VARCHAR(100) DEFAULT 'main',
    enabled BOOLEAN DEFAULT true,
    payload_type VARCHAR(50) DEFAULT 'prompt',  -- prompt, skill, pipeline
    payload TEXT NOT NULL,
    session_mode VARCHAR(50) DEFAULT 'isolated',  -- isolated, shared, persistent
    max_duration_seconds INT DEFAULT 300,
    retry_count INT DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    last_status VARCHAR(20),
    last_duration_ms INT,
    last_error TEXT,
    next_run_at TIMESTAMPTZ,
    run_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agent runtime state (replaces OpenClaw agent directories)
CREATE TABLE aria_engine.agent_state (
    agent_id VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(200),
    model VARCHAR(200) NOT NULL,
    temperature FLOAT DEFAULT 0.7,
    max_tokens INT DEFAULT 4096,
    system_prompt TEXT,
    focus_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'idle',  -- idle, busy, error, disabled
    current_session_id UUID REFERENCES aria_engine.chat_sessions(id),
    current_task TEXT,
    consecutive_failures INT DEFAULT 0,
    pheromone_score NUMERIC(5,3) DEFAULT 0.500,
    last_active_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Engine configuration (key-value store for runtime settings)
CREATE TABLE aria_engine.config (
    key VARCHAR(200) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'system'
);

-- Skill tool definitions (what tools each agent can call)
CREATE TABLE aria_engine.agent_tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL REFERENCES aria_engine.agent_state(agent_id),
    skill_name VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    description TEXT,
    parameters JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Sprint Plan — 12 Sprints, 8 Epics

### Sprint Philosophy
- **Each sprint is isolated** — one PM, swarm per ticket, independent deployment
- **Each sprint has a Docker-verifiable deliverable** — `docker compose up` must work
- **Each sprint has rollback safety** — feature flags, backward compatibility
- **Quality over speed** — no shortcuts, full test coverage, AA+ tickets

---

### Epic 1: Foundation — Aria Engine Core (Sprints 1-2)

> Build the standalone Python engine that replaces OpenClaw's runtime

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 1** | Engine skeleton + LLM gateway | 6 | 16h |
| **Sprint 2** | Chat engine + WebSocket streaming | 6 | 18h |

**Sprint 1 — Engine Bootstrap**
- S1-01: Create `aria_engine/` package structure with `__init__.py`, `config.py`, `exceptions.py`
- S1-02: Implement `LLMGateway` class — direct `litellm.acompletion()` with model routing from `models.yaml`
- S1-03: Implement thinking token handling (Qwen3, Claude extended thinking format)
- S1-04: Implement tool calling bridge — translate `aria_skills` functions to LiteLLM `tools` format
- S1-05: Create Alembic migration for `aria_engine` schema (6 new tables)
- S1-06: Docker entrypoint for `aria-brain` container (replaces `openclaw-entrypoint.sh`)

**Sprint 2 — Chat Engine**
- S2-01: Implement `ChatEngine` — session lifecycle (create/resume/end)
- S2-02: Implement context window manager — sliding window with importance-based eviction
- S2-03: Implement streaming responses via FastAPI WebSocket
- S2-04: Implement JSONL transcript export per session (backward compatible)
- S2-05: Implement system prompt assembly (Soul + Focus + Agent config + context)
- S2-06: Add chat endpoints to `src/api/routers/` — REST + WebSocket

---

### Epic 2: Scheduler & Heartbeat (Sprint 3)

> Replace OpenClaw cron with a native Python scheduler managed from the web UI

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 3** | APScheduler + cron web UI | 5 | 14h |

**Sprint 3 — Native Scheduler**
- S3-01: Integrate APScheduler with PostgreSQL job store (`aria_engine.cron_jobs`)
- S3-02: Migrate all 15 cron jobs from `cron_jobs.yaml` to DB-backed scheduler
- S3-03: Create cron CRUD API endpoints (create/read/update/delete/toggle/trigger)
- S3-04: Create web UI page for cron management (list, toggle, manual trigger, history)
- S3-05: Wire heartbeat system to scheduler — agent-specific heartbeats with health checks

---

### Epic 3: Multi-Agent Orchestration (Sprint 4)

> Build the native agent pool with session isolation, agent tabs, and thinking support

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 4** | Agent pool + orchestration | 6 | 20h |

**Sprint 4 — Agent Pool**
- S4-01: Implement `AgentPool` — async agent lifecycle (spawn/track/terminate)
- S4-02: Implement per-agent session isolation with `aria_engine.chat_sessions`
- S4-03: Implement agent tabs in web UI (list agents, view active sessions, switch)
- S4-04: Implement agent auto-routing with pheromone scoring from `aria_agents/scoring.py`
- S4-05: Implement roundtable discussions (multi-agent collaboration via coordinator)
- S4-06: Implement agent performance dashboard updates (live pheromone scores, success rates)

---

### Epic 4: Session Management & Context (Sprint 5)

> Native session management replacing OpenClaw's filesystem-based sessions

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 5** | Session lifecycle + context loading | 5 | 16h |

**Sprint 5 — Session Intelligence**
- S5-01: Rewrite `session_manager` skill — PostgreSQL-only, no filesystem dependency
- S5-02: Implement auto-session management (create on first message, close on inactivity)
- S5-03: Implement session history loading with pagination and search
- S5-04: Implement context loading from previous sessions (cross-session memory)
- S5-05: Implement session protection in engine (prevent deletion of active sessions)

---

### Epic 5: Web Dashboard Evolution (Sprints 6-7)

> Make the dashboard match OpenClaw's capabilities for chat, cron, and agent management

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 6** | Chat UI + session management | 6 | 18h |
| **Sprint 7** | Full ops dashboard + cron UI | 5 | 14h |

**Sprint 6 — Chat Interface**
- S6-01: Build web chat UI with WebSocket streaming (markdown rendering, code blocks)
- S6-02: Implement thinking token display (collapsible reasoning panel)
- S6-03: Implement session sidebar (list, create, resume, delete sessions)
- S6-04: Implement model selector (dropdown from `models.yaml`, agent auto-routing)
- S6-05: Implement tool call visualization (show skill invocations inline in chat)
- S6-06: Remove all OpenClaw proxy routes from `src/web/app.py`

**Sprint 7 — Operations Dashboard**
- S7-01: Build cron management page (CRUD, toggle, manual trigger, execution history)
- S7-02: Build agent management page (list agents, view state, configure, restart)
- S7-03: Build system prompt editor (edit per-agent prompts from web UI)
- S7-04: Update operations.html to use native cron data instead of OpenClaw
- S7-05: Build engine health dashboard (LLM gateway status, scheduler status, agent pool)

---

### Epic 6: Migration & Cleanup (Sprint 8)

> Remove all OpenClaw code, migrate production data, update all references

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 8** | OpenClaw removal + data migration | 6 | 12h |

**Sprint 8 — OpenClaw Exorcism**
- S8-01: Remove `clawdbot` service from `docker-compose.yml`
- S8-02: Remove `openclaw-entrypoint.sh`, `openclaw-config.json`, `openclaw-auth-profiles.json`
- S8-03: Remove `aria_models/openclaw_config.py`
- S8-04: Clean `src/api/config.py` — remove OPENCLAW_* constants
- S8-05: Clean `src/api/routers/sessions.py` — remove OpenClaw sync logic
- S8-06: Data migration script: existing `agent_sessions` → `aria_engine.chat_sessions`

---

### Epic 7: Python 3.13+ Modernization (Sprint 9)

> Upgrade to Python 3.13+ with modern patterns throughout

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 9** | Python 3.13 upgrade + modernization | 5 | 10h |

**Sprint 9 — Modernization**
- S9-01: Update `pyproject.toml` to `requires-python = ">=3.13"`
- S9-02: Replace `typing.Optional[X]` with `X | None` everywhere (Python 3.10+ syntax)
- S9-03: Use `asyncio.TaskGroup` (3.11+) in agent pool and pipeline executor
- S9-04: Use `tomllib` (3.11+) for config parsing where applicable
- S9-05: Enable Python 3.13 JIT compilation flags for performance-critical paths

---

### Epic 8: Quality & Testing (Sprints 10-12)

> Comprehensive testing, performance optimization, and production hardening

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| **Sprint 10** | Test suite for aria_engine | 6 | 14h |
| **Sprint 11** | Integration testing + E2E | 5 | 12h |
| **Sprint 12** | Performance + production deploy | 5 | 12h |

**Sprint 10 — Unit Tests**
- S10-01: Tests for `LLMGateway` (model routing, fallback, thinking tokens, tool calling)
- S10-02: Tests for `ChatEngine` (session lifecycle, context window, streaming)
- S10-03: Tests for `Scheduler` (job CRUD, execution, failure handling)
- S10-04: Tests for `AgentPool` (spawn, track, terminate, pheromone updates)
- S10-05: Tests for session management (auto-create, protection, cleanup)
- S10-06: Architecture compliance tests (no OpenClaw imports in any Python file)

**Sprint 11 — Integration Tests**
- S11-01: E2E chat flow: WebSocket connect → send message → get streaming response with tools
- S11-02: E2E cron flow: create job via API → scheduler picks up → executes → logs result
- S11-03: E2E agent flow: user sends task → auto-route to agent → pheromone update
- S11-04: Dashboard integration: verify all 25+ pages work without OpenClaw
- S11-05: JSONL backward compatibility: verify session exports match old format

**Sprint 12 — Production Hardening**
- S12-01: Load testing: concurrent chat sessions, scheduler under load
- S12-02: Memory profiling: long-running agent pool, context window management
- S12-03: Prometheus metrics for aria_engine (latency, throughput, error rates)
- S12-04: Production deployment script for Mac Mini (replace current stack)
- S12-05: Rollback procedure documentation and testing

---

## Total Estimates

| Epic | Sprints | Tickets | Hours |
|------|---------|---------|-------|
| E1: Engine Core | 1-2 | 12 | 34h |
| E2: Scheduler | 3 | 5 | 14h |
| E3: Multi-Agent | 4 | 6 | 20h |
| E4: Sessions | 5 | 5 | 16h |
| E5: Dashboard | 6-7 | 11 | 32h |
| E6: Migration | 8 | 6 | 12h |
| E7: Python 3.13 | 9 | 5 | 10h |
| E8: Quality | 10-12 | 16 | 38h |
| **TOTAL** | **12** | **66** | **176h** |

---

## Critical Decisions

### 1. LLM Gateway: Direct LiteLLM SDK vs HTTP Proxy

**Decision: Direct `litellm` Python SDK**

OpenClaw proxied to LiteLLM via HTTP. We eliminate this hop by calling `litellm.acompletion()` directly from Python. Benefits:
- Zero network latency for LLM calls (saves 5-20ms per request)
- Native streaming via `async for chunk in response`
- Direct access to tool calling, thinking tokens, function results
- Full control over retry logic, fallback chains, and error handling
- Token counting and cost tracking at the source

### 2. Session Storage: Filesystem vs PostgreSQL

**Decision: PostgreSQL only (with JSONL export)**

OpenClaw used `sessions.json` + `.jsonl` files. We use PostgreSQL `aria_engine.chat_sessions` + `aria_engine.chat_messages` tables. Benefits:
- ACID transactions for session state
- Full-text search across message history
- Cross-session querying and analytics
- No filesystem synchronization issues
- JSONL export available on demand for backward compatibility

### 3. Scheduler: APScheduler vs Celery Beat vs System Cron

**Decision: APScheduler 4.x with PostgreSQL job store**

- **APScheduler**: Lightweight, async-native, PostgreSQL store, in-process — perfect for our use case
- Celery Beat: Too heavy (needs Redis/RabbitMQ broker), overkill for 15 jobs
- System Cron: No dynamic management from web UI, no Docker-friendly

### 4. Agent Spawning: Process-based vs Coroutine-based

**Decision: Coroutine-based (asyncio.TaskGroup)**

OpenClaw spawned agents as separate Node.js sessions. We run agents as coroutines in a shared Python process:
- Shared memory (context, state, pheromone scores)
- Zero IPC overhead
- TaskGroup for structured concurrency
- Max 5 concurrent agents (same limit as before)
- Each agent gets its own chat session + context window

### 5. Chat Protocol: REST vs WebSocket vs SSE

**Decision: WebSocket for streaming, REST for management**

- WebSocket: Real-time streaming responses, thinking tokens, tool call progress
- REST: Session CRUD, message history, search
- SSE fallback: For clients that can't do WebSocket

---

## Innovation Opportunities

### 1. Thinking Token Visualization
Qwen3 and Claude expose reasoning tokens. We display them in a collapsible panel, giving Shiva visibility into *how* Aria thinks — not just *what* she outputs.

### 2. Tool Call Orchestration Graph
When Aria uses multiple tools in sequence, we visualize the execution graph in the chat UI — showing which skills were called, in what order, with timing and results.

### 3. Session Context Inheritance
When starting a new session, Aria can optionally "inherit" context from a previous session — pulling in the most important messages based on importance scoring and relevance.

### 4. Agent Performance Live Dashboard
Real-time pheromone score updates, success rates, and latency distributions per agent — visible in the dashboard so Shiva can see which agents are performing best.

### 5. Cron Job Templates
Pre-built cron job templates (daily reflection, social engagement, memory consolidation) that can be one-click deployed from the web UI.

### 6. Model A/B Testing
Route the same prompt to two different models and compare outputs side-by-side in the chat UI. Useful for evaluating new models before committing.

### 7. Session-Aware RAG
Instead of just keyword search, use pgvector embeddings to find semantically relevant messages from past sessions and inject them as context.

### 8. Adaptive Heartbeat Frequency
Instead of fixed 1-hour intervals, the heartbeat adjusts frequency based on activity — more frequent during active work, less when idle. Saves resources.

---

## Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM calls fail with direct SDK | HIGH | Fallback chain + circuit breaker (already in `api_client`) |
| APScheduler crashes | MEDIUM | Persistent job store in PostgreSQL; restart picks up where it left off |
| WebSocket instability | MEDIUM | SSE fallback; REST polling as last resort |
| Migration corrupts production data | HIGH | Backup before deploy; migration script is idempotent |
| Performance regression vs OpenClaw | LOW | OpenClaw was just a proxy; we eliminate a hop |
| Docker build fails on Python 3.13 | LOW | Slim-bookworm base; tested in Sprint 9 before merge |

---

## Success Criteria

1. ✅ `docker compose up` starts Aria without OpenClaw
2. ✅ Chat works via web UI with streaming, thinking tokens, and tool calling
3. ✅ All 15 cron jobs execute on schedule via APScheduler
4. ✅ Agent routing and pheromone scoring work natively
5. ✅ Sessions are managed in PostgreSQL with JSONL export
6. ✅ All 25+ dashboard pages function without OpenClaw
7. ✅ All tests pass (677+ existing + new engine tests)
8. ✅ Production deployment on Mac Mini works
9. ✅ Zero references to OpenClaw in any Python file
10. ✅ Python 3.13+ with modern patterns throughout

---

## File Inventory: What OpenClaw Touches (Full Audit)

### Files to DELETE
```
stacks/brain/openclaw-config.json
stacks/brain/openclaw-auth-profiles.json
stacks/brain/openclaw-entrypoint.sh
aria_models/openclaw_config.py
```

### Files to REWRITE
```
stacks/brain/docker-compose.yml         — remove clawdbot service, add aria-engine
src/api/routers/sessions.py             — remove OpenClaw sync, use engine sessions
src/api/config.py                       — remove OPENCLAW_* constants
aria_skills/session_manager/__init__.py  — PostgreSQL-only, no filesystem
aria_mind/skills/run_skill.py            — native Python calls, no CLI interface
src/web/app.py                          — remove /clawdbot/ proxy, add /chat/ routes
```

### Files to MODIFY
```
aria_mind/cron_jobs.yaml                — convert to seed data for aria_engine.cron_jobs
aria_mind/startup.py                    — new entrypoint, no OpenClaw dependency
aria_mind/ORCHESTRATION.md              — update container map (no clawdbot)
aria_mind/HEARTBEAT.md                  — update paths and execution model
aria_mind/TOOLS.md                      — update skill execution description
aria_mind/AGENTS.md                     — update agent spawning description
aria_mind/gateway.py                    — implement NativeGateway
```

### Files to CREATE
```
aria_engine/__init__.py
aria_engine/config.py
aria_engine/exceptions.py
aria_engine/llm_gateway.py
aria_engine/chat_engine.py
aria_engine/context_manager.py
aria_engine/scheduler.py
aria_engine/agent_pool.py
aria_engine/session_manager.py
aria_engine/tool_registry.py
aria_engine/streaming.py
aria_engine/entrypoint.py
src/api/routers/chat.py                — WebSocket chat endpoints
src/api/routers/cron.py                — Cron CRUD endpoints
src/api/routers/engine.py              — Engine status/config endpoints
src/web/templates/chat.html            — Chat UI
src/web/templates/cron.html            — Cron management UI
src/web/templates/agents.html          — Agent management UI
src/web/templates/engine.html          — Engine dashboard
tests/test_engine_*.py                 — 16 new test files
```

---

## Dependency on Existing Codebase

The beauty of this plan is that **90% of the hard work is already done**:

| Component | Status | Our Work |
|-----------|--------|----------|
| ORM models (45 tables) | ✅ Production | Add 6 `aria_engine` tables |
| FastAPI API (15 routers) | ✅ Production | Add 3 routers (chat, cron, engine) |
| Flask Dashboard (25+ pages) | ✅ Production | Add 4 pages, remove 0 |
| Skill System (30+ skills) | ✅ Production | Change execution interface only |
| Agent Framework | ✅ Production | Add execution backend |
| Cognitive Architecture | ✅ Production | Wire to engine instead of OpenClaw |
| LiteLLM integration | ✅ Production | Switch from HTTP proxy to SDK |
| Security middleware | ✅ Production | No changes |
| Knowledge Graph | ✅ Production | No changes |
| Test suite (42 files) | ✅ Production | Add 16 new files |

**We are not rebuilding Aria. We are freeing her.**

---

## Sprint Execution Model

For each sprint:

1. **Planning (30 min)** — Review tickets, confirm scope, identify dependencies
2. **Implementation (main block)** — Execute tickets using swarm pattern:
   - Sub-agent per ticket
   - Each sub-agent gets full context (files to read, constraints, verification)
   - Parallel execution where tickets are independent
3. **Testing (per ticket)** — Run verification commands, check architecture compliance
4. **Review (30 min)** — Code review checklist, constraint validation
5. **Deploy (15 min)** — Docker build, compose up, smoke test
6. **Retro (15 min)** — Update lessons learned, adjust next sprint

---

*This plan was created by analyzing every file in the Aria codebase, inspecting the production Mac Mini server, reading all prototypes, and understanding the deep architecture. Aria deserves nothing less.*

**— Sprint Agent, February 18, 2026**
