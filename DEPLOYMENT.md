# Aria Blue — Deployment & Operations Guide

> **Version**: 3.0.0 (aria_engine v3, multi-agent + artifact API)
> **Target**: Mac Mini — najia@192.168.1.53
> **Last updated**: Sprint 13

For architecture overview see [ARCHITECTURE.md](ARCHITECTURE.md). For model details see [MODELS.md](MODELS.md). For skill details see [SKILLS.md](SKILLS.md). For rollback procedures see [ROLLBACK.md](ROLLBACK.md).

---

## Prerequisites

- SSH access: `ssh -i ~/.ssh/najia_mac_key najia@192.168.1.53`
- **macOS with Apple Silicon** (M1/M2/M3/M4) for Metal GPU acceleration
- Docker & Docker Compose installed on Mac Mini
- At least 5GB free disk space
- All Sprint 13 tests passing

---

## Quick Deploy

```bash
# 1. Run all tests first
pytest tests/ -v --timeout=60

# 2. Deploy (with automatic backup and rollback)
./scripts/deploy_production.sh

# 3. Verify
./scripts/health_check.sh
```

## Detailed Steps

### 1. Pre-Deploy Checklist
- [ ] All unit tests pass: `pytest tests/unit/ -v`
- [ ] All integration tests pass: `pytest tests/integration/ -v`
- [ ] No legacy gateway references: `pytest tests/unit/test_no_openclaw.py -v`
- [ ] Load test acceptable: `bash tests/load/run_load_test.sh`
- [ ] Memory profile clean: `python tests/profiling/memory_profile.py --quick`
- [ ] Version bumped in pyproject.toml

### 2. Deploy
```bash
./scripts/deploy_production.sh
```

### 3. Post-Deploy Verification
```bash
# Health check
./scripts/health_check.sh

# Check metrics
curl http://192.168.1.53:8081/metrics | grep aria_build_info

# Check Grafana dashboard
open http://192.168.1.53:3000

# Tail logs
ssh -i ~/.ssh/najia_mac_key najia@192.168.1.53 \
  "cd /home/najia/aria && docker compose logs -f aria-brain --tail=50"
```

### 4. If Something Goes Wrong
See [ROLLBACK.md](ROLLBACK.md) for detailed rollback procedures.

```bash
# Quick rollback
./scripts/deploy_production.sh --rollback
```

### 5. First-Time Setup

```bash
git clone https://github.com/Najia-afk/Aria_moltbot.git
cd Aria_moltbot
cp stacks/brain/.env.example .env
nano .env  # Edit with your values
```

### 6. Start MLX Server (Metal GPU)

On macOS with Apple Silicon, MLX runs natively for GPU acceleration:

```bash
pip install mlx-lm
mlx_lm.server --model nightmedia/Qwen3-VLTO-8B-Instruct-qx86x-hi-mlx \
  --host 0.0.0.0 --port 8080 &
```

**Performance:** ~25-35 tokens/second on Metal GPU.

### 7. Start Docker Stack

```bash
docker compose up -d
docker compose ps  # All services should be healthy
```

### 8. Verify

```bash
# API health
curl http://localhost:8000/api/health

# aria_engine health
curl http://localhost:8081/health

# Prometheus metrics
curl http://localhost:8081/metrics | grep aria_
```

---

## API Keys

Configure in `.env`:

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
# Defaults match docker-compose.yml: admin / admin / aria_warehouse
DB_USER=admin
DB_PASSWORD=your_secure_password
DB_NAME=aria_warehouse

# LiteLLM
LITELLM_MASTER_KEY=your_litellm_master_key

# Cloud Fallbacks
OPEN_ROUTER_KEY=sk-or-v1-...
MOONSHOT_KIMI_KEY=your_kimi_key

# Aria Engine Gateway
ARIA_ENGINE_TOKEN=your_secure_gateway_token

# Moltbook Integration
MOLTBOOK_API_URL=https://www.moltbook.com/api/v1
MOLTBOOK_TOKEN=moltbook_sk_...

# Host
SERVICE_HOST=<MAC_HOST>

# Skill Environment
DATABASE_URL=postgresql://aria_admin:password@aria-db:5432/aria_warehouse
PYTHONPATH=/app:/app/skills
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
2. `01-schema.sql` — Creates Aria's dual-schema tables (aria_data + aria_engine) with seed data

