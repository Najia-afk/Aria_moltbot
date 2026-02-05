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
│   ├── heartbeat.py              # Heartbeat implementation
│   ├── memory.py                 # Memory management
│   ├── security.py               # Security implementation
│   ├── startup.py                # Startup routines
│   ├── cron_jobs.yaml            # Cron schedule definitions
│   ├── soul/                     # Soul implementation
│   │   ├── __init__.py
│   │   ├── identity.py           # Identity module
│   │   ├── values.py             # Core values
│   │   ├── boundaries.py         # Operational boundaries
│   │   └── focus.py              # Focus management
│   ├── skills/                   # Runtime skill mounts (populated at deploy)
│   │   ├── aria_skills/          # ← mounted from ../../aria_skills
│   │   ├── aria_agents/          # ← mounted from ../../aria_agents
│   │   └── legacy/               # ← mounted from ../../skills (deprecated)
│   ├── memory/                   # Memory storage
│   ├── hooks/                    # Behavioral hooks
│   └── tests/                    # Mind-specific tests
│
├── aria_skills/                  # Skill modules (25 directories, 26 classes)
│   ├── __init__.py               # Package exports (v2.0.0)
│   ├── base.py                   # BaseSkill, SkillConfig, SkillResult (362 lines)
│   ├── registry.py               # SkillRegistry with auto-discovery (171 lines)
│   ├── api_client/               # Centralized HTTP client
│   ├── brainstorm/               # Creative ideation
│   ├── ci_cd/                    # CI/CD pipeline management
│   ├── community/                # Community management
│   ├── data_pipeline/            # ETL & data pipeline operations
│   ├── database/                 # PostgreSQL operations
│   ├── experiment/               # ML experiment tracking
│   ├── fact_check/               # Claim verification
│   ├── goals/                    # Goal & habit tracking
│   ├── health/                   # System health monitoring
│   ├── hourly_goals/             # Micro-task tracking
│   ├── input_guard/              # Runtime security (injection detection)
│   ├── knowledge_graph/          # Entity-relationship graph
│   ├── litellm/                  # LiteLLM proxy management
│   ├── llm/                      # Multi-provider LLM routing (2 classes)
│   ├── market_data/              # Cryptocurrency market data
│   ├── model_switcher/           # Dynamic LLM model switching
│   ├── moltbook/                 # Moltbook social platform
│   ├── performance/              # Performance reviews
│   ├── portfolio/                # Portfolio management
│   ├── pytest_runner/            # Pytest execution
│   ├── research/                 # Information gathering
│   ├── schedule/                 # Scheduled jobs
│   ├── security_scan/            # Vulnerability detection
│   └── social/                   # Social presence management
│
├── aria_agents/                  # Multi-agent orchestration
│   ├── __init__.py
│   ├── base.py                   # BaseAgent, AgentConfig, AgentMessage
│   ├── loader.py                 # AGENTS.md parser
│   └── coordinator.py            # Agent lifecycle & routing
│
├── aria_models/                  # Model configuration
│   ├── __init__.py
│   ├── loader.py                 # Model loader
│   ├── models.yaml               # Model definitions
│   └── openclaw_config.py        # OpenClaw model config
│
├── aria_memories/                # Persistent memory storage
│   ├── drafts/                   # Draft content
│   ├── exports/                  # Exported data
│   ├── income_ops/               # Operational income data
│   ├── knowledge/                # Knowledge base files
│   ├── logs/                     # Activity & heartbeat logs
│   ├── plans/                    # Planning documents
│   └── research/                 # Research archives
│
├── stacks/brain/                 # Docker deployment (13 services)
│   ├── docker-compose.yml        # Full stack orchestration
│   ├── .env                      # Environment configuration
│   ├── .env.example              # Template for .env
│   ├── openclaw-entrypoint.sh    # OpenClaw startup with Python + skills
│   ├── openclaw-config.json      # OpenClaw provider template
│   ├── litellm-config.yaml       # LLM model routing
│   ├── prometheus.yml            # Prometheus scrape config
│   ├── init-scripts/             # PostgreSQL initialization
│   │   ├── 00-create-litellm-db.sh  # Creates separate litellm database
│   │   └── 01-schema.sql            # 8 core tables + seed data
│   ├── grafana/                  # Grafana provisioning
│   │   └── provisioning/
│   │       └── datasources/
│   │           └── datasources.yml
│   └── api/                      # FastAPI backend source
│       ├── main.py
│       └── requirements.txt
│
├── src/                          # Application source
│   ├── api/                      # FastAPI backend
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── database/                 # Database utilities
│   └── web/                      # Flask dashboard UI
│       └── index.html
│
├── scripts/                      # Utility scripts
│   ├── export_tables.sh          # Database export
│   ├── mac_backup.sh             # macOS backup script
│   └── service_control_setup.py  # Service configuration
│
├── prompts/                      # Prompt templates
│   ├── agent-workflow.md
│   └── ARIA_COMPLETE_REFERENCE.md
│
├── plans/                        # Project planning
│   ├── aria_action_plan_2026-02-05.md
│   └── improve_aria_plan.md
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
└── tests/                        # Pytest test suite
    ├── __init__.py
    ├── conftest.py               # Fixtures & configuration
    ├── test_agents.py            # Agent unit tests
    ├── test_endpoints.py         # API endpoint tests
    ├── test_imports.py           # Import validation
    ├── test_integration.py       # Integration tests
    ├── test_security.py          # Security tests
    ├── test_skills.py            # Skill unit tests
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

Each of the 25 skill directories follows the same pattern:

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
