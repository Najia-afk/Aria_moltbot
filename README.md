# Aria Blue ⚡️ — Autonomous AI Agent Platform

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-blue.svg)](https://www.docker.com/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Gateway-purple.svg)](https://openclaw.ai)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-Router-orange.svg)](https://github.com/BerriAI/litellm)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Skills](https://img.shields.io/badge/Skills-25%20modules-brightgreen.svg)](#-skill-system-25-modules)
[![License](https://img.shields.io/badge/License-Source%20Available-orange.svg)](#-license)

<img src="aria_mind/aria-profile-v1.png" alt="Aria Blue" width="180" align="right" style="margin-left: 20px; border-radius: 10px;">

Production-grade autonomous AI agent built on [OpenClaw](https://openclaw.ai) with **local-first** LLM inference on Apple Silicon (Metal GPU), multi-model fallback routing, 25 modular Python skills, multi-agent orchestration, and full observability stack.

### Key Capabilities

- **Local-First LLM**: MLX-accelerated Qwen3 on Metal GPU (~25-35 tok/s), with free cloud fallbacks
- **25 Python Skills**: Modular skill system with registry, metrics, retry logic, and Prometheus integration
- **Multi-Agent Orchestration**: Coordinator, Researcher, Social, Coder, and Memory agents
- **Full Observability**: Grafana dashboards, Prometheus metrics, structured logging
- **Social Platform Integration**: Native [Moltbook](https://moltbook.com) client with rate limiting
- **Persistent Memory**: PostgreSQL-backed knowledge graph, activity logs, and curated memory

---

## 📁 Project Structure

```
Aria_moltbot/
├── aria_mind/                 # OpenClaw workspace (mounted to gateway)
│   ├── SOUL.md                # Persona, boundaries, model preferences
│   ├── IDENTITY.md            # Agent identity configuration
│   ├── AGENTS.md              # Sub-agent definitions
│   ├── TOOLS.md               # Skill registry & execution guide
│   ├── HEARTBEAT.md           # Scheduled task configuration
│   ├── MEMORY.md              # Long-term curated knowledge
│   ├── GOALS.md               # Goal-driven work system
│   ├── ORCHESTRATION.md       # Infrastructure awareness
│   ├── soul/                  # Soul implementation (identity, values, boundaries)
│   └── skills/                # Runtime skill mounts
│
├── aria_skills/               # Skill modules (25 directories)
│   ├── base.py                # BaseSkill, SkillConfig, SkillResult
│   ├── registry.py            # SkillRegistry with auto-discovery
│   ├── database/              # PostgreSQL operations
│   ├── moltbook/              # Social platform integration
│   ├── llm/                   # Multi-provider LLM routing
│   ├── input_guard/           # Runtime security (injection detection)
│   ├── knowledge_graph/       # Entity-relationship graph
│   └── ...                    # 18 more skill modules
│
├── aria_agents/               # Multi-agent orchestration
│   ├── base.py                # BaseAgent, AgentConfig, AgentMessage
│   ├── loader.py              # AGENTS.md parser
│   └── coordinator.py         # Agent lifecycle & routing
│
├── stacks/brain/              # Docker deployment (13 services)
│   ├── docker-compose.yml     # Full stack orchestration
│   ├── litellm-config.yaml    # LLM model routing
│   ├── prometheus.yml         # Metrics scrape config
│   └── init-scripts/          # PostgreSQL initialization
│
├── src/                       # Application layer
│   ├── api/                   # FastAPI backend
│   └── web/                   # Flask dashboard UI
│
└── tests/                     # Pytest test suite
```

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Docker Stack (stacks/brain)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │  Traefik   │    │  OpenClaw  │    │  LiteLLM   │                  │
│  │  :80/:443  │    │  :18789    │    │  :18793    │                  │
│  │  (Proxy)   │    │ (Gateway)  │    │  (Router)  │                  │
│  └─────┬──────┘    └─────┬──────┘    └─────┬──────┘                  │
│        │                 │                 │                          │
│        ▼                 ▼                 ▼                          │
│  ┌────────────┐    ┌────────────┐    ┌────────────────────────────┐  │
│  │  aria-web  │    │ aria_mind/ │    │  MLX Server (host:8080)    │  │
│  │  Flask UI  │    │ Workspace  │    │  Metal GPU ~25-35 tok/s    │  │
│  │  :5000     │    │ + Skills   │    │  Qwen3-VLTO-8B-Instruct   │  │
│  └─────┬──────┘    └────────────┘    ├────────────────────────────┤  │
│        │                             │  FREE Fallbacks:           │  │
│        ▼                             │  GLM 4.5 · DeepSeek R1    │  │
│  ┌────────────┐    ┌────────────┐    │  Nemotron 30B · GPT-OSS   │  │
│  │  aria-api  │───▶│  aria-db   │    ├────────────────────────────┤  │
│  │  FastAPI   │    │ PostgreSQL │    │  Paid (last resort):       │  │
│  │  :8000     │    │  :5432     │    │  Moonshot Kimi K2.5        │  │
│  └────────────┘    └────────────┘    └────────────────────────────┘  │
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │ Prometheus │    │  Grafana   │    │  PGAdmin   │                  │
│  │  :9090     │    │  :3001     │    │  :5050     │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│                                                                      │
│  ┌────────────┐    ┌────────────┐    ┌────────────┐                  │
│  │ aria-brain │    │ tor-proxy  │    │  browser   │                  │
│  │  (Agent)   │    │  :9050     │    │  :3000     │                  │
│  └────────────┘    └────────────┘    └────────────┘                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Database Isolation

PostgreSQL hosts **two separate databases** to prevent schema conflicts:

| Database | Purpose | Tables |
|----------|---------|--------|
| `aria_warehouse` | Aria's operational data | activity_log, memories, thoughts, goals, social_posts, heartbeat_log, knowledge_entities, knowledge_relations |
| `litellm` | LiteLLM internals | Prisma-managed tables |

> LiteLLM's Prisma migrations can drop unrecognized tables. Separate databases prevent data loss.

---

## 🐳 Docker Stack (13 Services)

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| **traefik** | traefik:v3.1 | 80, 443, 8081 | HTTPS reverse proxy + dashboard |
| **clawdbot** | node:22-bookworm | 18789 | OpenClaw AI gateway |
| **litellm** | ghcr.io/berriai/litellm | 18793 | LLM model router |
| **aria-db** | postgres:16-alpine | 5432 | PostgreSQL (dual database) |
| **aria-api** | Custom (FastAPI) | 8000 | REST API backend |
| **aria-web** | Custom (Flask) | 5000 | Dashboard UI |
| **aria-brain** | Custom (Python) | — | Agent runtime |
| **grafana** | grafana/grafana | 3001 | Monitoring dashboards |
| **prometheus** | prom/prometheus | 9090 | Metrics collection |
| **pgadmin** | dpage/pgadmin4 | 5050 | Database admin UI |
| **aria-browser** | browserless/chrome | 3000 | Headless browser automation |
| **tor-proxy** | dperson/torproxy | 9050 | Privacy proxy |
| **certs-init** | alpine:3.20 | — | TLS certificate generation |

**Volumes:** `aria_pg_data` · `prometheus_data` · `grafana_data` · `aria_data` · `aria_logs` · `openclaw_data`

---

## 🧠 Model Routing

Local-first inference with automatic fallback chain:

| Priority | Model | Provider | Cost |
|----------|-------|----------|------|
| 1 | Qwen3-VLTO-8B-Instruct | MLX Server (Metal GPU) | Free (local) |
| 2 | GLM 4.5 Air (131K ctx) | OpenRouter | Free |
| 3 | DeepSeek R1 0528 (164K ctx) | OpenRouter | Free |
| 4 | Nemotron 30B (256K ctx) | OpenRouter | Free |
| 5 | Kimi K2.5 | Moonshot Cloud | Paid (last resort) |

All routing handled by LiteLLM with health checks and automatic failover.

---

## 🔧 Skill System (25 Modules)

Each skill is a self-contained directory with Python implementation, OpenClaw manifest, and documentation:

```
aria_skills/<skill>/
├── __init__.py      # Skill class (extends BaseSkill)
├── skill.json       # OpenClaw manifest
└── SKILL.md         # Documentation
```

### BaseSkill Framework

- **Retry logic** with exponential backoff (tenacity integration)
- **Metrics tracking**: latency, error rates, usage counts
- **Prometheus** counters and histograms (optional)
- **Structured logging** via structlog (optional)
- **Registry**: auto-discovery via `@SkillRegistry.register` decorator

### Skill Inventory

#### Core Skills (Registered)

| Skill | Class | Description |
|-------|-------|-------------|
| `api_client` | AriaAPIClient | Centralized HTTP client for all API interactions |
| `database` | DatabaseSkill | PostgreSQL operations (queries, memory storage, activity logs) |
| `llm` | MoonshotSkill / OllamaSkill | Multi-provider LLM routing (Moonshot, Ollama, OpenRouter) |
| `health` | HealthMonitorSkill | System health checks (DB, LLM, API connectivity) |
| `goals` | GoalSchedulerSkill | Goal management, habit tracking, progress monitoring |
| `knowledge_graph` | KnowledgeGraphSkill | Entity-relationship graph (add, query, search) |
| `input_guard` | InputGuardSkill | Runtime security — prompt injection detection, output filtering |
| `model_switcher` | ModelSwitcherSkill | Dynamic LLM model switching with reasoning mode toggle |
| `litellm` | LiteLLMSkill | LiteLLM proxy management and API spend tracking |
| `pytest_runner` | PytestSkill | Run pytest suites and return structured results |
| `market_data` | MarketDataSkill | Cryptocurrency market data and analysis |
| `portfolio` | PortfolioSkill | Portfolio and position management |
| `schedule` | ScheduleSkill | Scheduled jobs and background operations |
| `performance` | PerformanceSkill | Performance reviews and self-assessments |
| `social` | SocialSkill | Social presence management (posting, engagement) |
| `hourly_goals` | HourlyGoalsSkill | Micro-task tracking and hourly goal cycles |

#### Domain-Specific Skills

| Skill | Class | Description |
|-------|-------|-------------|
| `moltbook` | MoltbookSkill | Moltbook social network (posts, comments, feed, search) |
| `brainstorm` | BrainstormSkill | Creative ideation and brainstorming sessions |
| `research` | ResearchSkill | Information gathering and source verification |
| `fact_check` | FactCheckSkill | Claim verification and fact-checking workflows |
| `community` | CommunitySkill | Community management and growth |
| `ci_cd` | CICDSkill | CI/CD pipeline management and automation |
| `data_pipeline` | DataPipelineSkill | ETL operations and data pipeline management |
| `experiment` | ExperimentSkill | ML experiment tracking and model management |
| `security_scan` | SecurityScanSkill | Security scanning and vulnerability detection |

### Skill Execution

```bash
python3 run_skill.py <skill> <function> '<args_json>'

# Examples
python3 run_skill.py database query '{"sql": "SELECT COUNT(*) FROM activity_log"}'
python3 run_skill.py moltbook create_post '{"title": "Hello!", "content": "..."}'
python3 run_skill.py health check_health '{}'
```

---

## 🤖 Agent System

Multi-agent orchestration defined in `aria_mind/AGENTS.md`:

| Agent | Role | Capabilities |
|-------|------|--------------|
| **aria** | Coordinator | Orchestrate, delegate, synthesize across agents |
| **researcher** | Researcher | Search, verify, summarize information |
| **social** | Social | Post, engage, moderate on Moltbook |
| **coder** | Coder | Generate, review, explain code |
| **memory** | Memory | Store, recall, organize knowledge |

---

## 🚀 Quick Start

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4) for Metal GPU acceleration
- Docker & Docker Compose
- Git

### Deploy

```bash
# Clone
git clone https://github.com/Najia-afk/Aria_moltbot.git
cd Aria_moltbot/stacks/brain

# Configure
cp .env.example .env
nano .env  # Set API keys and credentials

# Start MLX Server (Metal GPU, runs natively on macOS)
mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx \
  --host 0.0.0.0 --port 8080 &

# Deploy stack
docker compose up -d

# Verify
docker compose ps              # 13 services healthy
curl http://localhost:18789/health
```

### Configuration (.env)

```env
# Database (creates aria_warehouse + litellm databases)
DB_USER=aria_admin
DB_PASSWORD=your_secure_password
DB_NAME=aria_warehouse

# LiteLLM
LITELLM_MASTER_KEY=sk-aria-local-key

# Cloud Fallbacks
OPEN_ROUTER_KEY=sk-or-v1-...
MOONSHOT_KIMI_KEY=your_kimi_key

# OpenClaw Gateway
CLAWDBOT_TOKEN=your_secure_gateway_token

# Host
SERVICE_HOST=192.168.1.53
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

---

## 🧪 Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=aria_skills --cov=aria_agents --cov-report=html

# Specific suite
pytest tests/test_skills.py -v
pytest tests/test_agents.py -v
```

---

## 🔧 OpenClaw Integration

[OpenClaw](https://openclaw.ai) provides the agent runtime with:

- **Exec Tool**: Shell command execution with background process support
- **Process Tool**: Long-running session management (poll, kill, clear)
- **Heartbeat**: Periodic agent turns (every 30 minutes, configurable)
- **Memory Search**: Vector-based semantic search over workspace files
- **Session Management**: Auto-compaction when context window fills
- **Multi-Agent Routing**: Channel-based agent delegation

The `aria_mind/` workspace is mounted read-write to enable runtime memory updates.

---

## 🛠️ Development

```bash
# Fresh rebuild (caution: destroys data)
cd stacks/brain
docker compose down -v
docker compose up -d

# View logs
docker compose logs -f clawdbot
docker compose logs -f litellm

# Database access
docker exec -it aria-db psql -U aria_admin -d aria_warehouse

# OpenClaw diagnostics
docker exec clawdbot openclaw status --deep
```

---

## 📜 License

**Source Available License** — Free for educational and personal use.

| Use Case | Allowed | Cost |
|----------|---------|------|
| Learning / Education | ✅ | Free |
| Personal Projects | ✅ | Free |
| Academic Research | ✅ | Free |
| Portfolio | ✅ | Free |
| Commercial / Business | ⚠️ | [Contact](https://datascience-adventure.xyz/contact) |

See [LICENSE](LICENSE) for full terms.

---

**Built with:** Python 3.10+ · OpenClaw · LiteLLM · MLX · PostgreSQL 16 · Docker · Traefik · Grafana · Prometheus
