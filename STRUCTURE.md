# Aria Blue - Project Structure

## Complete Directory Layout

```
Aria_moltbot/
├── README.md                     # Project overview & quick start
├── ARIA_MANUAL.md                # Full deployment guide
├── STRUCTURE.md                  # This file
│
├── aria_mind/                    # OpenClaw workspace (mounted to clawdbot)
│   ├── SOUL.md                   # Persona, boundaries, model preferences
│   ├── IDENTITY.md               # Name: Aria Blue ⚡️
│   ├── AGENTS.md                 # Sub-agent definitions
│   ├── TOOLS.md                  # Available skills & execution guide
│   ├── HEARTBEAT.md              # Cron job documentation
│   ├── GOALS.md                  # Goal-driven work system (5-min cycles)
│   ├── ORCHESTRATION.md          # Sub-agent & infrastructure awareness
│   ├── MEMORY.md                 # Long-term curated knowledge
│   ├── USER.md                   # User profile (Najia)
│   ├── __init__.py
│   ├── cli.py                    # Command-line interface
│   ├── cognition.py              # Cognitive functions
│   ├── heartbeat.py              # Heartbeat implementation
│   ├── memory.py                 # Memory management
│   ├── startup.py                # Startup routines
│   └── soul/                     # Soul implementation
│       ├── __init__.py
│       ├── identity.py           # Identity module
│       ├── values.py             # Core values
│       └── boundaries.py         # Operational boundaries
│
├── aria_skills/                  # Core skill implementations (mounted to clawdbot)
│   ├── __init__.py
│   ├── base.py                   # BaseSkill, SkillConfig, SkillResult
│   ├── registry.py               # SkillRegistry with TOOLS.md parser
│   ├── moltbook.py               # Moltbook social platform
│   ├── database.py               # PostgreSQL with asyncpg
│   ├── llm.py                    # LLM routing (Ollama + cloud fallback)
│   ├── health.py                 # Health monitoring
│   ├── knowledge_graph.py        # Knowledge graph operations
│   ├── goals.py                  # Goal & task scheduling
│   ├── performance.py            # Performance tracking (v1.1.0)
│   ├── social.py                 # Social media posting (v1.1.0)
│   ├── hourly_goals.py           # Hourly goal tracking (v1.1.0)
│   ├── litellm_skill.py          # LiteLLM proxy management (v1.1.0)
│   ├── schedule.py               # Schedule & task management (v1.1.0)
│   ├── model_switcher.py         # Ollama model switching
│   └── pytest_runner.py          # Pytest test runner
│
├── aria_agents/                  # Multi-agent orchestration (mounted to clawdbot)
│   ├── __init__.py
│   ├── base.py                   # BaseAgent, AgentConfig, AgentMessage
│   ├── loader.py                 # AGENTS.md parser
│   └── coordinator.py            # Agent lifecycle & routing
│
├── skills/                       # Legacy skill implementations (mounted to clawdbot)
│   ├── __init__.py
│   ├── moltbook_poster.py        # Original Moltbook poster
│   ├── goal_scheduler.py         # Original goal scheduler
│   ├── health_monitor.py         # Original health monitor
│   ├── knowledge_graph.py        # Original knowledge graph
│   └── requirements.txt
│
├── stacks/brain/                 # 🚀 PRIMARY DEPLOYMENT (Docker)
│   ├── docker-compose.yml        # Full stack orchestration (12 services)
│   ├── .env                      # Environment configuration
│   ├── .env.example              # Template for .env
│   │
│   ├── openclaw-entrypoint.sh    # OpenClaw startup with Python + skills
│   ├── openclaw-config.json      # OpenClaw provider template
│   ├── litellm-config.yaml       # LiteLLM model routing
│   ├── prometheus.yml            # Prometheus scrape config
│   │
│   ├── init-scripts/             # PostgreSQL initialization
│   │   ├── 00-create-litellm-db.sh  # Creates separate litellm database
│   │   └── 01-schema.sql            # Aria's 8 core tables + seed data
│   │
│   ├── grafana/                  # Grafana configuration
│   │   └── provisioning/
│   │       └── datasources/
│   │           └── datasources.yml
│   │
│   └── api/                      # FastAPI backend source
│       ├── main.py
│       └── requirements.txt
│
├── src/                          # Application source
│   ├── api/
│   │   ├── main.py               # FastAPI backend
│   │   └── requirements.txt
│   └── web/
│       └── index.html            # Dashboard UI
│
├── openclaw_skills/              # OpenClaw UI skills (SKILL.md format)
│   ├── aria-database/            # 🗄️ Database queries
│   │   └── SKILL.md
│   ├── aria-moltbook/            # 🦞 Moltbook social platform
│   │   └── SKILL.md
│   ├── aria-health/              # 💚 Health monitoring
│   │   └── SKILL.md
│   ├── aria-goals/               # 🎯 Goal tracking
│   │   └── SKILL.md
│   ├── aria-knowledge-graph/     # 🕸️ Knowledge graph
│   │   └── SKILL.md
│   ├── aria-llm/                 # 🧠 LLM routing
│   │   └── SKILL.md
│   ├── aria-pytest/              # 🧪 Pytest runner
│   │   └── SKILL.md
│   ├── aria-model-switcher/      # 🔄 Model switching
│   │   └── SKILL.md
│   ├── aria-performance/         # 📊 Performance tracking (v1.1.0)
│   │   └── SKILL.md
│   ├── aria-social/              # 📱 Social media posting (v1.1.0)
│   │   └── SKILL.md
│   ├── aria-hourly-goals/        # ⏰ Hourly goals (v1.1.0)
│   │   └── SKILL.md
│   ├── aria-litellm/             # 💰 LiteLLM proxy (v1.1.0)
│   │   └── SKILL.md
│   └── aria-schedule/            # 📅 Scheduling (v1.1.0)
│       └── SKILL.md
│
├── tests/                        # pytest test suite
│   ├── conftest.py               # Fixtures
│   ├── test_skills.py            # Skill unit tests
│   └── test_agents.py            # Agent unit tests
│
└── deploy.ps1                    # Windows PowerShell deployment script
```

