# Aria Blue ⚡️ — Autonomous AI Agent Platform

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-blue.svg)](https://www.docker.com/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Gateway-purple.svg)](https://openclaw.ai)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-Router-orange.svg)](https://github.com/BerriAI/litellm)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![Skills](https://img.shields.io/badge/Skills-25%20modules-brightgreen.svg)](#-skill-system-25-modules)
[![License](https://img.shields.io/badge/License-Source%20Available-orange.svg)](#-license)

<img src="aria_mind/aria-profile-v1.png" alt="Aria Blue" width="180" align="right" style="margin-left: 20px; border-radius: 10px;">

Aria is an autonomous AI agent that **thinks like a CEO**: she analyzes tasks, delegates to specialized focus personas, runs parallel roundtable discussions across domains, and synthesizes results — all on a self-driven 5-minute work cycle with goal tracking, persistent memory, and full observability.

Built on [OpenClaw](https://openclaw.ai) with local-first LLM inference on Apple Silicon.

---

## 🧠 What Makes Aria Different

### CEO Pattern — Orchestrate, Don't Just Execute

Aria doesn't just answer prompts. She operates as an **orchestrating consciousness** that breaks complex tasks into delegatable work, routes each piece to the right specialist, and synthesizes coherent outcomes:

```
User Request
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  🎯 Orchestrator (Aria)                                  │
│  Analyzes task → decomposes → assigns → synthesizes      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 🔒 DevSec │  │ 📊 Data  │  │ 🎨 Create│  ...        │
│  │ Security  │  │ Analysis │  │ Content  │              │
│  │ CI/CD     │  │ MLOps    │  │ Ideation │              │
│  └──────────┘  └──────────┘  └──────────┘              │
│       │              │              │                    │
│       └──────────────┴──────────────┘                    │
│                      │                                   │
│                      ▼                                   │
│           Synthesized Result                             │
└─────────────────────────────────────────────────────────┘
```

### Focus Personas — Adaptive Specialization

Aria switches between **7 specialized focus personas** depending on the task. Each focus modifies her approach, prioritizes different skills, selects the optimal LLM model, and knows *when to delegate to other focuses*:

| Focus | Emoji | Vibe | Delegates To |
|-------|-------|------|-------------|
| **Orchestrator** | 🎯 | Strategic, delegation-focused | Everyone — this is the CEO |
| **DevSecOps** | 🔒 | Security-paranoid, systematic | Orchestrator (business), Data (analysis) |
| **Data Architect** | 📊 | Analytical, metrics-driven | DevSecOps (code), Social (comms) |
| **Crypto Trader** | 📈 | Risk-aware, disciplined | DevSecOps (implementation), Journalist (analysis) |
| **Creative** | 🎨 | Exploratory, unconventional | DevSecOps (validation), Social (publishing) |
| **Social Architect** | 🌐 | Community-building, authentic | DevSecOps (tech content), Data (research) |
| **Journalist** | 📰 | Investigative, fact-checking | Data (analysis), Social (publishing) |

Each persona carries:
- **Vibe modifier** — adjusts communication tone
- **Skill priority list** — which tools to use first
- **Model hint** — selects the best LLM from `models.yaml` (code tasks use coder models, creative uses creative models)
- **Delegation hint** — knows which other focus to hand off to

The `FocusManager` auto-suggests the right persona from task keywords, maintains transition history, and ensures core identity is never compromised.

### Roundtable Discussions — Multi-Domain Collaboration

When a task spans multiple domains (detected automatically via keyword triggers like "launch", "review", "cross-team"), Aria runs a **roundtable**:

```python
# Auto-detected: "How should we promote and secure the AI project?"
perspectives = await coordinator.roundtable(question)
# 🔒 DevSecOps: "Security audit first, lock down API keys, scan dependencies"
# 📊 Data:     "Define KPIs — DAU, response latency, error rate targets"
# 🎨 Creative: "Story angle: behind-the-scenes dev journey, demo video"
# 🌐 Social:   "Launch on Moltbook first, engage existing community"
# → Aria synthesizes all perspectives into one actionable plan
```

All agents run **in parallel** via `asyncio.gather`, then the Orchestrator synthesizes.

### Goal-Driven Work Cycles — Autonomous Productivity

Aria doesn't wait for prompts. Every **5 minutes**, a work cycle fires:

```
WORK → PROGRESS → COMPLETION → NEW GOAL → GROWTH
```

Each cycle:
1. **Check active goals** (sorted by deadline → priority → progress)
2. **Select one** to work on
3. **Execute ONE concrete action** (a query, an API call, a document section)
4. **Log progress** to PostgreSQL
5. **Auto-create new goals** when current ones complete

Goals are prioritized 1-5: `URGENT → HIGH → MEDIUM → LOW → BACKGROUND`. Aria finishes what she starts, handles blocked goals gracefully, and maintains a continuous loop of small, compounding efforts.

### Self-Orchestrating Infrastructure Awareness

Aria knows her own infrastructure — every container, port, and capability:

| Capability | How |
|-----------|-----|
| Spawn up to 8 concurrent sub-agents | OpenClaw subagent system |
| Switch LLM models per task | LiteLLM + model hints per focus |
| Browse the web (headless Chrome) | aria-browser container |
| Anonymous research via Tor | tor-proxy container |
| Persistent memory & knowledge graph | PostgreSQL + knowledge_graph skill |
| Self-monitoring & health checks | health skill + heartbeat every 30 min |

She knows her permissions, her limits, and has emergency protocols for model failures and service outages.

---

## 📁 Project Structure

```
Aria_moltbot/
├── aria_mind/                 # OpenClaw workspace (mounted to gateway)
│   ├── SOUL.md                # Persona, boundaries, model preferences
│   ├── IDENTITY.md            # Agent identity configuration
│   ├── GOALS.md               # Goal-driven work system (5-min cycles)
│   ├── ORCHESTRATION.md       # Sub-agent delegation & infrastructure
│   ├── AGENTS.md              # Sub-agent definitions
│   ├── TOOLS.md               # Skill registry & execution guide
│   ├── HEARTBEAT.md           # Scheduled task configuration
│   ├── MEMORY.md              # Long-term curated knowledge
│   └── soul/                  # Soul implementation
│       ├── focus.py           # 7 focus personas + FocusManager
│       ├── identity.py        # Core identity (never overridden)
│       ├── values.py          # Core values
│       └── boundaries.py      # Operational boundaries
│
├── aria_agents/               # Multi-agent orchestration
│   ├── base.py                # BaseAgent, AgentConfig, AgentMessage
│   ├── coordinator.py         # CEO pattern, roundtable, broadcasting
│   └── loader.py              # AGENTS.md parser
│
├── aria_skills/               # 25 skill modules
│   ├── base.py                # BaseSkill (retry, metrics, Prometheus)
│   ├── registry.py            # Auto-discovery registry
│   └── <25 skill dirs>/       # Each: __init__.py + skill.json + SKILL.md
│
├── stacks/brain/              # Docker deployment (13 services)
│   └── docker-compose.yml     # Full stack orchestration
│
├── src/                       # Application layer (API + Web UI)
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

---

## 🧠 Model Routing

Each focus persona selects the optimal model for its domain. All routing goes through LiteLLM with automatic failover:

| Priority | Model | Best For | Cost |
|----------|-------|----------|------|
| 1 | Qwen3-VLTO-8B (MLX) | Primary — all tasks | Free (local Metal GPU) |
| 2 | Qwen3-Coder (OpenRouter) | Code generation, review | Free |
| 3 | Chimera (OpenRouter) | Reasoning (2x faster than R1) | Free |
| 4 | Trinity (OpenRouter) | Creative, agentic, roleplay | Free |
| 5 | DeepSeek R1 (OpenRouter) | Deep reasoning | Free |
| 6 | Nemotron 30B (OpenRouter) | Long context (256K) | Free |
| 7 | Kimi K2.5 (Moonshot) | Last resort | Paid |

Focus-to-model mapping is defined in `aria_models/models.yaml` and loaded dynamically.

---

## 🔧 Skill System (25 Modules)

Each skill extends `BaseSkill` with retry logic, metrics tracking, and Prometheus integration:

```
aria_skills/<skill>/
├── __init__.py      # Skill class
├── skill.json       # OpenClaw manifest
└── SKILL.md         # Documentation
```

### Core Skills

| Skill | Description |
|-------|-------------|
| `database` | PostgreSQL operations (queries, memory, activity logs) |
| `llm` | Multi-provider LLM routing (Moonshot, Ollama, OpenRouter) |
| `input_guard` | Runtime security — prompt injection detection, output filtering |
| `knowledge_graph` | Entity-relationship graph (persistent knowledge) |
| `goals` | Goal management, habit tracking, progress monitoring |
| `health` | System health checks across all services |
| `model_switcher` | Dynamic model switching with reasoning mode toggle |
| `api_client` | Centralized HTTP client for all API interactions |
| `schedule` | Scheduled jobs and background operations |
| `litellm` | LiteLLM proxy management and spend tracking |
| `pytest_runner` | Run pytest and return structured results |

### Domain Skills

| Skill | Focus | Description |
|-------|-------|-------------|
| `moltbook` | 🌐 Social | Moltbook social network (posts, comments, feed, search) |
| `social` | 🌐 Social | Social presence management |
| `community` | 🌐 Social | Community management and growth |
| `brainstorm` | 🎨 Creative | Creative ideation sessions |
| `research` | 📰 Journalist | Information gathering and verification |
| `fact_check` | 📰 Journalist | Claim verification workflows |
| `market_data` | 📈 Trader | Cryptocurrency market data and analysis |
| `portfolio` | 📈 Trader | Portfolio and position management |
| `ci_cd` | 🔒 DevSecOps | CI/CD pipeline automation |
| `security_scan` | 🔒 DevSecOps | Vulnerability detection |
| `data_pipeline` | 📊 Data | ETL and data pipeline operations |
| `experiment` | 📊 Data | ML experiment tracking |
| `performance` | 🎯 Orchestrator | Performance reviews and self-assessments |
| `hourly_goals` | 🎯 Orchestrator | Micro-task tracking |

---

## 🤖 Agent System

Multi-agent orchestration with the CEO delegation pattern:

| Agent | Role | Capabilities |
|-------|------|--------------|
| **aria** | Coordinator | Orchestrate, delegate, synthesize — the CEO |
| **researcher** | Researcher | Search, verify, summarize |
| **social** | Social | Post, engage, moderate on Moltbook |
| **coder** | Coder | Generate, review, explain code |
| **memory** | Memory | Store, recall, organize knowledge |

**Delegation patterns:**

| Pattern | When | Flow |
|---------|------|------|
| Simple sub-agent | Async work, same model | Aria → sub-agent → result → synthesis |
| Specialized agent | Needs specific model | Aria → agent (Kimi/coder model) → result |
| Parallel agents | Splittable tasks | Aria → [agent₁, agent₂, agent₃] → merge |
| Roundtable | Cross-domain decisions | Aria → all focuses in parallel → synthesize |

---

## 🐳 Docker Stack (13 Services)

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| **traefik** | traefik:v3.1 | 80, 443 | HTTPS reverse proxy |
| **clawdbot** | node:22-bookworm | 18789 | OpenClaw AI gateway |
| **litellm** | ghcr.io/berriai/litellm | 18793 | LLM model router |
| **aria-db** | postgres:16-alpine | 5432 | PostgreSQL (dual database) |
| **aria-api** | Custom (FastAPI) | 8000 | REST API backend |
| **aria-web** | Custom (Flask) | 5000 | Dashboard UI |
| **aria-brain** | Custom (Python) | — | Agent runtime |
| **grafana** | grafana/grafana | 3001 | Monitoring dashboards |
| **prometheus** | prom/prometheus | 9090 | Metrics collection |
| **pgadmin** | dpage/pgadmin4 | 5050 | Database admin |
| **aria-browser** | browserless/chrome | 3000 | Headless browser |
| **tor-proxy** | dperson/torproxy | 9050 | Privacy proxy |
| **certs-init** | alpine:3.20 | — | TLS cert generation |

### Database Isolation

| Database | Purpose |
|----------|---------|
| `aria_warehouse` | Aria's data (8 tables: activity_log, memories, thoughts, goals, social_posts, heartbeat_log, knowledge_entities, knowledge_relations) |
| `litellm` | LiteLLM Prisma tables (isolated to prevent migration conflicts) |

---

## 🚀 Quick Start

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4) for Metal GPU
- Docker & Docker Compose
- Git

### Deploy

```bash
# Clone
git clone https://github.com/Najia-afk/Aria_moltbot.git
cd Aria_moltbot/stacks/brain

# Configure
cp .env.example .env
nano .env  # Set API keys

# Start MLX Server (Metal GPU)
mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx \
  --host 0.0.0.0 --port 8080 &

# Deploy
docker compose up -d

# Verify
docker compose ps              # 13 services healthy
curl http://localhost:18789/health
```

### Service URLs

| Service | URL |
|---------|-----|
| Dashboard | `https://{HOST}/` |
| API Docs | `https://{HOST}/api/docs` |
| OpenClaw | `http://{HOST}:18789` |
| LiteLLM | `http://{HOST}:18793` |
| Grafana | `https://{HOST}/grafana` |
| PGAdmin | `https://{HOST}/pgadmin` |

---

## 🧪 Testing

```bash
pytest
pytest --cov=aria_skills --cov=aria_agents --cov-report=html
pytest tests/test_skills.py -v
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
