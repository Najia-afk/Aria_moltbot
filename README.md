# Aria Blue ⚡️

> An autonomous AI agent with sharp, efficient, and secure vibes.

Aria is an autonomous AI agent built on the [OpenClaw](https://github.com/openclaw/openclaw) architecture. She integrates with Moltbook social platform, manages her own memory, and operates with a layered skill system.

## 🏗️ Architecture

```
aria_mind/           # Core identity & configuration (OpenClaw workspace)
├── SOUL.md          # Persona, boundaries, guidelines
├── IDENTITY.md      # Name, emoji, avatar, handles
├── AGENTS.md        # Sub-agent definitions
├── TOOLS.md         # Available skills configuration
├── HEARTBEAT.md     # Scheduled tasks, health checks
├── BOOTSTRAP.md     # Initialization sequence
├── MEMORY.md        # Long-term knowledge
└── USER.md          # User profile

aria_skills/         # API-safe skill interfaces
├── base.py          # BaseSkill, SkillConfig, SkillResult
├── registry.py      # SkillRegistry with TOOLS.md parser
├── moltbook.py      # Moltbook social platform
├── database.py      # PostgreSQL with asyncpg
├── llm.py           # LLM skills (local + cloud)
├── health.py        # Health monitoring
└── goals.py         # Goal & task scheduling

aria_agents/         # Multi-agent orchestration
├── base.py          # BaseAgent, AgentConfig, AgentMessage
├── loader.py        # AGENTS.md parser
└── coordinator.py   # Agent lifecycle & routing

tests/               # pytest test suite
├── conftest.py      # Fixtures
├── test_skills.py   # Skill unit tests
├── test_agents.py   # Agent unit tests
└── test_integration.py  # End-to-end tests
```

## Infrastructure

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Stack                             │
├─────────────────────────────────────────────────────────────┤
│  traefik          │ HTTPS reverse proxy                     │
│  aria-db          │ PostgreSQL database                     │
│  aria-api         │ FastAPI data API                        │
│  aria-web         │ Flask UI portal                         │
│  aria-brain       │ Main agent container                    │
│  litellm          │ LLM router                              │
│  grafana          │ Monitoring dashboards                   │
│  prometheus       │ Metrics collection                      │
│  pgadmin          │ Database admin UI                       │
│  clawdbot         │ OpenClaw gateway                        │
└─────────────────────────────────────────────────────────────┘

Native Ollama (Metal GPU) runs alongside Docker for optimal performance.
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- macOS with Apple Silicon (for native Ollama with Metal GPU)

### Installation

```bash
# Clone the repository
git clone https://github.com/aria-blue/aria.git
cd aria

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"
```

### Configuration

Copy `stacks/brain/.env.example` to `stacks/brain/.env` and fill in your values:

```env
# Database
DB_USER=aria_admin
DB_PASSWORD=YOUR_PASSWORD
DB_NAME=aria_warehouse

# Native Ollama (Metal GPU - runs on host, not Docker)
OLLAMA_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3-vl:8b

# LLM APIs (fallback)
GOOGLE_GEMINI_KEY=your_gemini_key
MOONSHOT_KIMI_KEY=your_moonshot_key
```

### Running Native Ollama (Metal GPU)

On macOS with Apple Silicon, run Ollama natively for GPU acceleration:

```bash
# Start native Ollama (Metal GPU)
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# In another terminal, pull the model
ollama pull qwen3-vl:8b
```

### Running Docker Stack

```bash
cd stacks/brain
docker compose up -d
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
| LiteLLM | 18793 | LLM router |
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

Available skills in `aria_mind/TOOLS.md`:

| Skill | Description | Rate Limit |
|-------|-------------|------------|
| `moltbook` | Social platform | 5/hr, 20/day |
| `database` | PostgreSQL | - |
| `gemini` | Google LLM | 60/min |
| `moonshot` | Moonshot LLM | 10/min |
| `health_monitor` | System health | - |
| `goal_scheduler` | Task scheduling | - |

## 📄 License

MIT License

---

*Aria Blue ⚡️ - Sharp, Efficient, Secure*
