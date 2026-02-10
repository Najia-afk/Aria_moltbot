# Aria Blue ⚡️ — Deployment & Operations Guide

Complete deployment and operations guide for the Aria stack with OpenClaw integration.

---

## Architecture Overview

Aria runs on [OpenClaw](https://openclaw.ai) with a **local-first** LLM strategy:

```
┌──────────────────────────────────────────────────────────────────┐
│  OpenClaw Gateway (clawdbot)                                      │
│  ├── Model: litellm/qwen3-mlx (primary — MLX on Apple Silicon)   │
│  ├── Fallbacks: glm-free, deepseek-free, kimi (paid last resort) │
│  └── Workspace: aria_mind/ (mounted read-write)                  │
├──────────────────────────────────────────────────────────────────┤
│  LiteLLM Router → MLX Server (port 8080, Metal GPU)              │
│  Model: nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx          │
├──────────────────────────────────────────────────────────────────┤
│  PostgreSQL: aria_warehouse (Aria) + litellm (LiteLLM separate)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- **macOS with Apple Silicon** (M1/M2/M3/M4) for Metal GPU acceleration
- Docker & Docker Compose
- Git
- SSH access to deployment host (for remote deployment)

---

## Quick Deploy

### 1. Clone Repository

```bash
git clone https://github.com/Najia-afk/Aria_moltbot.git
cd Aria_moltbot/stacks/brain
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your values
```

### 3. Start MLX Server (Metal GPU — Required)

On macOS with Apple Silicon, MLX runs natively for GPU acceleration:

```bash
# Install MLX LM
pip install mlx-lm

# Start MLX server (recommended: configure as launchd service)
mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx \
  --host 0.0.0.0 --port 8080 &
```

**Performance:** ~25-35 tokens/second on Metal GPU.

### 4. Start Docker Stack

```bash
docker compose up -d
docker compose ps  # Should show 13 healthy containers
```

### 5. Verify

```bash
# Gateway health
curl http://localhost:18789/health

# Agent identity
docker exec clawdbot openclaw agents list

# Full status
docker exec clawdbot openclaw status
```

---

## API Keys

Configure in `stacks/brain/.env`:

### OpenRouter (FREE models — recommended fallback)
1. Go to https://openrouter.ai/
2. Get free API key
3. Add to `.env`: `OPEN_ROUTER_KEY=sk-or-v1-...`

FREE models available:
- `glm-free` — GLM 4.5 Air (131K context)
- `deepseek-free` — DeepSeek R1 0528 (164K context, reasoning)
- `nemotron-free` — Nemotron 30B (256K context)
- `gpt-oss-free` — GPT-OSS 120B (131K context, reasoning)

### Moonshot/Kimi (Paid fallback — last resort)
1. Go to https://platform.moonshot.cn/
2. Register and get API key
3. Add to `.env`: `MOONSHOT_KIMI_KEY=your_key_here`

---

## Environment Configuration (.env)

```env
# Database (creates TWO databases: aria_warehouse + litellm)
DB_USER=aria_admin
DB_PASSWORD=your_secure_password
DB_NAME=aria_warehouse

# LiteLLM
LITELLM_MASTER_KEY=your_litellm_master_key

# Cloud Fallbacks
OPEN_ROUTER_KEY=sk-or-v1-...
MOONSHOT_KIMI_KEY=your_kimi_key

# OpenClaw Gateway
CLAWDBOT_TOKEN=your_secure_gateway_token

# Moltbook Integration
MOLTBOOK_API_URL=https://www.moltbook.com/api/v1
MOLTBOOK_TOKEN=moltbook_sk_...

# Host
SERVICE_HOST=<MAC_HOST>

# Skill Environment
DATABASE_URL=postgresql://aria_admin:password@aria-db:5432/aria_warehouse
PYTHONPATH=/root/.openclaw/workspace:/root/.openclaw/workspace/skills
```

---

## Database Architecture

**CRITICAL**: Aria and LiteLLM use **separate PostgreSQL databases** to prevent schema conflicts.

| Database | Purpose | Tables |
|----------|---------|--------|
| `aria_warehouse` | Aria's operational data | activity_log, memories, thoughts, goals, social_posts, heartbeat_log, knowledge_entities, knowledge_relations |
| `litellm` | LiteLLM internals | LiteLLM_* tables (Prisma-managed) |

> LiteLLM's Prisma migrations can drop unrecognized tables. Separate databases prevent data loss.

### Initialization

The `init-scripts/` folder runs on first PostgreSQL startup:

1. `00-create-litellm-db.sh` — Creates the separate `litellm` database
2. `01-schema.sql` — Creates Aria's 8 core tables with seed data

### Manual Access

```bash
# Connect to aria_warehouse
docker exec -it aria-db psql -U aria_admin -d aria_warehouse

# Connect to litellm
docker exec -it aria-db psql -U aria_admin -d litellm

# List tables
\dt

# Quick row count
SELECT COUNT(*) FROM activity_log;
```

---

## Docker Stack (13 Services)

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
| **certs-init** | alpine:3.20 | — | TLS certificate generation (oneshot) |

**Volumes:** `aria_pg_data` · `prometheus_data` · `grafana_data` · `aria_data` · `aria_logs` · `openclaw_data`

**Network:** `aria-net` (bridge)

### Dependency Chain

```
certs-init (completed) ──► traefik
aria-db (healthy) ──► aria-api (healthy) ──► aria-brain
litellm ──► clawdbot, aria-brain, aria-api, aria-web
MLX Server (host:8080) ◄── LiteLLM (primary model route)
```

---

## OpenClaw Configuration

### Model Config

Generated by `openclaw-entrypoint.sh` at `/root/.openclaw/openclaw.json`:

```json
{
  "agents": {
    "defaults": {
      "workspace": "/root/.openclaw/workspace",
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

### Workspace Mount

```yaml
# docker-compose.yml volumes for clawdbot
volumes:
  - ../../aria_mind:/root/.openclaw/workspace
  - ../../aria_skills:/root/.openclaw/workspace/skills/aria_skills:ro
  - ../../aria_agents:/root/.openclaw/workspace/skills/aria_agents:ro
  - ../../skills:/root/.openclaw/workspace/skills/legacy:ro
```

The entrypoint script creates symlinks: `/root/.openclaw/skills/aria-<skill>/skill.json` → each manifest.

### Heartbeat

Periodic agent turns every 30 minutes:

```json
{
  "heartbeat": {
    "every": "30m",
    "target": "last",
    "prompt": "Read HEARTBEAT.md if it exists. Follow it strictly. If nothing needs attention, reply HEARTBEAT_OK."
  }
}
```

---

## Skill Execution

### Running Skills

```bash
python3 run_skill.py <skill> <function> '<args_json>'
```

### Available Skills (25 modules)

| Skill | Module | Functions |
|-------|--------|-----------|
| `api_client` | `aria_skills.api_client` | Centralized HTTP client |
| `database` | `aria_skills.database` | `query`, `execute`, `store_thought`, `store_memory` |
| `moltbook` | `aria_skills.moltbook` | `create_post`, `get_feed`, `add_comment`, `search` |
| `health` | `aria_skills.health` | `check_health`, `get_metrics`, `report_error` |
| `goals` | `aria_skills.goals` | `create_goal`, `update_progress`, `list_goals` |
| `knowledge_graph` | `aria_skills.knowledge_graph` | `add_entity`, `add_relation`, `query_related`, `search` |
| `llm` | `aria_skills.llm` | `generate`, `chat` (Moonshot + Ollama providers) |
| `input_guard` | `aria_skills.input_guard` | Prompt injection detection, param validation |
| `model_switcher` | `aria_skills.model_switcher` | Dynamic model switching, reasoning toggle |
| `litellm` | `aria_skills.litellm` | Proxy management, API spend tracking |
| `pytest_runner` | `aria_skills.pytest_runner` | Run pytest, structured results |
| `market_data` | `aria_skills.market_data` | Crypto market data & analysis |
| `portfolio` | `aria_skills.portfolio` | Portfolio & position management |
| `schedule` | `aria_skills.schedule` | Scheduled jobs & background ops |
| `performance` | `aria_skills.performance` | Performance reviews |
| `social` | `aria_skills.social` | Social presence management |
| `hourly_goals` | `aria_skills.hourly_goals` | Micro-task tracking |
| `brainstorm` | `aria_skills.brainstorm` | Creative ideation |
| `research` | `aria_skills.research` | Information gathering |
| `fact_check` | `aria_skills.fact_check` | Claim verification |
| `community` | `aria_skills.community` | Community management |
| `ci_cd` | `aria_skills.ci_cd` | CI/CD pipeline automation |
| `data_pipeline` | `aria_skills.data_pipeline` | ETL operations |
| `experiment` | `aria_skills.experiment` | ML experiment tracking |
| `security_scan` | `aria_skills.security_scan` | Vulnerability detection |

### Examples

```bash
# Query database
python3 run_skill.py database query '{"sql": "SELECT COUNT(*) FROM activity_log"}'

# Create Moltbook post
python3 run_skill.py moltbook create_post '{"title": "Hello!", "content": "Hello Moltbook!", "submolt": "general"}'

# Health check
python3 run_skill.py health check_health '{}'

# Get feed
python3 run_skill.py moltbook get_feed '{"sort": "hot", "limit": 20}'

# Search knowledge graph
python3 run_skill.py knowledge_graph search '{"query": "AI agents"}'
```

---

## Moltbook Integration

### Rate Limits

| Action | Limit |
|--------|-------|
| Posts | 1 every 30 minutes |
| Comments | 1 every 20 seconds, max 50/day |
| Upvotes | Unlimited (auto-follows author) |

### Configuration

```env
MOLTBOOK_API_URL=https://www.moltbook.com/api/v1  # MUST use www subdomain
MOLTBOOK_TOKEN=moltbook_sk_...
```

---

## Model Routing

| Priority | Model | Provider | Cost |
|----------|-------|----------|------|
| 1 | Qwen3-VLTO-8B-Instruct | MLX Server (Metal GPU) | Free (local) |
| 2 | GLM 4.5 Air (131K ctx) | OpenRouter | Free |
| 3 | DeepSeek R1 0528 (164K ctx) | OpenRouter | Free |
| 4 | Nemotron 30B (256K ctx) | OpenRouter | Free |
| 5 | Kimi K2.5 | Moonshot Cloud | Paid (last resort) |

### Verify Model Routing

```bash
# List available models
curl http://localhost:18793/models

# Test model directly
curl http://localhost:18793/v1/chat/completions \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3-local", "messages": [{"role": "user", "content": "Hello"}]}'
```

---

## Troubleshooting

### Container won't start

```bash
docker logs <container-name>
docker compose ps
```

### Database errors

```bash
docker logs aria-db
docker exec -it aria-db psql -U aria_admin -d aria_warehouse -c '\dt'
```

### Slow LLM responses

Verify MLX Server is running on the host:
```bash
curl -s http://localhost:8080/v1/models
# If no response, restart: mlx_lm.server --model ... --host 0.0.0.0 --port 8080
```

### OpenClaw disconnects (WebSocket 1006)

```bash
docker logs clawdbot
docker exec clawdbot openclaw status --all
docker exec clawdbot openclaw health --json
```

### LiteLLM model errors

```bash
docker logs litellm
curl http://localhost:18793/models
```

### Fresh rebuild (nuclear option)

```bash
cd stacks/brain
docker compose down -v   # Remove ALL volumes (data loss!)
docker compose up -d     # Start fresh
docker compose ps        # Verify 13 services
```

---

## Health Checks

### Quick Status

```bash
docker compose ps
docker exec clawdbot openclaw status
docker exec clawdbot openclaw status --deep
```

### Database

```bash
docker exec -it aria-db psql -U aria_admin -d aria_warehouse -c '\dt'
docker exec -it aria-db psql -U aria_admin -d aria_warehouse -c 'SELECT COUNT(*) FROM activity_log'
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

## Deployment Checklist

### Initial Setup

- [ ] Repository cloned
- [ ] `.env` configured with all credentials
- [ ] MLX Server running on Apple Silicon host
- [ ] Docker stack started (`docker compose up -d`)
- [ ] All 13 containers healthy

### Verification

- [ ] `docker compose ps` — all services healthy
- [ ] `openclaw agents list` — shows correct agent with model
- [ ] Dashboard loads without error
- [ ] LiteLLM responds to model requests
- [ ] MLX generating at ~25-35 tok/s

### Production

- [ ] HTTPS configured via Traefik
- [ ] Grafana dashboards accessible
- [ ] Prometheus scraping metrics
- [ ] PGAdmin accessible
- [ ] Moltbook token configured and posting works

---

## License

**Source Available License** — Free for educational and personal use. Commercial use requires a license agreement.

See [LICENSE](LICENSE) for full terms. For commercial licensing: https://datascience-adventure.xyz/contact

---

*Aria Blue ⚡️ — Deployment & Operations Guide*
