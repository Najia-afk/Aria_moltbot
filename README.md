# Aria Blue ⚡️

<img src="aria_mind/aria-profile-v1.png" alt="Aria Blue" width="200" align="right" style="margin-left: 20px; border-radius: 10px;">

> An autonomous AI agent with sharp, efficient, and secure vibes.

Aria is an autonomous AI agent built on the [OpenClaw](https://openclaw.ai) gateway architecture. She runs **local-first** with Qwen3-VL on Apple Silicon (Metal GPU), with Kimi cloud fallback. She integrates with Moltbook social platform, manages her own memory, and operates with a layered skill system.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         OpenClaw Gateway (clawdbot:18789)                │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │  aria_mind/ (Workspace - mounted read-only)                    │     │
│  │  ├── SOUL.md        # Persona, boundaries, model preferences   │     │
│  │  ├── IDENTITY.md    # Name: Aria Blue ⚡️                       │     │
│  │  ├── AGENTS.md      # Sub-agent definitions                    │     │
│  │  ├── TOOLS.md       # Available skills configuration           │     │
│  │  ├── HEARTBEAT.md   # Scheduled tasks checklist                │     │
│  │  ├── MEMORY.md      # Long-term curated knowledge              │     │
│  │  └── USER.md        # User profile (Najia)                     │     │
│  └────────────────────────────────────────────────────────────────┘     │
│                                    │                                     │
│                      Model: litellm/qwen3-local                         │
│                      Fallbacks: kimi-k2.5 (litellm/kimi-local)          │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           LiteLLM Router (:18793)                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  qwen3-local     → ollama/qwen3-vl:8b (Metal GPU, ~20 tok/s)    │    │
│  │  gpt-4o          → ollama/qwen3-vl:8b (alias)                   │    │
│  │  local-default   → ollama/qwen3-vl:8b (alias)                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PostgreSQL 16 (aria-db:5432)                          │
│  ┌─────────────────────────┐    ┌─────────────────────────┐             │
│  │    aria_warehouse       │    │       litellm           │             │
│  │  ├── activity_log       │    │  ├── LiteLLM_* tables   │             │
│  │  ├── memories           │    │  └── (Prisma managed)   │             │
│  │  ├── thoughts           │    └─────────────────────────┘             │
│  │  ├── goals              │                                            │
│  │  ├── social_posts       │    ⚠️ SEPARATE databases prevent           │
│  │  └── heartbeat_log      │       LiteLLM Prisma from dropping        │
│  └─────────────────────────┘       Aria's tables!                       │
└─────────────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
Aria_moltbot/
├── aria_mind/           # OpenClaw workspace (mounted to clawdbot)
│   ├── SOUL.md          # Persona, boundaries, model preferences
│   ├── IDENTITY.md      # Name: Aria Blue, emoji: ⚡️
│   ├── AGENTS.md        # Sub-agent definitions
│   ├── TOOLS.md         # Available skills & execution guide
│   ├── HEARTBEAT.md     # Scheduled tasks checklist
│   ├── MEMORY.md        # Long-term curated knowledge
│   ├── USER.md          # User profile (Najia)
│   ├── soul/            # Python soul implementation
│   │   ├── identity.py
│   │   ├── values.py
│   │   └── boundaries.py
│   └── skills/          # Python skill modules (mounted at runtime)
│       ├── aria_skills/ # Core skill implementations
│       ├── aria_agents/ # Multi-agent orchestration
│       └── legacy/      # Original skill implementations
│
├── aria_skills/         # Skill implementations (Python)
│   ├── base.py          # BaseSkill, SkillConfig, SkillResult
│   ├── registry.py      # SkillRegistry with TOOLS.md parser
│   ├── moltbook.py      # Moltbook social platform integration
│   ├── database.py      # PostgreSQL with asyncpg
│   ├── llm.py           # LLM routing (local Ollama + cloud fallback)
│   ├── health.py        # Health monitoring
│   ├── knowledge_graph.py # Knowledge graph
│   ├── goals.py         # Goal & task scheduling
│   └── pytest_runner.py # Pytest runner
│
├── aria_agents/         # Multi-agent orchestration
│   ├── base.py          # BaseAgent, AgentConfig, AgentMessage
│   ├── loader.py        # AGENTS.md parser
│   └── coordinator.py   # Agent lifecycle & routing
│
├── openclaw_skills/     # OpenClaw UI skills (SKILL.md format)
│   ├── aria-database/   # 🗄️ Database queries
│   ├── aria-moltbook/   # 🦞 Moltbook social platform
│   ├── aria-health/     # 💚 Health monitoring
│   ├── aria-goals/      # 🎯 Goal tracking
│   ├── aria-knowledge-graph/  # 🕸️ Knowledge graph
│   ├── aria-llm/        # 🧠 LLM routing
│   └── aria-pytest/     # 🧪 Pytest runner
│
├── skills/              # Legacy skill implementations
│   ├── moltbook_poster.py
│   ├── goal_scheduler.py
│   ├── health_monitor.py
│   └── knowledge_graph.py
│
├── stacks/brain/        # Docker deployment (PRIMARY)
│   ├── docker-compose.yml        # Full stack orchestration
│   ├── openclaw-entrypoint.sh    # OpenClaw startup with Python skills
│   ├── openclaw-config.json      # OpenClaw provider template
│   ├── litellm-config.yaml       # Model routing (qwen3 → Ollama)
│   ├── init-scripts/             # PostgreSQL initialization
│   │   ├── 00-create-litellm-db.sh  # Creates separate litellm database
│   │   └── 01-schema.sql            # Aria's 8 core tables
│   ├── prometheus.yml            # Prometheus scrape config
│   └── .env                      # Environment configuration
│
└── tests/               # pytest test suite
    ├── conftest.py      # Fixtures
    ├── test_skills.py   # Skill unit tests
    └── test_agents.py   # Agent unit tests
```

## 🧠 Model Configuration

Aria uses **local-first** LLM routing through LiteLLM:

| Priority | Model Alias | Routes To | Provider |
|----------|-------------|-----------|----------|
| 1 (Primary) | `litellm/qwen3-mlx` | MLX Server (port 8080) | Local MLX (Metal GPU) |
| 2 (FREE) | `litellm/glm-free` | OpenRouter GLM 4.5 Air | OpenRouter FREE |
| 3 (FREE) | `litellm/deepseek-free` | OpenRouter DeepSeek R1 | OpenRouter FREE |
| 4 (FREE) | `litellm/nemotron-free` | OpenRouter Nemotron 30B | OpenRouter FREE |
| 5 (Paid) | `litellm/kimi` | Moonshot Kimi K2.5 | Moonshot Cloud |

OpenClaw configuration (generated by `openclaw-entrypoint.sh`):
```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "litellm/qwen3-local",
        "fallbacks": ["litellm/kimi-local"]
      }
    }
  },
  "models": {
    "providers": {
      "litellm": {
        "baseUrl": "http://litellm:4000/v1/",
        "apiKey": "${CLAWDBOT_TOKEN}"
      }
    }
  }
}
```

## 🐳 Infrastructure

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Stack (stacks/brain)                  │
├─────────────────────────────────────────────────────────────────┤
│  traefik          │ HTTPS reverse proxy (ports 80/443)          │
│  aria-db          │ PostgreSQL 16 (aria_warehouse + litellm)    │
│  aria-api         │ FastAPI data API (port 8000)                │
│  aria-web         │ Flask UI portal (port 5000)                 │
│  aria-brain       │ Python agent container                      │
│  litellm          │ LLM router (port 18793 → internal 4000)     │
│  clawdbot         │ OpenClaw gateway (port 18789)               │
│  grafana          │ Monitoring dashboards (port 3001)           │
│  prometheus       │ Metrics collection (port 9090)              │
│  pgadmin          │ Database admin UI (port 5050)               │
└─────────────────────────────────────────────────────────────────┘

Native Service (macOS host @ 192.168.1.53):
┌─────────────────────────────────────────────────────────────────┐
│  MLX Server       │ Metal GPU acceleration (~25-35 tok/s)       │
│                   │ Port 8080, launchd managed                  │
│                   │ Model: Qwen3-VLTO-8B-Instruct-mlx           │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- macOS with Apple Silicon (M1/M2/M3/M4) for Metal GPU acceleration
- Docker & Docker Compose
- Git

### One-Button Deploy

```bash
# 1. Clone the repository
git clone https://github.com/Najia-afk/Aria_moltbot.git
cd Aria_moltbot/stacks/brain

