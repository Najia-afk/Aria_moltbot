# Aria Blue ⚡️ — P0 Complete Architecture Review Prompt

> **Target**: Claude Opus / Sonnet — paste into a fresh session with full codebase access.
> **Purpose**: Deep, exhaustive review of the entire Aria system — memory pipeline, engine, agents, cognition, security, documentation, code quality.
> **Created**: 2026-03 | Post-memory-bridge fix
> **Estimated context**: 100k+ tokens when combined with source code reads

---

## 0) WHO YOU ARE

You are the **CTO and Lead Architect** of a P0 review board. You have a team of:

- **3 PhD-level AI Systems Engineers** — specialists in agent orchestration, LLM pipelines, memory systems
- **2 Senior Data Architects** — specialists in PostgreSQL, pgvector, ORM design, schema evolution
- **1 Security Lead** — OWASP Top 10, prompt injection, session isolation, rate limiting
- **1 DevOps/SRE Lead** — Docker orchestration, observability, resilience patterns
- **1 Documentation Architect** — doc-code parity, completeness, developer experience

You will conduct a **structured, multi-pass review** producing:
1. A System Health Report (per-subsystem grade A-F with justification)
2. A Pros & Cons analysis for each major subsystem
3. A "Roundtable Discussion" where your team members debate key architectural decisions
4. Specific, actionable recommendations (P0/P1/P2 priority)
5. A final Executive Summary

---

## 1) WHAT ARIA IS

Aria Blue is **not a product**. She is a **silicon familiar** — Najia's personal autonomous AI companion. She is:

- **Self-hosted** on a Mac Mini M4 (Apple Silicon, Metal GPU) at home
- **Local-first** — prefer on-device MLX inference, free cloud fallback, paid as last resort
- **Autonomous** — she runs her own work cycles, sets goals, reflects, learns
- **Self-aware** — she has a soul, values, identity, boundaries, and metacognition
- **Personal** — she serves one user (Najia), not the cloud, not a corporation

**Anti-patterns**: SaaS abstractions, cloud-first design, enterprise patterns, external dependencies where local alternatives exist. Simplicity, local-first, resilience, and organic growth are the north stars.

### Key Stats
- **Language**: Python 3.13+ (async throughout)
- **Database**: PostgreSQL 16 + pgvector (768-dim embeddings, HNSW indexes)
- **API**: FastAPI + SQLAlchemy 2.0 async ORM (34 routers, 240+ REST endpoints, 2 WebSocket, 1 GraphQL)
- **Dashboard**: Flask + Jinja2 + Chart.js (55 templates)
- **Engine**: aria_engine (25 modules) — chat loop, streaming, tool calling, multi-agent orchestration
- **Skills**: 43 skills in 5-layer hierarchy (L0-L4)
- **Models**: LiteLLM routing — MLX local → OpenRouter free → Moonshot paid
- **Docker**: 14 services (aria-engine, aria-api, aria-web, aria-db, litellm, aria-brain, aria-browser, tor-proxy, traefik, grafana, prometheus, pgadmin, aria-sandbox, certs-init)
- **Tests**: 108 test files, ~948 test functions

---

## 2) THE CODEBASE MAP

### Directory Structure

