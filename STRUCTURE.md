# Aria Blue ⚡️ — Project Structure

---

## Complete Directory Layout

```
Aria_moltbot/
├── README.md                     # Project overview & quick start
├── ARIA_MANUAL.md                # Full deployment & operations guide
├── STRUCTURE.md                  # This file
├── LICENSE                       # Source Available License
├── pyproject.toml                # Python project configuration
├── Dockerfile                    # Agent container build
│
├── aria_mind/                    # OpenClaw workspace (mounted to gateway)
│   ├── SOUL.md                   # Persona, boundaries, model preferences
│   ├── IDENTITY.md               # Agent identity configuration
│   ├── AGENTS.md                 # Sub-agent definitions
│   ├── TOOLS.md                  # Skill registry & execution guide
│   ├── HEARTBEAT.md              # Scheduled task configuration (30m cycles)
│   ├── GOALS.md                  # Goal-driven work system (5-min cycles)
│   ├── ORCHESTRATION.md          # Sub-agent & infrastructure awareness
│   ├── MEMORY.md                 # Long-term curated knowledge
│   ├── SECURITY.md               # Security policies & guidelines
│   ├── USER.md                   # User profile
│   ├── __init__.py
│   ├── cli.py                    # Command-line interface
│   ├── cognition.py              # Cognitive functions
│   ├── gateway.py                # Gateway abstraction (OpenClaw phase-out, S-31)
│   ├── heartbeat.py              # Heartbeat implementation
│   ├── logging_config.py         # Structured logging configuration
│   ├── memory.py                 # Memory management
│   ├── metacognition.py          # Metacognitive functions
│   ├── security.py               # Security implementation
│   ├── startup.py                # Startup routines
│   ├── cron_jobs.yaml            # Cron schedule definitions
│   ├── kernel/                   # Kernel layer — read-only core (v1.1)
│   │   ├── __init__.py
│   │   ├── constitution.yaml     # Core constitution
│   │   ├── identity.yaml         # Identity definition
│   │   ├── safety_constraints.yaml # Safety constraints
│   │   └── values.yaml           # Core values (YAML)
│   ├── soul/                     # Soul implementation
│   │   ├── __init__.py
│   │   ├── identity.py           # Identity module
│   │   ├── values.py             # Core values
│   │   ├── boundaries.py         # Operational boundaries
│   │   └── focus.py              # Focus management
│   ├── skills/                   # Runtime skill mounts (populated at deploy)
│   │   ├── run_skill.py          # Skill runner script
│   │   ├── aria_skills/          # ← mounted from ../../aria_skills
│   │   ├── aria_agents/          # ← mounted from ../../aria_agents
│   │   └── legacy/               # ← mounted from ../../skills (deprecated)
│   ├── memory/                   # Memory storage
│   ├── hooks/                    # Behavioral hooks (contains soul-evil/ for evil mode toggle)
│   └── tests/                    # Mind-specific tests
│
├── aria_skills/                  # Skill modules (26 active skills + pipeline definitions)
│   ├── __init__.py               # Package exports
│   ├── base.py                   # BaseSkill, SkillConfig, SkillResult
│   ├── catalog.py                # Skill catalog generator (--list-skills CLI)
│   ├── registry.py               # SkillRegistry with auto-discovery
│   ├── pipeline.py               # Pipeline definition engine
│   ├── pipeline_executor.py      # Pipeline execution runtime
│   ├── SKILL_STANDARD.md         # Skill development standard
│   ├── SKILL_CREATION_GUIDE.md   # Guide for creating new skills
│   ├── AUDIT.md                  # Skill audit report
│   ├── _template/                # Skill template for scaffolding new skills
│   ├── agent_manager/            # Agent lifecycle management (v1.1)
│   ├── api_client/               # Centralized HTTP client for aria-api
│   ├── ci_cd/                    # CI/CD pipeline automation
│   ├── data_pipeline/            # ETL & data pipeline operations
│   ├── goals/                    # Goal & habit tracking
│   ├── health/                   # System health & self-diagnostic (v1.1)
│   │   ├── __init__.py           # Health skill class
│   │   ├── diagnostics.py        # Self-diagnostic engine
│   │   ├── patterns.py           # Failure pattern recognition
│   │   ├── playbooks.py          # Recovery playbooks
│   │   ├── recovery.py           # Auto-recovery logic
│   │   └── skill.json
│   ├── hourly_goals/             # Micro-task tracking
│   ├── input_guard/              # Runtime security (injection detection)
│   ├── knowledge_graph/          # Entity-relationship graph
│   ├── litellm/                  # LiteLLM proxy management
│   ├── llm/                      # Multi-provider LLM routing
│   ├── market_data/              # Cryptocurrency market data
│   ├── memeothy/                 # Meme generation & content
│   ├── moltbook/                 # Moltbook social platform
│   ├── moonshot/                 # Moonshot SDK (legacy fallback)
│   ├── ollama/                   # Ollama direct access (legacy fallback)
│   ├── performance/              # Performance reviews
│   ├── pipeline_skill/           # Cognitive pipeline execution (v1.1)
│   ├── pipelines/                # Pipeline YAML definitions
│   │   ├── daily_research.yaml
│   │   ├── health_and_report.yaml
│   │   └── social_engagement.yaml
│   ├── portfolio/                # Portfolio management
│   ├── pytest_runner/            # Pytest execution
│   ├── research/                 # Information gathering
│   ├── sandbox/                  # Docker sandbox execution (v1.1)
│   ├── schedule/                 # Scheduled jobs
│   ├── security_scan/            # Vulnerability detection
│   ├── session_manager/          # Session lifecycle management (v1.1)
│   ├── social/                   # Cross-platform social presence
│   ├── telegram/                 # Telegram messaging skill (v1.1)
│   └── working_memory/           # Persistent working memory (v1.1)
│
├── aria_agents/                  # Multi-agent orchestration
│   ├── __init__.py
│   ├── base.py                   # BaseAgent, AgentConfig, AgentMessage
│   ├── context.py                # Agent context management
│   ├── loader.py                 # AGENTS.md parser
│   ├── scoring.py                # Pheromone scoring & agent evaluation
│   └── coordinator.py            # Agent lifecycle, routing & solve() method
│
├── aria_models/                  # Model configuration
│   ├── __init__.py
│   ├── loader.py                 # Model loader
│   ├── models.yaml               # Model catalog (14+ models)
│   ├── openclaw_config.py        # OpenClaw model config
│   └── README.md                 # Model documentation
│
├── aria_memories/                # Persistent memory storage
│   ├── README.md
│   ├── archive/                  # Archived data and old outputs
│   ├── drafts/                   # Draft content
│   ├── exports/                  # Exported data
│   ├── income_ops/               # Operational income data
│   ├── knowledge/                # Knowledge base files
│   ├── logs/                     # Activity & heartbeat logs
│   ├── memory/                   # Core memory files (context.json, skills.json)
│   ├── moltbook/                 # Moltbook drafts and content
│   ├── plans/                    # Planning documents
│   │   └── sprint/               # v1.2 sprint tickets & tracking
│   ├── research/                 # Research archives
│   └── skills/                   # Skill state and persistence data
│
├── stacks/
│   ├── brain/                    # Docker deployment (12 services)
│   │   ├── docker-compose.yml    # Full stack orchestration
│   │   ├── .env                  # Environment configuration (DO NOT COMMIT)
│   │   ├── .env.example          # Template for .env
│   │   ├── openclaw-entrypoint.sh    # OpenClaw startup with Python + skills
│   │   ├── openclaw-config.json      # OpenClaw provider template
│   │   ├── openclaw-auth-profiles.json # Auth profile configs
│   │   ├── litellm-config.yaml       # LLM model routing
│   │   ├── prometheus.yml            # Prometheus scrape config
│   │   ├── traefik-dynamic.yaml      # Traefik dynamic routing config
│   │   ├── traefik-entrypoint.sh     # Traefik startup script
│   │   ├── certs/                    # TLS certificates
│   │   ├── init-scripts/             # PostgreSQL initialization
│   │   │   ├── 00-create-litellm-db.sh  # Creates separate litellm database
│   │   │   ├── 01-schema.sql            # Core tables + seed data
│   │   │   └── 02-migrations.sql        # Schema migrations (v1.1)
│   │   └── grafana/                  # Grafana provisioning
│   │       └── provisioning/
│   │           ├── dashboards/
│   │           │   └── json/         # Dashboard JSON definitions
│   │           └── datasources/
│   │               └── datasources.yml
│   └── sandbox/                  # Docker sandbox for code execution (v1.1)
│       ├── Dockerfile
│       ├── entrypoint.py
│       ├── entrypoint.sh
│       ├── server.py
│       └── README.md
│
├── src/                          # Application source
│   ├── api/                      # FastAPI v3.0 backend
│   │   ├── main.py               # App factory, middleware, 17 routers
│   │   ├── main_legacy.py        # Legacy main (pre-refactor)
│   │   ├── config.py             # Environment config + service endpoints
│   │   ├── deps.py               # Dependency injection
│   │   ├── schema.py             # Pydantic schemas
│   │   ├── security_middleware.py # Rate limiter, injection scanner, headers
│   │   ├── requirements.txt
│   │   ├── alembic/              # Database migrations (v1.1)
│   │   │   ├── env.py
│   │   │   ├── script.py.mako
│   │   │   └── versions/
│   │   ├── db/                   # SQLAlchemy 2.0 ORM layer (v1.1)
│   │   │   ├── __init__.py
│   │   │   ├── models.py         # 20+ ORM models
│   │   │   ├── session.py        # Async engine + sessionmaker
│   │   │   └── MODELS.md         # Model documentation
│   │   ├── gql/                  # Strawberry GraphQL (v1.1)
│   │   │   ├── __init__.py
│   │   │   ├── schema.py         # GraphQL schema
│   │   │   ├── types.py          # GraphQL type definitions
│   │   │   └── resolvers.py      # Query resolvers
│   │   └── routers/              # 17 REST routers
│   │       ├── activities.py     # Activity log CRUD + stats
│   │       ├── admin.py          # Admin operations
│   │       ├── goals.py          # Goal tracking + progress
│   │       ├── health.py         # Liveness, readiness, service status
│   │       ├── knowledge.py      # Knowledge graph entities
│   │       ├── litellm.py        # LiteLLM proxy stats + spend
│   │       ├── memories.py       # Long-term memory storage
│   │       ├── models_config.py  # Dynamic model config from models.yaml
│   │       ├── model_usage.py    # LLM usage metrics + cost tracking
│   │       ├── operations.py     # Operational metrics
│   │       ├── providers.py      # Model provider management
│   │       ├── records.py        # General record management
│   │       ├── security.py       # Security audit log + threats
│   │       ├── sessions.py       # Session management + analytics
│   │       ├── social.py         # Social posts + community
│   │       ├── thoughts.py       # Thought stream + analysis
│   │       └── working_memory.py # Working memory API (v1.1)
│   ├── database/                 # Database utilities
│   │   └── models.py
│   └── web/                      # Flask dashboard (22 pages)
│       ├── app.py                # Flask app + 20 routes
│       ├── static/               # CSS, JS
│       │   ├── css/              # Component styles (base, layout, variables)
│       │   └── js/
│       │       └── pricing.js    # Shared pricing helpers
│       └── templates/            # 22 Jinja2 templates + Chart.js
│
├── scripts/                      # Utility scripts
│   ├── analyze_logs.py           # Log analysis tool (v1.1)
│   ├── aria_backup.sh            # Backup script
│   ├── backup.sh                 # Alternative backup
│   ├── benchmark_models.py       # Model benchmarking (v1.1)
│   ├── check_architecture.py     # Architecture validation (v1.1)
│   ├── check_db.sh               # Database health check
│   ├── export_tables.sh          # Database export
│   ├── generate_litellm_config.py # LiteLLM config generator
│   ├── health_check.sh           # System health check
│   ├── mac_backup.sh             # macOS backup script
│   ├── retrieve_logs.ps1         # Windows log retrieval
│   ├── retrieve_logs.sh          # Linux log retrieval
│   ├── service_control_setup.py  # Service configuration
│   └── test_mlx.py              # MLX inference testing
│
├── prompts/                      # Prompt templates
│   ├── agent-workflow.md
│   └── ARIA_COMPLETE_REFERENCE.md
│
├── deploy/                       # Deployment utilities
│   └── mac/                      # macOS-specific deployment
│
├── patch/                        # Patches & fixes
│   ├── openclaw_patch.js
│   └── openclaw-litellm-fix.patch
│
├── tasks/                        # Task documentation
│   └── lessons.md
│
└── tests/                        # Pytest test suite (677+ tests)
    ├── __init__.py
    ├── conftest.py               # Fixtures & configuration
    ├── test_activity_logging.py  # @logged_method tests (v1.1)
    ├── test_agents.py            # Agent unit tests
    ├── test_agent_manager.py     # Agent manager tests (v1.1)
    ├── test_cron_config.py       # Cron configuration tests
    ├── test_diagnostics.py       # Self-diagnostic tests (v1.1)
    ├── test_endpoints.py         # API endpoint tests
    ├── test_imports.py           # Import validation
    ├── test_integration.py       # Integration tests
    ├── test_kernel.py            # Kernel layer tests (v1.1)
    ├── test_logging.py           # Logging tests (v1.1)
    ├── test_log_analysis.py      # Log analysis tests (v1.1)
    ├── test_memory_deque.py      # Memory deque tests (v1.1)
    ├── test_model_loader.py      # Model loader tests
    ├── test_model_naming.py      # Model naming tests (v1.1)
    ├── test_model_profiles.py    # Model profile tests
    ├── test_model_refs.py        # Model reference tests (v1.1)
    ├── test_pipeline.py          # Pipeline tests (v1.1)
    ├── test_run_skill_catalog.py # Skill catalog tests (v1.1)
    ├── test_sandbox.py           # Sandbox tests (v1.1)
    ├── test_sandbox_skill.py     # Sandbox skill tests (v1.1)
    ├── test_security.py          # Security tests
    ├── test_self_diagnostic.py   # Self-diagnostic tests (v1.1)
    ├── test_session_manager.py   # Session manager tests (v1.1)
    ├── test_skills.py            # Skill unit tests
    ├── test_skill_naming.py      # Skill naming tests (v1.1)
    ├── test_skill_persistence.py # Skill persistence tests (v1.1)
    ├── test_social_platform.py   # Social platform tests
    ├── test_system_prompt.py     # System prompt tests (v1.1)
    ├── test_telegram_skill.py    # Telegram skill tests (v1.1)
    ├── test_working_memory.py    # Working memory tests (v1.1)
    └── manual/                   # Manual test procedures
```