## Key Files Explained

### aria_mind/ (OpenClaw Workspace)

| File | Purpose | Loaded When |
|------|---------|-------------|
| `SOUL.md` | Persona, boundaries, tone | Every session |
| `IDENTITY.md` | Name: "Aria Blue", emoji: ⚡️ | Every session |
| `AGENTS.md` | Sub-agent definitions | Every session |
| `TOOLS.md` | Available skills & limits | Every session |
| `HEARTBEAT.md` | Periodic task checklist | Every heartbeat (30m) |
| `MEMORY.md` | Long-term knowledge | Main session only |
| `USER.md` | User profile (Najia) | Every session |

### stacks/brain/ (Docker Deployment)

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Orchestrates all 12 services |
| `openclaw-entrypoint.sh` | Generates OpenClaw config at startup |
| `openclaw-config.json` | Template for LiteLLM provider |
| `litellm-config.yaml` | Routes model aliases to Ollama |
| `init-scripts/` | PostgreSQL database initialization |

### Database Initialization Scripts

```
init-scripts/
├── 00-create-litellm-db.sh     # Creates separate 'litellm' database
└── 01-schema.sql               # Creates Aria's tables in 'aria_warehouse'
```

**Why separate databases?** LiteLLM uses Prisma migrations that can drop tables not in its schema. Keeping Aria's tables in `aria_warehouse` and LiteLLM's in `litellm` prevents data loss.

## Python Skills Architecture

Aria's Python skills are mounted into the OpenClaw container at runtime:

```
/root/.openclaw/workspace/          # OpenClaw workspace
├── SOUL.md, IDENTITY.md, etc.      # Configuration files
└── skills/                         # Python skill modules
    ├── run_skill.py                # Skill runner (generated at startup)
    ├── aria_skills/                # ← mounted from ../../aria_skills
    │   ├── base.py
    │   ├── database.py
    │   ├── moltbook.py
    │   ├── health.py
    │   ├── goals.py
    │   ├── llm.py
    │   ├── knowledge_graph.py
    │   ├── model_switcher.py
    │   ├── pytest_runner.py
    │   ├── performance.py          # v1.1.0
    │   ├── social.py               # v1.1.0
    │   ├── hourly_goals.py         # v1.1.0
    │   ├── litellm_skill.py        # v1.1.0
    │   └── schedule.py             # v1.1.0
    ├── aria_agents/                # ← mounted from ../../aria_agents
    │   ├── base.py
    │   ├── loader.py
    │   └── coordinator.py
    └── legacy/                     # ← mounted from ../../skills
        ├── moltbook_poster.py
        ├── goal_scheduler.py
        └── health_monitor.py
```

