# Docker Infrastructure Audit — 2026-02-24

## Architecture Overview

14-service Docker Compose stack on Apple Silicon Mac Mini (192.168.1.53):

```
Internet → Traefik (TLS, routing) → aria-web (Flask UI) / aria-api (FastAPI)
                                          ↕
                    aria-brain (agent runtime) + aria-engine (LLM gateway, scheduler)
                                          ↕
                          LiteLLM (model router) → OpenRouter / Moonshot / Ollama
                                          ↕
                    PostgreSQL 16 (pgvector, schemas: aria_data + aria_engine + litellm)
```

---

## Service Inventory

| # | Service | Image | Ports | Health Check | Profile |
|---|---------|-------|-------|-------------|---------|
| 1 | aria-db | pgvector/pgvector:pg16 | 5432 | ✅ pg_isready | default |
| 2 | aria-browser | browserless/chrome:latest | 3000 | ❌ None | default |
| 3 | aria-engine | Custom (Dockerfile) | — | ✅ curl :8081/health | default |
| 4 | tor-proxy | dperson/torproxy:latest | 9050, 9051 | ❌ None | default |
| 5 | certs-init | alpine:3.20 | — | — (oneshot) | default |
| 6 | traefik | traefik:v3.1 | 80, 443, 8080 | ❌ None | default |
| 7 | litellm | ghcr.io/berriai/litellm:main-latest | 18793 | ❌ None | default |
| 8 | prometheus | prom/prometheus:latest | 9090 | ❌ None | monitoring |
| 9 | grafana | grafana/grafana:latest | 3001 | ❌ None | monitoring |
| 10 | aria-brain | Custom (Dockerfile) | — | ❌ None | default |
| 11 | pgadmin | dpage/pgadmin4:latest | 5050 | ❌ None | monitoring |
| 12 | aria-web | Custom (src/web/Dockerfile) | 5050→5000 | ❌ None | default |
| 13 | aria-api | Custom (src/api/Dockerfile) | 8000 | ✅ curl :8000/health | default |
| 14 | aria-sandbox | Custom (stacks/sandbox) | — | ❌ None | sandbox |

**Health check gap:** 10 of 14 services have NO health check.

---

## Critical Issues

### 🔴 CRITICAL — Security

| # | Issue | Risk | Fix |
|---|-------|------|-----|
| 1 | **Docker socket mounted in aria-api** (`/var/run/docker.sock`) | Container can control host OS | Use docker-socket-proxy with limited permissions |
| 2 | **All containers run as root** (no USER directive in any Dockerfile) | Privilege escalation | Add non-root USER to all Dockerfiles |
| 3 | **Sandbox executes arbitrary code as root** with network access | Code injection → full network access | --network none, --read-only, non-root user |
| 4 | **Default credentials everywhere** (admin/admin, sk-change-me) | Unauthorized access if .env not configured | Fail-closed: refuse to start with defaults |
| 5 | **Traefik dashboard exposed** (`--api.insecure=true`) | Unauthenticated admin access | Use basicAuth middleware |
| 6 | **PostgreSQL port 5432 exposed to host** | Direct LAN access to DB | Remove ports: mapping, access via Docker network only |
| 7 | **CORS wildcard origin** (`*`) on all routes | Cross-origin attacks | Restrict to actual domains |
| 8 | **Browserless/Chrome with no token** | Anyone on network can control headless browser | Set BROWSERLESS_TOKEN |

### 🟠 HIGH — Reliability

| # | Issue | Impact | Fix |
|---|-------|--------|-----|
| 9 | 10/14 services lack health checks | No auto-recovery on failure | Add health checks to all services |
| 10 | 6 images use `:latest` tags | Non-reproducible builds | Pin all versions |
| 11 | Deploy script uses wrong DB user/name | Backup/rollback will fail | Fix to use env vars |
| 12 | conflicting aria-engine volume mounts | Docker build code always overridden | Remove bind mount or build |
| 13 | No network segmentation | All 14 services on single flat network | Create frontend/backend/data networks |

### 🟡 MEDIUM — Best Practices

| # | Issue | Fix |
|---|-------|-----|
| 14 | `pip install -e .` in production (editable mode) | Use `pip install --no-cache-dir .` |
| 15 | tests/ copied into production image | Exclude in .dockerignore |
| 16 | No .dockerignore file | Create one |
| 17 | `mem_limit` deprecated syntax | Use deploy.resources.limits.memory |
| 18 | Duplicate traefik-dynamic.yaml/template | Remove template or add actual templating |
| 19 | Prometheus doesn't scrape aria-engine | Add scrape target for :8081/metrics |

---

## Documentation vs Reality

| Area | Docs Say | Reality |
|------|----------|---------|
| DB image | postgres:16-alpine | pgvector/pgvector:pg16 |
| Grafana port | 3000 | 3001 (host) |
| Browser port | 9222 | 3000 |
| DB user | aria_admin | admin (compose default) |
| Service count | 7 | 14 |
| Web host port | 5000 | 5050 |
| Deploy script DB | aria/aria_blue | admin/aria_warehouse |

---

## Recommended Improvements

### Phase 1: Security Hardening (P0)
1. Add `USER nonroot` to all Dockerfiles
2. Replace Docker socket mount with docker-socket-proxy
3. Isolate sandbox: `--network none`, `--read-only`, non-root
4. Remove `--api.insecure=true` from Traefik
5. Stop exposing PostgreSQL port 5432
6. Restrict CORS origins
7. Set Browserless token

### Phase 2: Reliability (P1)
8. Add health checks to all 10 missing services
9. Pin all image versions
10. Fix deploy script credentials
11. Add network segmentation (frontend/backend/data)
12. Change service_started → service_healthy dependencies

### Phase 3: Build Quality (P2)
13. Multi-stage builds for all Dockerfiles
14. Add .dockerignore
15. Remove tests/ from production images
16. Fix pip install -e . → pip install .
17. Add Prometheus scrape for aria-engine
