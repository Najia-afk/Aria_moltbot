# S-118: Pin All Docker Image Versions
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
6 Docker images use `:latest` tags making builds non-reproducible.

## Fix
Pin to specific versions in docker-compose.yml:
- `browserless/chrome:latest` → `browserless/chrome:2.18.0`
- `dperson/torproxy:latest` → `dperson/torproxy:2.13.0`
- `prom/prometheus:latest` → `prom/prometheus:v2.51.0`
- `grafana/grafana:latest` → `grafana/grafana:11.4.0`
- `dpage/pgadmin4:latest` → `dpage/pgadmin4:8.14`
- `ghcr.io/berriai/litellm:main-latest` → pin to specific build hash

## Verification
```bash
grep -c ":latest" stacks/brain/docker-compose.yml
# EXPECTED: 0
```

---

# S-119: Fix Deploy Script DB Credentials
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
`scripts/deploy_production.sh` uses `pg_dump -U aria aria_blue` but actual defaults are `admin`/`aria_warehouse`.

## Fix
```bash
# BEFORE
pg_dump -U aria aria_blue > backup.sql
# AFTER
pg_dump -U ${DB_USER:-admin} ${DB_NAME:-aria_warehouse} > backup.sql
```

Also fix health check expected port (5000 → 5050) and container count.

## Verification
```bash
grep "aria_blue" scripts/deploy_production.sh
# EXPECTED: no matches

grep "DB_USER\|DB_NAME" scripts/deploy_production.sh
# EXPECTED: env var references
```

---

# S-120: Docker Network Segmentation
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
All 14 services share a single flat `aria-net` bridge network. Database, Tor proxy, browser, and public services all on same network.

## Fix
Create 4 networks:
```yaml
networks:
  frontend:   # traefik, aria-web
  backend:    # aria-api, aria-engine, aria-brain, litellm
  data:       # aria-db, pgadmin
  monitoring: # prometheus, grafana
```

Each service connects only to networks it needs. aria-api bridges frontend + backend + data.

## Verification
```bash
docker network ls | grep aria
# EXPECTED: aria-frontend, aria-backend, aria-data, aria-monitoring
```

---

# S-121: Multi-Stage Docker Builds + .dockerignore
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
- No multi-stage builds (git, curl in production images)
- No .dockerignore (unnecessary files in context)
- tests/ copied into production image
- `pip install -e .` (editable) in production

## Fix
1. Create `.dockerignore` with: .git, .venv, __pycache__, tests/, aria_souvenirs/, etc.
2. Refactor Dockerfile to multi-stage (builder + runtime)
3. Change `pip install -e .` → `pip install --no-cache-dir .`
4. Remove tests/ copy from production stage

## Verification
```bash
test -f .dockerignore && echo "OK" || echo "FAIL"
# EXPECTED: OK

docker images | grep aria | awk '{print $7}'
# EXPECTED: smaller image sizes
```
