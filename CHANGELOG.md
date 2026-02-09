# Changelog

All notable changes to Aria Blue will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