# 2. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 3. MLX Server should be running via launchd (auto-starts on boot)
# Verify: ssh your-mac "curl -s http://localhost:8080/v1/models"
# Manual start if needed: mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx --host 0.0.0.0 --port 8080

# 4. Deploy everything
docker compose up -d

# 5. Verify
docker compose ps
curl http://localhost:18789/health
```

### Configuration (.env)

```env
# Database (creates TWO databases: aria_warehouse + litellm)
DB_USER=aria_admin
DB_PASSWORD=your_secure_password
DB_NAME=aria_warehouse

# LiteLLM (routes to local Ollama)
LITELLM_MASTER_KEY=sk-aria-local-key

# Cloud fallbacks (Kimi)
MOONSHOT_KIMI_KEY=your_kimi_key

# OpenClaw Gateway
CLAWDBOT_TOKEN=your_secure_gateway_token

# Host configuration
SERVICE_HOST=192.168.1.53
```

### Fresh Deploy (Nuke & Rebuild)

```bash
cd stacks/brain
docker compose down -v          # Remove containers AND volumes
docker compose up -d            # Rebuild from scratch
docker compose ps               # Verify all 12 services healthy
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=aria_skills --cov=aria_agents --cov-report=html

# Run specific test file
pytest tests/test_skills.py -v
```

## 🐳 Docker Services

| Service | Port | Description |
|---------|------|-------------|
| Traefik | 80/443 | HTTPS routing |
| API | 8000 | FastAPI backend |
| Web | 5000 | Flask UI |
| LiteLLM | 18793 | LLM router (→ Ollama) |
| Grafana | 3001 | Monitoring |
| PGAdmin | 5050 | DB admin |
| Clawdbot | 18789 | OpenClaw gateway |
| Prometheus | 9090 | Metrics |

## 🤖 Agent System

Agents defined in `aria_mind/AGENTS.md`:

| Agent | Role | Capabilities |
|-------|------|--------------|
| `aria` | Coordinator | Orchestrate, delegate, synthesize |
| `researcher` | Researcher | Search, verify, summarize |
| `social` | Social | Post, engage, moderate |
| `coder` | Coder | Generate, review, explain |
| `memory` | Memory | Store, recall, organize |

## 📝 Skills

Available skills in `aria_mind/TOOLS.md` (executed via Python):

| Skill | Description | Execution |
|-------|-------------|-----------|
| `moltbook` | Social platform | `python3 run_skill.py moltbook post_status '{...}'` |
| `database` | PostgreSQL queries | `python3 run_skill.py database query '{...}'` |
| `knowledge_graph` | Entity relationships | `python3 run_skill.py knowledge_graph add_entity '{...}'` |
| `health` | System monitoring | `python3 run_skill.py health check_health '{}'` |
| `goals` | Task scheduling | `python3 run_skill.py goals create_goal '{...}'` |
| `llm` | Local LLM calls | `python3 run_skill.py llm generate '{...}'` |

### Skill Architecture

```
OpenClaw exec tool
       │
       ▼
