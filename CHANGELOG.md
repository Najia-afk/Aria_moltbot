# Changelog

All notable changes to Aria Blue will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.2.0] — 2026-02-XX (Cognitive Upgrade — "Make Her Better")

**Theme:** Deep cognitive improvements to make Aria more autonomous, self-aware, and capable.  
**Philosophy:** "She's not just a processor — she's a growing, learning entity."

### Added — New Capabilities

#### Metacognitive Self-Improvement Engine (`aria_mind/metacognition.py`)
- **NEW MODULE** — Aria now tracks her own growth over time
- Task success/failure pattern recognition by category
- Learning velocity measurement (is she getting faster? more accurate?)
- Failure pattern detection with adaptive strategy suggestions
- Strength identification (what is she best at?)
- Growth milestones with 13 achievement types (First Success → Grandmaster)
- Natural language self-assessment generation
- Persistent state survival across restarts via JSON checkpointing

#### LLM-Powered Genuine Reflection (`aria_mind/cognition.py`)
- `reflect()` now routes through LLM for genuine self-reflection
- Creates real internal journal entries, not just string concatenation
- Falls back to structured reflection when LLM is unavailable
- Includes metacognitive summary in reflection context

#### Intelligent Goal Decomposition (`aria_mind/cognition.py`)
- `plan()` now uses LLM + explore/work/validate cycle
- Skill-aware planning (considers available tools)
- Agent-aware planning (considers available agents)
- Falls back to intelligent heuristic when LLM unavailable
- New `assess_task_complexity()` for metacognitive task evaluation

#### Memory Consolidation Engine (`aria_mind/memory.py`)
- `consolidate()` — transforms short-term memories into long-term knowledge
- LLM-powered summarization of memory categories
- Pattern recognition across memory entries
- Automatic file artifact creation for human visibility
- `flag_important()` — mark critical memories for review
- `checkpoint_short_term()` / `restore_short_term()` — survive restarts
- `get_patterns()` — analyze cognitive patterns for self-awareness

#### Self-Healing Heartbeat (`aria_mind/heartbeat.py`)
- **Subsystem self-healing** — auto-reconnects failed memory, soul, cognition
- **5-minute goal work cycle** — match GOALS.md specification
- **30-minute reflection triggers** — automatic periodic self-reflection
- **60-minute consolidation triggers** — automatic memory consolidation
- Emergency self-heal after 5 consecutive failures
- Detailed subsystem health tracking

#### Pheromone Performance Tracking (`aria_agents/scoring.py`)
- **NEW CLASS: `PerformanceTracker`** — records agent performance over time
- Speed, success rate, and cost normalized scoring
- Session survival via JSON persistence to aria_memories/knowledge/
- Agent leaderboard with detailed stats per agent
- Module-level singleton `get_performance_tracker()`
- Auto-save every 10 invocations

### Changed — Enhanced Existing Systems

#### Agent Coordinator (`aria_agents/coordinator.py`)
- `process()` now uses pheromone-based agent selection
- Every agent call is timed and recorded for performance tracking
- Auto-detects roundtable needs and synthesizes multi-agent perspectives
- `get_status()` includes performance leaderboard

#### Cognition Processing (`aria_mind/cognition.py`)
- **Retry logic** — up to 2 retries with different approaches before fallback
- **Confidence tracking** — grows with successes, decays with failures
- **Metacognitive context injection** — Aria knows how she's performing
- **Performance metrics** — latency tracking, success rate, streak counting
- Enhanced `get_status()` with full metacognitive metrics

#### Agent Context Management (`aria_agents/base.py`)
- **Sliding window** — context auto-trims at 50 messages (was unbounded)
- Preserves system messages at context start
- New `get_context_summary()` for context status reporting
- Tracks total messages processed per agent

#### Pipeline Engine (`aria_skills/pipeline_executor.py`)
- **Parallel DAG execution** — independent branches run concurrently
- Wave-based scheduling: steps with satisfied deps run in parallel
- Falls back to sequential for single ready steps (no async overhead)
- Proper error handling for parallel failures