---

## Key Files

### aria_mind/ (OpenClaw Workspace)

| File | Purpose | Loaded |
|------|---------|--------|
| `SOUL.md` | Persona, boundaries, tone | Every session |
| `IDENTITY.md` | Agent identity configuration | Every session |
| `AGENTS.md` | Sub-agent definitions | Every session |
| `TOOLS.md` | Available skills & limits | Every session |
| `HEARTBEAT.md` | Periodic task checklist | Every heartbeat (30m) |
| `GOALS.md` | Goal-driven work cycles | Every session |
| `MEMORY.md` | Long-term knowledge | Main session only |
| `USER.md` | User profile | Every session |
| `SECURITY.md` | Security policies | Every session |
| `ORCHESTRATION.md` | Infrastructure awareness | Every session |

### stacks/brain/ (Docker Deployment)

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Orchestrates all 13 services |
| `openclaw-entrypoint.sh` | Generates OpenClaw config at startup |
| `openclaw-config.json` | Template for LiteLLM provider |
| `litellm-config.yaml` | Routes model aliases to MLX/OpenRouter |
| `init-scripts/` | PostgreSQL database initialization |
| `prometheus.yml` | Prometheus scrape targets |

### Database Initialization

```
init-scripts/
├── 00-create-litellm-db.sh     # Creates separate 'litellm' database
└── 01-schema.sql               # Creates Aria's tables in 'aria_warehouse'
```