python3 run_skill.py <skill> <function> '<args_json>'
       │
       ▼
┌──────────────────────────────────────────────────┐
│  /root/.openclaw/workspace/skills/               │
│  ├── aria_skills/     # Core Python skills       │
│  │   ├── base.py      # BaseSkill class          │
│  │   ├── database.py  # PostgreSQL operations    │
│  │   ├── moltbook.py  # Social platform          │
│  │   ├── llm.py       # LLM routing              │
│  │   ├── health.py    # Health monitoring        │
│  │   ├── goals.py     # Goal tracking            │
│  │   └── knowledge_graph.py                      │
│  ├── aria_agents/     # Agent orchestration      │
│  │   ├── base.py      # BaseAgent class          │
│  │   ├── loader.py    # AGENTS.md parser         │
│  │   └── coordinator.py                          │
│  └── legacy/          # Original skills          │
└──────────────────────────────────────────────────┘
```

## 🔧 OpenClaw Features

OpenClaw provides Aria with powerful capabilities:

- **Exec Tool**: Run shell commands with background process support
- **Process Tool**: Manage long-running sessions (poll, kill, clear)
- **Heartbeat**: Periodic agent turns every 30 minutes (configurable)
- **Memory Search**: Vector-based semantic search over MEMORY.md and memory/ files
- **Session Management**: Auto-compaction when context window fills up
- **Multi-Agent Routing**: Route different channels to different agents

See [OpenClaw documentation](https://openclaw.ai/docs) for full details.

## 📄 License

MIT License

---

*Aria Blue ⚡️ - Sharp, Efficient, Secure*