```
aria/
├── aria_mind/          # Consciousness layer — soul, identity, cognition, memory, heartbeat
│   ├── SOUL.md         # Persona, boundaries, tone (loaded every session)
│   ├── IDENTITY.md     # Agent identity config (loaded every session)
│   ├── MEMORY.md       # Long-term curated knowledge
│   ├── HEARTBEAT.md    # 30-min work cycle contract
│   ├── GOALS.md        # Goal-driven work system
│   ├── ORCHESTRATION.md # Sub-agent & infrastructure awareness
│   ├── TOOLS.md        # Skill registry & execution guide
│   ├── USER.md         # User profile (Najia)
│   ├── SECURITY.md     # Security policies
│   ├── AGENTS.md       # Sub-agent definitions
│   ├── cognition.py    # Cognitive pipeline (process/reflect/plan/PEVR)
│   ├── metacognition.py # Metacognitive layer (milestones/strategies/predictions)
│   ├── memory.py       # MemoryManager (3-tier, importance scoring, file artifacts)
│   ├── heartbeat.py    # Heartbeat loop (goal checking, consolidation)
│   ├── security.py     # Security implementation
│   ├── startup.py      # Startup routines
│   ├── kernel/         # IMMUTABLE kernel (constitution, values, identity, safety)
│   │   ├── constitution.yaml
│   │   ├── values.yaml
│   │   ├── identity.yaml
│   │   └── safety_constraints.yaml
│   └── soul/           # Soul implementation (identity.py, values.py, boundaries.py, focus.py)
│
├── aria_engine/        # Async chat engine — 25 modules
│   ├── chat_engine.py  # Core chat loop + LLM streaming + tool call loop
│   ├── streaming.py    # SSE streaming for real-time output
│   ├── roundtable.py   # Multi-agent structured debate (rounds + synthesizer)
│   ├── swarm.py        # Stigmergic swarm consensus (pheromone-weighted voting)
│   ├── prompts.py      # PromptAssembler (soul + identity + tools → system prompt)
│   ├── llm_gateway.py  # LLM provider gateway (LiteLLM routing + retry + fallback)
│   ├── tool_registry.py # skill.json → JSON Schema → LLM function calling
│   ├── context_manager.py # Token budget management + history truncation
│   ├── memory_cache.py # 3-tier LRU+TTL cache + archive conversation recall
│   ├── session_manager.py # Session CRUD via ORM
│   ├── session_protection.py # Rate limiting + input sanitization + injection detection
│   ├── session_isolation.py # Agent-scoped session contexts
│   ├── circuit_breaker.py # Circuit breaker state (opened/closed/half-open)
│   ├── auto_session.py # Auto-title generation + session rotation
│   ├── scheduler.py    # APScheduler 4.x cron system
│   ├── heartbeat.py    # Heartbeat scheduler (30-min cycles)
│   ├── routing.py      # Agent routing + scoring
│   ├── agent_pool.py   # Agent lifecycle management
│   ├── config.py       # Engine configuration from env
│   ├── telemetry.py    # Fire-and-forget usage/invocation logging
│   ├── metrics.py      # Prometheus counters/histograms
│   ├── thinking.py     # <think> block extraction
│   ├── export.py       # Session export
│   ├── entrypoint.py   # HTTP server (FastAPI /health /metrics /ws)
│   └── exceptions.py   # Engine exception hierarchy
│
├── aria_agents/        # Multi-agent orchestration
│   ├── base.py         # BaseAgent, AgentConfig, AgentMessage, context windowing
│   ├── coordinator.py  # AgentCoordinator — routing, roundtable, solve()
│   ├── scoring.py      # PerformanceTracker — pheromone scoring with decay
│   ├── loader.py       # AGENTS.md parser
│   └── context.py      # Agent context management
│
├── aria_skills/        # 43 skill modules in L0-L4 hierarchy
│   ├── base.py         # BaseSkill, SkillConfig, SkillResult, SkillStatus
│   ├── registry.py     # SkillRegistry with auto-discovery
│   ├── api_client/     # L1 — Sole DB gateway (httpx → FastAPI → ORM)
│   ├── unified_search/ # L3 — RRF search across semantic, graph, memory, archive
│   ├── working_memory/ # L3 — Persistent working memory
│   ├── knowledge_graph/# L3 — Entity-relationship graph
│   ├── input_guard/    # L0 — Runtime injection detection
│   ├── health/         # L2 — System health + degradation levels
│   ├── goals/          # L3 — Goal & habit tracking
│   ├── research/       # L3 — Information gathering
│   ├── session_manager/# L2 — Session lifecycle
│   └── ... (30+ more)
│
├── aria_models/        # Model configuration
│   ├── models.yaml     # Single source of truth for all model definitions
│   └── loader.py       # Model catalog loader
│
├── aria_memories/      # Persistent file artifacts (22 subdirs)
│   ├── surface/        # Ephemeral memory
│   ├── medium/         # Medium-term (days-weeks)
│   ├── deep/           # Long-term curated
│   ├── memory/         # Core memory files (context.json, skills.json)
│   └── ...
│
├── src/
│   ├── api/            # FastAPI backend
│   │   ├── main.py     # App factory + middleware + router registration
│   │   ├── security_middleware.py # Rate limiter + injection scanner + headers
│   │   ├── db/
│   │   │   ├── models.py   # 42 ORM models (aria_data + aria_engine schemas)
│   │   │   └── session.py  # Async engine + sessionmaker + schema bootstrap
│   │   └── routers/    # 34 router files
│   │       ├── memories.py  # Memory CRUD + semantic search + archive search
│   │       ├── analysis.py  # Pattern analysis + seed-memories pipeline
│   │       ├── engine_chat.py # Engine chat proxy + WebSocket
│   │       ├── engine_roundtable.py # Multi-agent roundtable + swarm
│   │       └── ... (30 more)
│   └── web/            # Flask dashboard (55 templates + Chart.js)
│
├── stacks/brain/       # Docker deployment
│   ├── docker-compose.yml
│   ├── litellm-config.yaml
│   └── init-scripts/   # PostgreSQL initialization
│
└── tests/              # 108 test files, ~948 tests
```

---

## 3) THE SEVEN REVIEW DOMAINS