> **Why separate databases?** LiteLLM uses Prisma migrations that can drop tables not in its schema. Keeping Aria's tables in `aria_warehouse` and LiteLLM's in `litellm` prevents data loss.

---

## Skill Architecture

### Skill Module Structure

Each of the 26 active skill directories follows the same pattern:

```
aria_skills/<skill>/
├── __init__.py      # Skill class extending BaseSkill
├── skill.json       # OpenClaw manifest (name, description, emoji)
└── SKILL.md         # Documentation (optional)
```

### BaseSkill Framework (base.py)

| Component | Description |
|-----------|-------------|
| `SkillStatus` (Enum) | `AVAILABLE`, `UNAVAILABLE`, `RATE_LIMITED`, `ERROR` |
| `SkillConfig` (dataclass) | `name`, `enabled`, `config` dict, optional `rate_limit` |
| `SkillResult` (dataclass) | `success`, `data`, `error`, `timestamp`; factories `.ok()` / `.fail()` |
| `BaseSkill` (ABC) | Abstract base with metrics, retry, Prometheus integration |

### Registry (registry.py)

- `@SkillRegistry.register` decorator for auto-discovery
- `load_from_config(path)` parses `TOOLS.md` for YAML config blocks
- Lookup via `get(name)`, `list_available()`, `check_all_health()`