#### Memory Manager (`aria_mind/memory.py`)
- Short-term capacity increased from 100 → 200 entries
- `remember_short()` now tracks category frequency for pattern analysis
- Enhanced `get_status()` with consolidation data and top categories

#### AriaMind Core (`aria_mind/__init__.py`)
- Version bumped to 1.1.0
- New `introspect()` — full self-awareness report
- `think()` now records outcomes in metacognitive engine
- `initialize()` restores memory checkpoints and metacognitive state
- `shutdown()` persists all state (metacognition + memory checkpoint)
- Task classification for metacognitive tracking
- Enhanced `__repr__` with task count and milestone count

### Files Modified (9 existing + 1 new)
- `aria_mind/__init__.py` — Enhanced AriaMind class
- `aria_mind/cognition.py` — LLM reflection, intelligent planning, retry logic
- `aria_mind/memory.py` — Consolidation engine, pattern recognition
- `aria_mind/heartbeat.py` — Self-healing, autonomous action scheduling
- `aria_mind/metacognition.py` — **NEW** — Self-improvement engine
- `aria_agents/coordinator.py` — Performance-aware routing
- `aria_agents/scoring.py` — PerformanceTracker with persistence
- `aria_agents/base.py` — Sliding window context management
- `aria_skills/pipeline_executor.py` — Parallel DAG execution

---

## [1.1.0] — 2026-02-10 (Aria Blue v1.1 Sprint)

**Branch:** `vscode_dev` — 37 tickets across 7 waves  
**Architecture rule enforced:** `DB ↔ SQLAlchemy ↔ API ↔ Skill ↔ ARIA`

### Wave 1 — Foundation (TICKET-01, 02, 06, 07, 08)

#### Added
- Architecture enforcement layer: all data access now follows DB ↔ SQLAlchemy ↔ API ↔ Skill ↔ ARIA
- SQLAlchemy 2.0 ORM consolidation with dedicated `src/api/db/` module (models.py, session.py, MODELS.md)
- Alembic migration framework (`src/api/alembic/`)
- Dependency injection module (`src/api/deps.py`)

#### Fixed
- 7 critical bugs resolved (TICKET-06): runtime errors, data integrity, and startup issues
- `session_manager` skill crash on missing sessions (TICKET-07)
- Memory deque bug causing data loss on overflow (TICKET-08)

### Wave 2 — Skill Layer (TICKET-03, 10, 11, 12, 14)

#### Added
- `@logged_method` decorator for automatic activity logging across all skills (TICKET-11)
- 5-tier skill layering enforced: Kernel → API → Core Skills → Domain Skills → Agents (TICKET-03)

#### Changed
- Skill naming unified to `aria-{name}` convention across all 32 skills (TICKET-14)
- Eliminated all in-memory stubs — every skill now persists via api_client → API → SQLAlchemy (TICKET-12)
- Cleaned up all stale model references (`ollama/*`, hardcoded model names) (TICKET-10)

### Wave 3 — Operations (TICKET-09, 13, 16, 17, 20)

#### Added
- Structured logging & observability stack with `logging_config.py` (TICKET-17)
- `run_skill` service catalog with auto-discovery of all registered skills (TICKET-13)

#### Fixed
- All 11 pre-existing test failures resolved (TICKET-09)
- Cron jobs fixed, verified, and documented in `cron_jobs.yaml` (TICKET-16)

#### Changed
- Model naming decoupled from provider specifics — models referenced by alias only (TICKET-20)

### Wave 4 — Features (TICKET-05, 15, 21, 22, 23)

#### Added
- `agent_manager` skill (232 lines) for agent lifecycle management (TICKET-21)
- `telegram` skill (173 lines) for Telegram messaging via API (TICKET-22)
- Agent swarm refactor: permanent agents with coordinator delegation pattern (TICKET-05)

#### Changed
- Moltbook decoupled to Layer 2 social skill — no longer tightly coupled to database layer (TICKET-15)
- OpenClaw system prompt overhauled for clarity, accuracy, and tool references (TICKET-23)