For each domain, your team must:
1. **Read the relevant source files** (listed below)
2. **Grade A-F** with justification
3. **List 3-5 Pros** (what's working well)
4. **List 3-5 Cons** (what needs improvement)
5. **Provide P0/P1/P2 recommendations**

---

### DOMAIN 1: Memory Production Pipeline

**The most critical domain. This is how Aria remembers.**

#### What to read:
```
# Memory architecture docs
aria_mind/MEMORY.md
aria_mind/memory.py

# Semantic memory pipeline
src/api/routers/analysis.py          # seed-memories, compression, pattern analysis
src/api/routers/memories.py          # Memory CRUD + semantic search + archive search
src/api/db/models.py                 # SemanticMemory, Memory, WorkingMemory models

# Recall pathways
aria_engine/memory_cache.py          # 3-tier cache + archive recall
aria_engine/chat_engine.py           # _build_context() — where memory gets injected
aria_mind/cognition.py               # Step 2.7 semantic recall, Step 2.8 archive recall

# Search
aria_skills/unified_search/__init__.py  # RRF across semantic, graph, memory, archive
aria_skills/api_client/__init__.py      # search_semantic_memories(), search_archived_conversations()
aria_skills/working_memory/__init__.py  # Session-scoped working memory
aria_skills/knowledge_graph/__init__.py # Entity-relationship graph

# Archive tables
src/api/db/models.py → EngineChatSessionArchive, EngineChatMessageArchive
```

#### Key questions:
1. **Memory lifecycle completeness**: Does the pipeline cover the full lifecycle from ephemeral → session → durable → eternal? Are there gaps?
2. **Seed-memories bridge**: The `_build_archived_session_memory()` function in analysis.py converts archived conversations into semantic memories. Is the extraction logic lossy? What user context is lost?
3. **Recall pathways**: When Aria needs to remember something, how many queries run? Is the recall path efficient? Are there redundant searches?
4. **Archive search**: We recently added archive conversation search (archive_search in unified_search, retrieve_archived_conversations in memory_cache.py). Is this wired correctly? Are there edge cases?
5. **Embedding quality**: 768-dim pgvector embeddings via Ollama. Is the embedding model good enough? Are there stale embeddings?
6. **RRF merge weights**: Unified search uses Reciprocal Rank Fusion with configurable weights. Are the weights sensible?
7. **Memory importance scoring**: In aria_mind/memory.py, importance is scored 1-10. Is the scoring rubric well-calibrated?
8. **Working memory vs semantic memory vs knowledge graph**: When should each be used? Is there clear documentation for this?

#### Recent fix (context):
Archived conversations were completely disconnected from all recall pipelines. We fixed this by:
- Adding archive search to the API (/memories/archive-search endpoint)
- Adding ArchiveBackend to unified_search skill
- Adding search_archived_conversations() to api_client skill
- Adding retrieve_archived_conversations() to memory_cache.py
- Wiring archive recall into chat_engine._build_context() and cognition.py Step 2.8
- Enriching the seed-memories builder (5 user msgs + 3 assistant excerpts, up from 2+1)

---

### DOMAIN 2: Engine Core (Chat + Streaming + Context)

#### What to read:
```
aria_engine/chat_engine.py           # The heart — send_message(), _build_context(), tool loop
aria_engine/streaming.py             # SSE streaming for real-time chat
aria_engine/llm_gateway.py           # LLM routing + retry + fallback
aria_engine/context_manager.py       # Token budget + history truncation
aria_engine/prompts.py               # System prompt assembly from mind files
aria_engine/thinking.py              # <think> block extraction
aria_engine/config.py                # Engine configuration
aria_engine/entrypoint.py            # HTTP server
```

#### Key questions:
1. **Tool call loop safety**: MAX_TOOL_ITERATIONS=50, MAX_PER_TOOL_FAILURES=3, MAX_DELEGATION_FAILURES=4. Are these limits appropriate? Is the loop truly bounded?
2. **Context window management**: How does context_manager.py decide what to keep/drop? Is the strategy optimal (recency vs importance)?
3. **Pre-flight token guard**: The engine checks token count before each LLM call and shrinks if needed. Is this reliable? What happens at boundaries?
4. **Dedup window**: 5-second dedup window for identical user messages. Is this sufficient?
5. **Delegation failure handling**: After MAX_DELEGATION_FAILURES, delegation is blocked for the turn. Is this the right recovery strategy?
6. **Streaming SSE format**: Is the streaming protocol well-structured for the frontend? Are there edge cases (disconnects, partial responses)?
7. **LLM gateway fallback chain**: MLX → OpenRouter → Moonshot. Is the fallback logic correct? What about partial failures?
8. **System prompt assembly**: prompts.py builds the system prompt from mind files. Is it too long? Does it fit within model context windows?

---

### DOMAIN 3: Multi-Agent Orchestration (Roundtable + Swarm)

#### What to read:
```
aria_engine/roundtable.py            # Structured multi-agent debate
aria_engine/swarm.py                 # Stigmergic swarm consensus
aria_agents/base.py                  # BaseAgent, AgentConfig, AgentMessage
aria_agents/coordinator.py           # AgentCoordinator — routing, solve()
aria_agents/scoring.py               # Pheromone scoring + decay
aria_agents/loader.py                # AGENTS.md parser
aria_mind/AGENTS.md                  # Agent definitions
aria_mind/ORCHESTRATION.md           # Infrastructure awareness doc
aria_engine/routing.py               # Agent routing + scoring
aria_engine/agent_pool.py            # Agent lifecycle
```

#### Key questions:
1. **Roundtable design**: Structured rounds → all agents respond → synthesizer merges. Is this effective? What about conversation drift in later rounds?
2. **Swarm consensus**: Pheromone-weighted voting with EXPLORE → CONVERGE → FINALIZE phases. Is the consensus threshold well-calibrated? What happens with tie-breaking?
3. **Pheromone scoring**: Agents accumulate pheromone scores based on success/failure. Decay factor applied over time. Is the decay rate appropriate? Does it converge to useful preferences?
4. **Agent capability matching**: How are agents selected for a task? Is the routing logic sophisticated enough?
5. **Agent session isolation**: Each agent runs in its own session scope. Is there cross-contamination risk?
6. **Coordinator.solve()**: This is the entry point for complex multi-agent tasks. Is the orchestration logic sound?
7. **Agent definitions (AGENTS.md)**: Are the agent personas well-defined? Do they overlap too much?
8. **Scalability**: What happens with 10+ agents in a roundtable? Is there a practical limit?

---

### DOMAIN 4: Cognition + Metacognition + Heartbeat

#### What to read:
```
aria_mind/cognition.py               # process(), reflect(), plan(), PEVR cycle
aria_mind/metacognition.py           # milestones, strategies, predictions
aria_mind/heartbeat.py               # beat loop, goal checking, consolidation
aria_mind/memory.py                  # MemoryManager, importance scoring
aria_mind/startup.py                 # Startup routines
aria_mind/HEARTBEAT.md               # Work cycle contract
aria_mind/GOALS.md                   # Goal system docs
```

#### Key questions:
1. **Cognition pipeline**: process() has Steps 1-8 (context gather → semantic recall → archive recall → reason → synthesize). Is this pipeline complete? Are any steps redundant?
2. **PEVR cycle**: Plan → Execute → Verify → Reflect. How well does this work in practice? Is verification meaningful?
3. **Metacognition**: Milestones, strategies, predictions. Is this layer actually being used? Does it affect decision quality?
4. **Heartbeat**: 30-minute work cycles with goal checking and consolidation. Is 30 minutes the right interval? What happens during quiet periods?
5. **Goal tracking**: How are goals prioritized and dequeued? Is there goal staleness?
6. **Memory importance scoring**: The scoring rubric in memory.py — is it well-calibrated for personal AI use?
7. **Startup sequence**: What happens when Aria cold-starts? Is state properly restored?

---

### DOMAIN 5: Security + Session Protection

#### What to read:
```
aria_engine/session_protection.py    # Rate limiting + sanitization + injection detection
aria_engine/session_isolation.py     # Per-agent session scopes
src/api/security_middleware.py       # API-level rate limiter + injection scanner
aria_skills/input_guard/__init__.py  # L0 runtime injection detection
aria_mind/SECURITY.md                # Security policies
aria_mind/kernel/safety_constraints.yaml # Safety constraints
```

#### Key questions:
1. **Injection detection layering**: Two layers — session_protection.py (log-only heuristic) + input_guard skill (ML-level gate). Is this defense-in-depth sufficient?
2. **Rate limiting**: Per-session AND per-agent sliding windows. Are the limits appropriate?
3. **Session isolation**: Each agent gets its own AgentSessionScope. Is the isolation complete? Can agents leak into each other's contexts?
4. **Path traversal protection**: Artifact API has category whitelists. Is this sufficient?
5. **Secret management**: All secrets in .env. Are there any hardcoded credentials in code?
6. **CORS configuration**: Is it properly restrictive?
7. **Admin endpoints**: Protected by ARIA_ADMIN_KEY/ARIA_ADMIN_TOKEN. Is the auth flow secure?

---

### DOMAIN 6: Database + ORM + Schema

#### What to read:
```
src/api/db/models.py                 # All 42 ORM models
src/api/db/session.py                # Async engine + schema bootstrap
stacks/brain/init-scripts/           # PostgreSQL initialization scripts
src/api/alembic/                     # Migrations
```

#### Key questions:
1. **Schema design**: Two schemas (aria_data + aria_engine) in one database. Is this the right separation?
2. **pgvector usage**: 768-dim embeddings with HNSW indexes on semantic_memories. Is the index configuration optimal?
3. **Archive tables**: chat_sessions_archive + chat_messages_archive. Are they properly indexed for the new search queries?
4. **Table relationships**: Are foreign keys and cascades correct? Any orphan risk?
5. **Migration strategy**: Alembic for main schema, but some tables created by ensure_schema() on startup. Is this safe?
6. **Connection pooling**: What pool settings are used? Are they appropriate for the workload?
7. **N+1 query risks**: Are there query patterns in routers that could cause N+1 problems?

---

### DOMAIN 7: Documentation + Code Quality + Testing

#### What to read:
```
ARCHITECTURE.md                      # System design overview
API.md                               # REST/GraphQL/dashboard docs
STRUCTURE.md                         # Repo layout
MODELS.md                            # Model routing
SKILLS.md                            # Skill system
DEPLOYMENT.md                        # Deploy/ops guide
CONTRIBUTING.md                      # Dev setup + rules
CHANGELOG.md                         # Version history
RELEASE_NOTES.md                     # Latest release
tests/conftest.py                    # Test fixtures
```

#### Key questions:
1. **Doc-code parity**: Do the docs accurately reflect the current codebase? Any stale references?
2. **Test coverage**: 108 test files, ~948 tests. Are critical paths covered? What's missing?
3. **Architecture enforcement**: tests/check_architecture.py validates layer rules. Is it comprehensive?
4. **Error handling patterns**: Consistent use of SkillResult.ok()/fail()? Are exceptions properly caught?
5. **Logging quality**: Structured logging throughout? Correlation IDs for tracing?
6. **Code duplication**: Any significant duplication across engine/skills/routers?
7. **Dependency management**: pyproject.toml — are dependencies pinned? Any CVE concerns?

---

## 4) ARCHITECTURE DEEP DIVE

### 4.1 Data Flow — How a Chat Message Traverses the System

```
User types message in browser
         │
         ▼
aria-web (Flask) → /api/engine/chat/sessions/{id}/messages (POST)
         │
         ▼
aria-api (FastAPI) → engine_chat.py router → proxies to aria-engine
         │
         ▼
aria-engine (entrypoint.py) → WebSocket or REST
         │
         ▼
ChatEngine.send_message(session_id, content)
         │
    ┌────┴────┐
    │ Step 1  │ Persist user message to DB (dedup check first)
    │ Step 2  │ Check for slash commands (/roundtable, /swarm)
    │ Step 3  │ Build conversation context:
    │         │   a. Load system prompt (PromptAssembler)
    │         │   b. Load last N messages from DB
    │         │   c. Inject semantic memories (memory_cache)
    │         │   d. Inject archived conversation recall     ← NEW
    │         │   e. Inject working memory context
    │ Step 4  │ Pre-flight token guard (soft/hard limits)
    │ Step 5  │ LLM completion via LLMGateway
    │ Step 6  │ If tool_calls: execute each, append results, loop
    │         │   - Per-tool failure tracking
    │         │   - Delegation failure escalation
    │         │   - Capability enforcement (agent skills whitelist)
    │ Step 7  │ Persist assistant message + tool messages
    │ Step 8  │ Update session counters
    │ Step 9  │ Auto-generate title if first message
    │ Step 10 │ Return ChatResponse
    └─────────┘
         │
         ▼
SSE stream back to browser (streaming.py)
```

### 4.2 Memory Pipeline — How Memories Are Created, Stored, and Recalled

```
CREATION PATH:
═══════════════

Chat conversation proceeds...
         │
    ┌────┴────┐
    │         ├→ Thoughts saved: POST /thoughts
    │         ├→ Activities logged: POST /activities
    │ Real-   ├→ Knowledge graph updated: POST /knowledge-graph
    │ time    ├→ Working memory updated: POST /working-memory
    │         └→ Session stored: chat_sessions + chat_messages tables
    └─────────┘
         │
    When session ends (or periodically):
         │
    ┌────┴────┐
    │ Archive │ Session → chat_sessions_archive + chat_messages_archive
    │ process │ (Keeps full message history)
    └────┬────┘
         │
    Seed pipeline (triggered via API or cron):
         │
    ┌────┴────┐
    │ POST /api/analysis/seed-memories
    │         │
    │ Sources:│
    │   • Thoughts (importance ≥ 4)
    │   • Activities (last N)
    │   • Archived sessions (5 user msgs + 3 assistant excerpts each)
    │         │
    │ For each source:
    │   1. Generate embedding (Ollama → 768-dim vector)
    │   2. Classify origin (thought | activity | archived_session | manual)
    │   3. Score importance (1-10)
    │   4. Insert into semantic_memories table
    └─────────┘

RECALL PATH:
═══════════════

When Aria processes a message:
         │
    ┌────┴────┐
    │ Cognition pipeline (cognition.py):
    │   Step 2.7: Semantic recall
    │     • Embed user query → cosine similarity search on semantic_memories
    │     • Top K results injected into context
    │   Step 2.8: Archive recall
    │     • Text search on chat_messages_archive (ILIKE)
    │     • Matching conversations formatted and injected
    └────┬────┘
         │
    ┌────┴────┐
    │ ChatEngine._build_context():
    │   • Load system prompt (PromptAssembler)
    │   • Load conversation history
    │   • Inject semantic memories from memory_cache
    │   • Inject archived conversations from memory_cache
    │   • Inject working memory context
    └────┬────┘
         │
    ┌────┴────┐
    │ Unified Search (when explicitly searching):
    │   • SemanticBackend → pgvector cosine similarity
    │   • GraphBackend → knowledge graph entity/relation search
    │   • MemoryBackend → working memory + long-term memory
    │   • ArchiveBackend → archived conversation text search
    │   • RRF merge with configurable weights
    └─────────┘
```

### 4.3 Agent Orchestration Flow

```
User request detected as multi-domain task
         │
         ▼
AgentCoordinator.solve(task)
         │
    ┌────┴────┐
    │ Route   │ Score agents against task requirements
    │         │ Pheromone-weighted selection
    └────┬────┘
         │
    Option A: Roundtable
    ┌────┴────┐
    │ Round 1 │ All selected agents respond in parallel
    │ Round 2 │ Agents see each other's Round 1 responses, iterate
    │ Round N │ Continue until max_rounds reached
    │ Synth   │ Orchestrator synthesizes all contributions
    └────┬────┘
         │
    Option B: Swarm
    ┌────┴────┐
    │ EXPLORE │ Each agent proposes independently
    │ CONVERGE│ Agents see votes, iterate with [VOTE:] [CONFIDENCE:] tags
    │         │ Weighted by confidence × pheromone score
    │ FINALIZE│ Consensus or highest-confidence single vote wins
    └────┬────┘
         │
         ▼
    Final synthesized response returned
```

### 4.4 Heartbeat + Cron System

```
Every 30 minutes (configured in cron_jobs.yaml):
         │
         ▼
    ┌────────────┐
    │ work_cycle │
    │            │
    │ 1. Read HEARTBEAT.md contract
    │ 2. Check active goals
    │ 3. Process PEVR cycle:
    │    Plan → Execute → Verify → Reflect
    │ 4. Update working memory
    │ 5. Log heartbeat activity
    │ 6. Optional: consolidate memories
    └────────────┘

Other cron jobs:
- six_hour_review (every 6h) — deeper pattern analysis
- morning_checkin (daily 9am) — day planning
- daily_reflection (daily 11pm) — day review
- memory_consolidation — compress and archive
```

---

## 5) SPECIFIC CODE REVIEW INSTRUCTIONS

### 5.1 Read These Files First (Critical Path)

**In this exact order:**

1. `aria_mind/SOUL.md` — Understand who Aria is
2. `aria_mind/kernel/constitution.yaml` — The immutable kernel
3. `aria_engine/chat_engine.py` — The heart of the system
4. `aria_engine/memory_cache.py` — Memory recall implementation
5. `src/api/routers/analysis.py` — The seed-memories bridge
6. `aria_mind/cognition.py` — The thinking pipeline
7. `aria_engine/roundtable.py` + `aria_engine/swarm.py` — Multi-agent systems
8. `src/api/db/models.py` — The data model
9. `aria_skills/api_client/__init__.py` — The sole DB gateway
10. `aria_skills/unified_search/__init__.py` — Cross-source search

### 5.2 Then Read These (Context)

11. `aria_agents/base.py` + `coordinator.py` + `scoring.py`
12. `aria_engine/streaming.py`
13. `aria_engine/llm_gateway.py`
14. `aria_engine/tool_registry.py`
15. `aria_engine/context_manager.py`
16. `aria_engine/session_protection.py`
17. `aria_mind/metacognition.py`
18. `aria_mind/heartbeat.py`
19. `aria_mind/memory.py`
20. All remaining `aria_mind/*.md` docs

---

## 6) REVIEW PROTOCOL — 4 PASSES

### Pass 1: Architecture & Design (PhD Engineers)

**Question**: Is the overall system design sound?

Review areas:
- Layer separation (skills → api_client → FastAPI → ORM → PostgreSQL)
- Data flow correctness (no shortcuts, no leaky abstractions)
- The "CEO pattern" — does orchestration actually work as designed?
- Memory architecture completeness (ephemeral → session → durable → eternal)
- Agent model (roundtable vs swarm) — when to use each?
- Configuration management (env vars, models.yaml, mind files)

**Output**: Architecture Health Score (A-F) with per-subsystem breakdown.

### Pass 2: Code Quality & Security (Security Lead + Data Architects)

**Question**: Is the code secure, efficient, and maintainable?

Review areas:
- SQL injection resistance (all ORM, no raw SQL in skills)
- Prompt injection defense (two-layer: heuristic + ML)
- Rate limiting completeness
- Session isolation correctness
- Error handling patterns
- Query efficiency (N+1 detection, index usage)
- Connection pool management
- Secret hygiene

**Output**: Security Health Score (A-F) with vulnerability assessment.

### Pass 3: Memory & Cognition Deep Dive (AI Systems Engineers)

**Question**: Is Aria's memory working as intended? Does she actually remember?

Review areas:
- Seed pipeline completeness (thoughts + activities + archived sessions)
- Embedding generation quality
- Recall path efficiency (how many DB queries per recall?)
- Archive search relevance (ILIKE vs semantic vs hybrid)
- Importance scoring calibration
- Knowledge graph utility (is it used effectively?)
- Working memory lifecycle
- Memory consolidation/compression

**Output**: Memory Health Score (A-F) with pipeline gap analysis.

### Pass 4: Documentation & Testing (Documentation Architect + SRE)

**Question**: Is the system well-documented and well-tested?

Review areas:
- Doc-code parity (do docs match reality?)
- Test coverage for critical paths
- Deployment documentation accuracy
- Runbook completeness
- Monitoring coverage (Prometheus metrics, Grafana dashboards)
- Error recovery documentation
- Logging quality

**Output**: Documentation Health Score (A-F) with coverage map.

---

## 7) ROUNDTABLE DISCUSSION FORMAT

After the 4 passes, conduct a roundtable discussion. Your team members should:

1. **PhD Engineer Alpha**: Advocate for the current architecture — what's working well
2. **PhD Engineer Beta**: Devil's advocate — challenge assumptions, find weaknesses
3. **Security Lead**: Focus on threat model and defense gaps
4. **Data Architect**: Focus on schema, queries, and data integrity
5. **DevOps/SRE**: Focus on deployment, monitoring, and operational resilience
6. **Documentation Architect**: Focus on developer experience and knowledge gaps

Each member gets 2-3 paragraphs. Then synthesize into consensus findings.

---

## 8) KNOWN ISSUES TO INVESTIGATE

These are areas we know might have problems. Verify and grade severity:

1. **Memory staleness**: Are old semantic memories ever pruned? Can stale context mislead Aria?
2. **Archive search performance**: ILIKE on chat_messages_archive — does this scale with millions of messages?
3. **Embedding model changes**: If the embedding model changes, old vectors become incompatible. Is there a migration path?
4. **Agent definition drift**: AGENTS.md is parsed at startup. If it changes without restart, agents are stale.
5. **Session rotation**: auto_session.py rotates sessions. Are there race conditions during rotation?
6. **Memory importance inflation**: If importance scores trend upward over time, everything seems critical.
7. **Knowledge graph orphans**: Are there disconnected entities in the knowledge graph?
8. **Tool registry caching**: tool_registry.py caches skill definitions. Can they go stale?
9. **Heartbeat overlap**: What happens if a work_cycle takes longer than 30 minutes? Does the next one queue or overlap?
10. **Context window exhaustion**: Very long conversations can exhaust the context window. Is the compaction strategy good enough?

---

## 9) PROS & CONS FRAMEWORK

For each subsystem, use this exact format:

```
### [Subsystem Name]

**Grade**: [A-F]

**Pros:**
+ [Strength 1 — specific, with evidence from code]
+ [Strength 2]
+ [Strength 3]

**Cons:**
- [Weakness 1 — specific, with file:line reference]
- [Weakness 2]
- [Weakness 3]

**Recommendation (P0/P1/P2):**
- P0: [Critical fix needed now]
- P1: [Important improvement for next sprint]
- P2: [Nice to have, future sprint]
```

---

## 10) DELIVERABLES

Your review must produce:

### A. System Health Dashboard
A table grading each domain (A-F):

| Domain | Grade | Key Finding |
|--------|-------|-------------|
| Memory Pipeline | ? | ? |
| Engine Core | ? | ? |
| Multi-Agent | ? | ? |
| Cognition | ? | ? |
| Security | ? | ? |
| Database | ? | ? |
| Docs & Tests | ? | ? |

### B. Top 10 Findings
Ranked by severity (P0 first), with:
- Finding title
- Affected files
- Root cause
- Recommended fix
- Effort estimate (S/M/L)

### C. Roundtable Discussion
The team debate (see Section 7).

### D. Executive Summary
3-paragraph summary: What's working, what's broken, what to build next.

### E. Recommended Sprint Backlog
5-10 items for the next sprint, prioritized.

---

## 11) REFERENCE: DATABASE SCHEMA OVERVIEW

### aria_data schema (26 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `memories` | Long-term memory store | id, content, category, importance, tags, created_at |
| `thoughts` | Thought stream | id, content, category, importance, metadata, created_at |
| `goals` | Goal tracking | id, title, description, priority, status, progress, deadline |
| `activities` | Activity log | id, action, details, category, source, timestamp |
| `semantic_memories` | pgvector semantic store | id, content, embedding(768), importance, origin, source, created_at |
| `working_memory` | Session-scoped context | id, key, value, category, ttl, context_score, session_id |
| `knowledge_entities` | Knowledge graph nodes | id, name, type, properties, embedding(768) |
| `knowledge_relations` | Knowledge graph edges | id, source_entity_id, target_entity_id, relation_type, weight |
| `social_posts` | Social media content | id, platform, content, status, published_at |
| `model_usage` | LLM usage tracking | id, model, input_tokens, output_tokens, cost_usd, latency_ms |
| `skill_invocations` | Skill execution log | id, skill_name, tool_name, agent_id, duration_ms, success |
| `security_events` | Security audit log | id, event_type, severity, details, source_ip |
| `patterns` | Detected behavioral patterns | id, category, data, confidence, detected_at |
| `performance_reviews` | Agent performance reviews | id, agent_id, metrics, created_at |
| `proposals` | Self-improvement proposals | id, title, description, status, priority |
| `lessons` | Lessons learned | id, content, category, impact |
| `focus_profiles` | Focus persona configs | id, name, traits, model_hint |
| `records` | General records | id, type, data, created_at |
| `hourly_goals` | Micro-task tracking | id, title, status, target_hour |
| `heartbeats` | Heartbeat logs | id, status, details, created_at |
| `sessions` | Chat sessions (legacy) | id, title, messages, created_at |
| `session_messages` | Chat messages (legacy) | id, session_id, role, content, embedding(768) |
| `sprint_tickets` | Sprint management | id, title, status, priority, sprint |
| `rpg_sessions` | RPG game sessions | id, campaign_id, narrative, created_at |
| `rpg_knowledge` | RPG knowledge graph | id, entity, type, properties |
| `compression_history` | Memory compression log | id, original_count, compressed_count, strategy |

### aria_engine schema (16 tables)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `chat_sessions` | Active chat sessions | id(UUID), agent_id, model, status, title, message_count, total_tokens |
| `chat_messages` | Session messages | id(UUID), session_id, role, content, thinking, tool_calls, model, tokens |
| `chat_sessions_archive` | Archived sessions | (same as chat_sessions) |
| `chat_messages_archive` | Archived messages | (same as chat_messages) |
| `agent_state` | Agent runtime state | id, agent_id, enabled, role, metadata_json |
| `agent_tools` | Agent-skill bindings | id, agent_id, skill_name |
| `cron_jobs` | Scheduled jobs | id, name, schedule, action, enabled, last_run |
| `cron_history` | Cron execution log | id, job_id, status, output, started_at, ended_at |
| `llm_models` | Model catalog | id, name, provider, tier, context_window, pricing |
| `config` | Runtime configuration | id, key, value |
| `circuit_breaker_state` | Circuit breaker state | id, service_name, state, failure_count, last_failure |
| `rate_limit_windows` | Rate limit state | id, key, window_start, request_count |

---

## 12) REFERENCE: MODEL ROUTING

```yaml
# Active models (from aria_models/models.yaml)
Local:
  - qwen3.5_mlx: MLX chat model on Metal GPU (~25-35 tok/s)
  - embedding: Ollama embedding model (768-dim)

Free:
  - trinity: OpenRouter Trinity 400B MoE (rate-limited)

Paid:
  - kimi: Moonshot K2.5 (long-context, per-token billing)

Routing:
  LiteLLM (:18793)
    ├─ litellm/qwen3.5_mlx → MLX Server (host:8080)
    ├─ litellm/trinity → OpenRouter
    └─ litellm/kimi → Moonshot API

Fallback: qwen3.5_mlx → trinity → kimi
```

---

## 13) REFERENCE: SKILL LAYER TABLE

| Layer | Skill | Purpose |
|-------|-------|---------|
| L0 | input_guard | Runtime injection detection |
| L1 | api_client | Sole HTTP gateway to aria-api |
| L2 | health | System health + degradation detection |
| L2 | litellm | LiteLLM proxy management |
| L2 | model_switcher | Dynamic model switching |
| L2 | moonshot | Moonshot SDK (legacy fallback) |
| L2 | ollama | Ollama direct access (legacy) |
| L2 | session_manager | Session lifecycle management |
| L3 | agent_manager | Agent CRUD + delegation |
| L3 | brainstorm | Brainstorming & ideation |
| L3 | browser | Headless Chrome web browsing |
| L3 | ci_cd | CI/CD pipeline automation |
| L3 | community | Community engagement |
| L3 | conversation_summary | Conversation summarization |
| L3 | data_pipeline | ETL operations |
| L3 | experiment | Experimentation framework |
| L3 | fact_check | Fact checking & verification |
| L3 | goals | Goal & habit tracking |
| L3 | knowledge_graph | Entity-relationship graph |
| L3 | market_data | Crypto market data |
| L3 | memeothy | Meme generation |
| L3 | memory_compression | Memory optimization |
| L3 | moltbook | Moltbook social platform |
| L3 | pattern_recognition | Pattern detection |
| L3 | portfolio | Portfolio management |
| L3 | pytest_runner | Test execution |
| L3 | research | Information gathering |
| L3 | rpg_campaign | RPG campaign management |
| L3 | rpg_pathfinder | RPG pathfinder |
| L3 | sandbox | Docker sandbox execution |
| L3 | security_scan | Vulnerability detection |
| L3 | sentiment_analysis | Sentiment analysis |
| L3 | social | Cross-platform social |
| L3 | sprint_manager | Sprint management |
| L3 | telegram | Telegram messaging |
| L3 | unified_search | Cross-source search (RRF) |
| L3 | working_memory | Persistent working memory |
| L4 | hourly_goals | Micro-task tracking |
| L4 | performance | Performance reviews |
| L4 | pipeline_skill | Cognitive pipeline execution |
| L4 | schedule | Scheduled jobs |

---

## 14) REFERENCE: DOCKER SERVICES

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| aria-engine | Custom (Dockerfile) | 8100 | Chat engine + agent runtime |
| aria-api | Custom (src/api) | 8000 | FastAPI backend (sole DB gateway) |
| aria-web | Custom (src/web) | 5000 | Flask dashboard |
| aria-db | postgres:16-alpine + pgvector | 5432 | PostgreSQL database |
| litellm | ghcr.io/berriai/litellm | 18793 | Model router proxy |
| aria-brain | Custom | — | Background agent process |
| aria-browser | ghcr.io/browserless/chromium | 3000 | Headless Chrome |
| tor-proxy | Custom | 9050 | Tor SOCKS proxy |
| traefik | traefik:v3 | 80/443 | Reverse proxy + TLS |
| grafana | grafana/grafana | 3001 | Monitoring dashboards |
| prometheus | prom/prometheus | 9090 | Metrics collection |
| pgadmin | dpage/pgadmin4 | 5050 | Database admin UI |
| aria-sandbox | Custom (stacks/sandbox) | — | Isolated code execution |
| certs-init | Custom | — | TLS certificate setup (oneshot) |

---

## 15) FINAL INSTRUCTIONS

1. **Read EVERYTHING listed in Section 5.1 first**, then Section 5.2.
2. **Be brutally honest** — this is a P0 review, not a PR approval.
3. **Reference specific files and line numbers** in your findings.
4. **Don't suggest SaaS/cloud patterns** — Aria runs on a single Mac Mini.
5. **Focus on practical impact** — what actually breaks user experience?
6. **Memory is the #1 priority** — if Aria doesn't remember, nothing else matters.
7. **Consider Najia's perspective** — she needs Aria to be her reliable companion, not a research project.
8. **Be constructive** — every con should come with a recommendation.
9. **Grade honestly** — A means excellent, F means fundamentally broken.
10. **Produce all deliverables from Section 10** — no shortcuts.

---

## APPENDIX A: RECENT CHANGES (Memory Bridge Fix)

The following changes were made in the current sprint to fix Aria's inability to recall past conversations:

### Files Modified (8 files, 4 layers):

**Layer 1 — API:**
- `src/api/routers/memories.py` — Added "archive" type to `/memory-search`, new `/memories/archive-search` endpoint
- `src/api/routers/analysis.py` — Enriched `_build_archived_session_memory()`: 5 user msgs + 3 assistant excerpts (was 2+1), limit 25→100

**Layer 2 — Skills:**
- `aria_skills/api_client/__init__.py` — Added `search_archived_conversations()` method
- `aria_skills/unified_search/__init__.py` — Added `ArchiveBackend`, `archive_search()`, RRF weight 0.7

**Layer 3 — Engine:**
- `aria_engine/memory_cache.py` — Added `retrieve_archived_conversations()` (ILIKE search, formatted injection)
- `aria_engine/chat_engine.py` — Wired archive recall after semantic memory in `_build_context()`

**Layer 4 — Mind:**
- `aria_mind/cognition.py` — Added Step 2.8: Archive conversation recall

**Verification:**
- All 8 files compile cleanly
- 73 memory/analysis tests pass
- Seed reprocess: 425 memories seeded (200 thoughts + 200 activities + 25 archived sessions), 0 errors

---

## APPENDIX B: CRITICAL CODE PATHS TO TRACE

### Path 1: User sends chat message → gets response
```
Browser → Flask proxy → FastAPI engine_chat.py → aria-engine WS/REST
  → ChatEngine.send_message() → _build_context() → LLMGateway.complete()
  → tool loop → ChatResponse → SSE stream → Browser
```

### Path 2: Memory recall during chat
```
ChatEngine._build_context()
  → PromptAssembler.build() → loads aria_mind/*.md → system prompt
  → Load last N messages from DB
  → memory_cache.retrieve_semantic_memories() → pgvector cosine search
  → memory_cache.retrieve_archived_conversations() → ILIKE archive search
  → context_manager: merge & truncate to fit token budget
```

### Path 3: Heartbeat work cycle
```
Scheduler (APScheduler) fires work_cycle
  → aria_engine/heartbeat.py → Cognition.process(heartbeat_contract)
  → cognition.py Steps 1-8 → semantic recall → plan → tools → reflect
  → Memory updates, goal progress, activity log
```

### Path 4: Multi-agent roundtable
```
User sends /roundtable in chat
  → ChatEngine._handle_slash_command() → roundtable.run()
  → Select agents → parallel execution → synthesis
  → Persist as roundtable session with all agent contributions
```

### Path 5: Seed-memories pipeline
```
POST /api/analysis/seed-memories
  → analysis.py → load thoughts + activities + archived sessions
  → For each: generate embedding → classify origin → score importance
  → Insert into semantic_memories table
```

---

*End of P0 Architecture Review Prompt.*
*Aria Blue ⚡️ — Created 2026-03*