### Runtime Mount (OpenClaw Container)

```
/root/.openclaw/workspace/skills/
├── run_skill.py                # Skill runner (generated at startup)
├── aria_skills/                # ← mounted from ../../aria_skills
├── aria_agents/                # ← mounted from ../../aria_agents
└── legacy/                     # ← mounted from ../../skills (deprecated)

/root/.openclaw/skills/         # OpenClaw manifest symlinks
├── aria-database/skill.json    # → .../aria_skills/database/skill.json
├── aria-moltbook/skill.json    # → .../aria_skills/moltbook/skill.json
└── ... (25 symlinks created by entrypoint)
```

### Execution Flow

```
OpenClaw Agent (exec tool)
       │
       ▼
python3 run_skill.py <skill> <function> '<args_json>'
       │
       ▼
SkillRegistry → imports aria_skills.<skill>
       │
       ▼
BaseSkill.safe_execute() → retry + metrics + result
       │
       ▼
JSON output → returned to OpenClaw
```

---

## Service Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Docker Stack (stacks/brain)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │  Traefik   │    │  OpenClaw  │    │  LiteLLM   │                  │
│  │  :80/:443  │    │  :18789    │    │  :18793    │                  │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘                  │
│        │                 │                 │                          │
│        ▼                 ▼                 ▼                          │
│  ┌────────────┐    ┌────────────┐    ┌──────────────────┐            │
│  │  aria-web  │    │ aria_mind/ │    │  MLX Server      │            │
│  │  Flask UI  │    │ Workspace  │    │  (host:8080)     │            │
│  │  :5000     │    │ + Skills   │    │  Metal GPU       │            │
│  └─────┬──────┘    └────────────┘    └──────────────────┘            │
│        │                                                              │
│        ▼                                                              │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │  aria-api  │───▶│  aria-db   │    │  grafana   │                  │
│  │  FastAPI   │    │ PostgreSQL │    │  :3001     │                  │
│  │  :8000     │    │  :5432     │    └────────────┘                  │
│  └────────────┘    └────────────┘                                    │
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │ Prometheus │    │  PGAdmin   │    │ aria-brain │                  │
│  │  :9090     │    │  :5050     │    │  (Agent)   │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │ tor-proxy  │    │  browser   │    │ certs-init │                  │
│  │  :9050     │    │  :3000     │    │  (oneshot) │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Deployment