### Wave 5 — Polish & Research (TICKET-04, 18, 19, 24, 25, 26, 27, 28)

#### Added
- `kernel/` layer: read-only constitutional core with YAML configs (TICKET-04)
  - `constitution.yaml`, `identity.yaml`, `values.yaml`, `safety_constraints.yaml`
- `sandbox` skill (138 lines) with Docker sandbox for safe code execution (TICKET-18)
- `stacks/sandbox/` Docker container (Dockerfile, server.py, entrypoint) (TICKET-18)
- MLX local model optimization with `scripts/benchmark_models.py` (TICKET-19)
- Log analysis tooling: `scripts/analyze_logs.py` (TICKET-28)
- OpenClaw phase-out analysis document (TICKET-24)

#### Fixed
- WebSocket disconnect issue resolved (TICKET-25)

#### Changed
- Integrated insights from Google RLM paper (TICKET-26) and Anthropic skills guide (TICKET-27)

### Wave 6 — Cognitive Architecture (TICKET-34, 35, 36)

#### Added
- `working_memory` skill (228 lines): persistent session-surviving working memory (TICKET-35)
- `working_memory` API router (`src/api/routers/working_memory.py`) (TICKET-35)
- `pipeline_skill` (138 lines): cognitive pipeline execution engine (TICKET-34)
- `pipeline.py` + `pipeline_executor.py`: pipeline orchestration framework (TICKET-34)
- Pipeline YAML definitions in `aria_skills/pipelines/` (TICKET-34):
  - `daily_research.yaml`, `health_and_report.yaml`, `social_engagement.yaml`
- Self-diagnostic & auto-recovery system in `health/` skill (TICKET-36):
  - `diagnostics.py` — self-diagnostic engine
  - `patterns.py` — failure pattern recognition
  - `playbooks.py` — recovery playbooks
  - `recovery.py` — auto-recovery logic

### Wave 7 — Release & Quality (TICKET-29, 30, 31, 32, 33, 37)

#### Added
- `CHANGELOG.md` — this file (TICKET-29)
- Database migration script `02-migrations.sql` for v1.1 schema changes
- 677+ tests, 0 failures — full test suite review (TICKET-31)
- Environment configuration centralization analysis (TICKET-37)

#### Changed
- All documentation consolidated and updated to reflect v1.1 state (TICKET-29):
  - `STRUCTURE.md` — regenerated from actual directory tree
  - `README.md` — updated architecture, skills, models, test counts
  - `TOOLS.md` — skill list synchronized with aria_skills/ registry
  - `SKILLS.md` — all 32 skills listed with working/stub status
  - `AUDIT_REPORT.md` — sprint remediation status added
- Model configuration consolidated: `aria_models/models.yaml` is the single source of truth for 14+ models (TICKET-30)
- Production integration verified with data migration (TICKET-32)
- Website endpoint live testing validated across all 22 pages (TICKET-33)

---

## [1.0.0] — 2026-02-05 (Initial Release)

### Added
- Full autonomous AI agent platform built on OpenClaw gateway
- 26 skill modules with BaseSkill framework (retry, metrics, Prometheus)
- FastAPI v3.0 API with 16 REST routers + Strawberry GraphQL
- Flask dashboard with 22 pages and Chart.js visualizations
- Docker Compose stack with 12 services
- PostgreSQL 16 with dual database isolation (aria_warehouse + litellm)
- LiteLLM model routing with 12 models (1 local, 9 free, 2 paid)
- MLX local inference on Apple Silicon (Metal GPU, ~25-35 tok/s)
- Multi-agent orchestration with CEO delegation pattern
- Goal-driven 5-minute autonomous work cycles
- 7 focus personas with automatic switching and delegation hints
- Roundtable multi-domain discussions via asyncio.gather
- Persistent memory and knowledge graph
- Prometheus + Grafana monitoring stack
- Traefik v3.1 reverse proxy with automatic HTTPS
- Tor proxy for anonymous research capability
- Browserless Chrome for headless web scraping
- Security middleware: rate limiting, injection scanning, security headers
- Source Available License