### Manual Access

```bash
# Connect to aria_warehouse (default DB_USER is 'admin')
docker exec -it aria-db psql -U ${DB_USER:-admin} -d aria_warehouse

# Connect to litellm
docker exec -it aria-db psql -U ${DB_USER:-admin} -d litellm

# List tables
\dt

# Quick row count
SELECT COUNT(*) FROM activity_log;
```

---

## Docker Stack

| Service | Image | Port (host) | Profile | Description |
|---------|-------|-------------|---------|-------------|
| **aria-db** | pgvector/pgvector:pg16 | — (internal) | default | PostgreSQL 16 + pgvector (dual database) |
| **aria-browser** | browserless/chrome:2.18.0 | 3000 | default | Headless browser automation |
| **aria-engine** | Custom (Python) | — (internal) | default | Aria Engine AI gateway (health on :8081) |
| **tor-proxy** | dperson/torproxy:latest | 9050, 9051 | default | Privacy proxy |
| **certs-init** | alpine:3.20 | — | default | TLS certificate generation (oneshot) |
| **traefik** | traefik:v3.1 | 8080, 8443, 8081 | default | HTTPS reverse proxy + dashboard |
| **litellm** | ghcr.io/berriai/litellm:main-v1.61.4 | 18793 | default | LLM model router |
| **aria-brain** | Custom (Python) | — | default | Agent runtime |
| **aria-web** | Custom (Flask) | 5050 | default | Dashboard UI |
| **aria-api** | Custom (FastAPI) | 8000 | default | REST API backend |
| **docker-socket-proxy** | tecnativa/docker-socket-proxy:0.2 | — (internal) | default | Restricted Docker API proxy |
| **prometheus** | prom/prometheus:v2.51.0 | 9090 | monitoring | Metrics collection |
| **grafana** | grafana/grafana:11.4.0 | 3001 | monitoring | Monitoring dashboards |
| **pgadmin** | dpage/pgadmin4:8.14 | 5050 | monitoring | Database admin UI |
| **aria-sandbox** | Custom (Python) | — (internal) | sandbox | Isolated code execution (S-29) |

> **15 services total**: 11 default + 3 monitoring profile + 1 sandbox profile.
> Traefik ports use env vars: `TRAEFIK_HTTP_PORT` (default 8080), `TRAEFIK_HTTPS_PORT` (default 8443), `TRAEFIK_DASH_PORT` (default 8081).
> aria-web port uses `ARIA_WEB_PORT` (default 5050; macOS reserves 5000).

**Volumes:** `aria_pg_data` · `prometheus_data` · `grafana_data` · `aria_data` · `aria_logs` · `aria_engine_data`

**Network:** `aria-net` (bridge)

### Dependency Chain

```
certs-init (completed) ──► traefik
aria-db (healthy) ──► aria-api (healthy) ──► aria-brain
litellm ──► aria-engine, aria-brain, aria-api, aria-web
MLX Server (host:8080) ◄── LiteLLM (primary model route)
```

---

## Aria Engine Configuration

### Model Config

Generated by the Aria Engine at startup:

```json
{
  "agents": {
    "defaults": {
      "workspace": "/app",
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
        "apiKey": "${ARIA_ENGINE_TOKEN}"
      }
    }
  }
}
```

### Workspace Mount

```yaml
# docker-compose.yml volumes for aria-engine
volumes:
  - ../../aria_mind:/app
  - ../../aria_skills:/app/skills/aria_skills:ro
  - ../../aria_agents:/app/skills/aria_agents:ro
  - ../../skills:/app/skills/legacy:ro
```