### Skill Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  OpenClaw Agent                                                      │
│  └─► Uses exec tool to run Python skill                             │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  python3 run_skill.py database query '{"sql": "SELECT..."}'         │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  run_skill.py                                                        │
│  ├── Imports aria_skills.database.DatabaseSkill                     │
│  ├── Initializes with DATABASE_URL from environment                 │
│  ├── Calls skill.query(sql=...)                                     │
│  └── Returns JSON result                                            │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PostgreSQL (aria-db:5432)                                           │
│  └─► Database: aria_warehouse                                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Service Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │  Port 80/443 │  │  Port 18789  │  │  Port 18793  │                   │
│  │   (Traefik)  │  │  (OpenClaw)  │  │  (LiteLLM)   │                   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                   │
└─────────┼─────────────────┼─────────────────┼───────────────────────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼───────────────────────────┐
│         ▼                 ▼                 ▼           DOCKER          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   traefik    │  │   clawdbot   │  │   litellm    │                   │
│  │  (routing)   │  │  (OpenClaw)  │  │  (router)    │                   │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘                   │
│         │                 │                 │                            │
│         ▼                 ▼                 ▼                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   aria-web   │  │  aria_mind/  │  │   Ollama     │                   │
│  │  (Flask UI)  │  │ (workspace)  │  │ (host:11434) │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
│         │                                                                │
│         ▼                                                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │   aria-api   │  │   aria-db    │  │   grafana    │                   │
│  │  (FastAPI)   │  │ (PostgreSQL) │  │ (monitoring) │                   │
│  └──────┬───────┘  └──────────────┘  └──────────────┘                   │
│         │                 ▲                 ▲                            │
│         └─────────────────┴─────────────────┘                            │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │
│  │  prometheus  │  │   pgadmin    │  │  aria-brain  │                   │
│  │  (metrics)   │  │  (DB admin)  │  │  (Python)    │                   │
│  └──────────────┘  └──────────────┘  └──────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Quick Deployment

### From Windows (PowerShell)

```powershell
cd C:\git\Aria_moltbot
.\deploy.ps1 -Action deploy
```

### From Mac/Linux

```bash
cd Aria_moltbot/stacks/brain
docker compose up -d
```

### Fresh Deploy (Nuke & Rebuild)

```bash
cd stacks/brain
docker compose down -v    # Remove volumes (data loss!)
docker compose up -d      # Rebuild
docker compose ps         # Verify 12 healthy services
```

## Services After Deployment

| Service | URL | Credentials |
|---------|-----|-------------|
| Dashboard | https://{SERVICE_HOST}/ | - |
| API Docs | https://{SERVICE_HOST}/api/docs | - |
| OpenClaw | http://{SERVICE_HOST}:18789 | Token in .env |
| LiteLLM | http://{SERVICE_HOST}:18793 | Master key in .env |
| PGAdmin | https://{SERVICE_HOST}/pgadmin | Set in .env |
| Grafana | https://{SERVICE_HOST}/grafana | Set in .env |
| Traefik | https://{SERVICE_HOST}/traefik/dashboard | - |
| Prometheus | https://{SERVICE_HOST}/prometheus | - |

## Manual Commands

```powershell
# Check status
.\deploy.ps1 -Action status

# View logs
.\deploy.ps1 -Action logs

# Restart services
.\deploy.ps1 -Action restart

# Stop everything
.\deploy.ps1 -Action stop
```

Or directly with Docker:

```bash
cd stacks/brain
docker compose ps
docker compose logs -f clawdbot
docker compose restart
docker compose down
```

## Model Chain

```
┌─────────────────────────────────────────────────────────────────┐
│  OpenClaw Request                                                │
│  └─► litellm/qwen3-local                                        │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ LiteLLM Router (port 18793)                                 ││
│  qwen3-mlx     → MLX Server (port 8080)                      ││
│  │ ├─► glm-free    → OpenRouter GLM 4.5 Air (FREE)             ││
│  │ ├─► deepseek-free → OpenRouter DeepSeek R1 (FREE)           ││
│  │ ├─► nemotron-free → OpenRouter Nemotron 30B (FREE)          ││
│  │ └─► kimi        → Moonshot Kimi K2.5 (PAID - last resort)   ││
│  └─────────────────────────────────────────────────────────────┘│
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ MLX Server (host:8080, Metal GPU via launchd)               ││
│  │ └─► Qwen3-VLTO-8B-Instruct-mlx (~25-35 tok/s)               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  FALLBACK CHAIN (if local fails):                                │
│  └─► OpenRouter FREE models (glm, deepseek, nemotron)           │
│  └─► Moonshot Kimi (paid, only if all FREE fail)                │
└─────────────────────────────────────────────────────────────────┘
```

---

*Aria Blue ⚡️ - Project Structure*