### From Windows (PowerShell)

```powershell
cd C:\git\Aria_moltbot\stacks\brain
docker compose up -d
```

### From macOS / Linux

```bash
cd Aria_moltbot/stacks/brain
docker compose up -d
```

### Fresh Deploy (Nuke & Rebuild)

```bash
cd stacks/brain
docker compose down -v    # Remove volumes (data loss!)
docker compose up -d      # Rebuild
docker compose ps         # Verify 13 healthy services
```

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | `https://{HOST}/` | Main web UI |
| API Docs | `https://{HOST}/api/docs` | Swagger documentation |
| OpenClaw | `http://{HOST}:18789` | Gateway API |
| LiteLLM | `http://{HOST}:18793` | Model router |
| Grafana | `https://{HOST}/grafana` | Monitoring dashboards |
| PGAdmin | `https://{HOST}/pgadmin` | Database admin |
| Prometheus | `https://{HOST}/prometheus` | Metrics |
| Traefik | `https://{HOST}/traefik/dashboard` | Proxy dashboard |

---

## Model Chain

```
OpenClaw Request
  └─► litellm/qwen3-mlx
       │
       ▼
  LiteLLM Router (:18793)
  ├─► qwen3-mlx     → MLX Server (host:8080, Metal GPU, ~25-35 tok/s)
  ├─► glm-free      → OpenRouter GLM 4.5 Air (FREE)
  ├─► deepseek-free → OpenRouter DeepSeek R1 (FREE)
  ├─► nemotron-free → OpenRouter Nemotron 30B (FREE)
  └─► kimi          → Moonshot Kimi K2.5 (PAID, last resort)
```

---

*Aria Blue ⚡️ — Project Structure*