The entrypoint script creates symlinks: `/app/skills/aria-<skill>/skill.json` → each manifest.

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
python3 aria_mind/skills/run_skill.py <skill> <function> '<args_json>'
```

Recommended discovery-first flow (lower token overhead):

```bash
python3 aria_mind/skills/run_skill.py --auto-task "summarize current priorities" --route-limit 2 --route-no-info
python3 aria_mind/skills/run_skill.py --skill-info api_client
```

### Available Skills

See [SKILLS.md](SKILLS.md) for the skill system overview. Browse `aria_skills/*/skill.json` for the live catalog, or run:

```bash
python -m aria_mind --list-skills
```

### Examples

```bash
# Query database
python3 aria_mind/skills/run_skill.py api_client get_activities '{"limit": 1}'

# Create Moltbook post
python3 aria_mind/skills/run_skill.py social social_post '{"content": "Hello Moltbook!", "platform": "moltbook"}'

# Health check
python3 aria_mind/skills/run_skill.py health health_check '{}'

# Get feed
python3 aria_mind/skills/run_skill.py moltbook get_feed '{"limit": 20}'

# Search knowledge graph
python3 aria_mind/skills/run_skill.py api_client graph_search '{"query": "AI agents", "entity_type": "skill"}'
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

See [MODELS.md](MODELS.md) for the full model routing strategy. The single source of truth is [`aria_models/models.yaml`](aria_models/models.yaml).

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
docker exec -it aria-db psql -U ${DB_USER:-admin} -d aria_warehouse -c '\dt'
```

### Slow LLM responses

Verify MLX Server is running on the host:
```bash
curl -s http://localhost:8080/v1/models
# If no response, restart: mlx_lm.server --model ... --host 0.0.0.0 --port 8080
```

### Engine disconnects (WebSocket 1006)

```bash
docker logs aria-engine
docker exec aria-engine aria-engine status --all
docker exec aria-engine aria-engine health --json
```

### LiteLLM model errors

```bash
docker logs litellm
curl http://localhost:18793/models
```

### Fresh rebuild (nuclear option)

```bash
docker compose down -v   # Remove ALL volumes (data loss!)
docker compose up -d     # Start fresh
docker compose ps        # Verify all services healthy
```

---

## Health Checks

### Quick Status

```bash
docker compose ps
docker exec aria-engine aria-engine status
docker exec aria-engine aria-engine status --deep
```

### Database

```bash
docker exec -it aria-db psql -U ${DB_USER:-admin} -d aria_warehouse -c '\dt'
docker exec -it aria-db psql -U ${DB_USER:-admin} -d aria_warehouse -c 'SELECT COUNT(*) FROM activity_log'
```

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | `https://{HOST}/` | Main web UI |
| API Docs | `https://{HOST}/api/docs` | Swagger documentation |
| Aria Engine | `http://{HOST}:8100` | Engine API |
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
- [ ] All 15 services defined (11 default + monitoring/sandbox profiles)

### Verification

- [ ] `docker compose ps` — all services healthy
- [ ] `aria-engine agents list` — shows correct agent with model
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

## Architecture After Migration

```
Mac Mini (192.168.1.53)
├── docker compose stack (15 services):
│   ├── aria-db (PostgreSQL 16 + pgvector — pgvector/pgvector:pg16)
│   ├── litellm (LLM model router)
│   ├── aria-brain (aria_engine — heartbeat, cron, agents)
│   ├── aria-api (FastAPI REST API)
│   ├── aria-web (Dashboard)
│   ├── aria-engine (Python async engine)
│   ├── traefik (HTTPS reverse proxy)
│   ├── docker-socket-proxy (restricted Docker API)
│   ├── tor-proxy, aria-browser, certs-init
│   └── [monitoring profile] prometheus, grafana, pgadmin
│   └── [sandbox profile] aria-sandbox
├── /home/najia/aria/
│   ├── aria_engine/
│   ├── aria_mind/
│   ├── aria_skills/
│   ├── aria_agents/
│   ├── aria_memories/ (persistent data)
│   └── backups/ (deploy backups)
└── Ports:
    ├── 5050 — Flask dashboard (ARIA_WEB_PORT)
    ├── 8080 — Traefik HTTP (TRAEFIK_HTTP_PORT)
    ├── 8443 — Traefik HTTPS (TRAEFIK_HTTPS_PORT)
    ├── 8081 — Traefik dashboard (TRAEFIK_DASH_PORT)
    ├── 8000 — aria-api (FastAPI)
    ├── 18793 — LiteLLM
    ├── 3000 — aria-browser
    └── 9050 — tor-proxy
```

---

## License

**Source Available License** — Free for educational and personal use. Commercial use requires a license agreement.

See [LICENSE](LICENSE) for full terms. For commercial licensing: https://datascience-adventure.xyz/contact

---

*Aria Blue — Deployment & Operations Guide*
