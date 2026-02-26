# S-117: Add Health Checks to All Docker Services
**Epic:** E5 — Architecture Cleanup | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
10 of 14 Docker services have NO health checks in `stacks/brain/docker-compose.yml`. Only `aria-db`, `aria-engine`, and `aria-api` have them. Services using `condition: service_started` instead of `condition: service_healthy` means dependent services start before their dependencies are actually ready.

Missing health checks: aria-browser, tor-proxy, traefik, litellm, prometheus, grafana, aria-brain, pgadmin, aria-web, aria-sandbox.

## Root Cause
Health checks were added ad-hoc only to critical services, not systematically.

## Fix
Add health checks to all 10 missing services in `stacks/brain/docker-compose.yml`:

```yaml
aria-browser:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/"]
    interval: 30s
    timeout: 10s
    retries: 3

tor-proxy:
  healthcheck:
    test: ["CMD", "curl", "--socks5", "localhost:9050", "-s", "https://check.torproject.org/api/ip"]
    interval: 60s
    timeout: 15s
    retries: 3

traefik:
  healthcheck:
    test: ["CMD", "traefik", "healthcheck", "--ping"]
    interval: 15s
    timeout: 5s
    retries: 3
  # Also add: --ping=true to command

litellm:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:4000/health"]
    interval: 30s
    timeout: 10s
    retries: 3

aria-brain:
  healthcheck:
    test: ["CMD", "python", "-c", "import aria_mind; print('ok')"]
    interval: 30s
    timeout: 10s
    retries: 3

aria-web:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5000/"]
    interval: 30s
    timeout: 10s
    retries: 3

prometheus:
  healthcheck:
    test: ["CMD", "wget", "--spider", "-q", "http://localhost:9090/-/ready"]
    interval: 30s
    timeout: 5s
    retries: 3

grafana:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:3000/api/health"]
    interval: 30s
    timeout: 10s
    retries: 3

pgadmin:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:80/misc/ping"]
    interval: 30s
    timeout: 10s
    retries: 3
```

Then update all `condition: service_started` → `condition: service_healthy` for services that now have health checks.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure only |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ❌ | No models |
| 4 | Docker-first testing | ✅ | Must test full stack |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None

## Verification
```bash
# 1. Start stack
docker compose -f stacks/brain/docker-compose.yml up -d

# 2. Wait for health checks and verify all healthy
docker compose -f stacks/brain/docker-compose.yml ps
# EXPECTED: all services show "healthy" status

# 3. Count healthy services
docker compose -f stacks/brain/docker-compose.yml ps --format json | python -c "
import sys, json
data = json.loads(sys.stdin.read())
healthy = sum(1 for s in data if 'healthy' in str(s.get('Health', '')))
print(f'{healthy} services healthy')
"
# EXPECTED: 13 services healthy (14 minus certs-init oneshot)
```

## Prompt for Agent
```
Read: stacks/brain/docker-compose.yml (full file)

Steps:
1. Identify all services WITHOUT healthcheck blocks
2. Add appropriate health checks to each
3. Update condition: service_started → condition: service_healthy where applicable
4. Add --ping=true to traefik command for native ping endpoint
5. Test: docker compose up -d
6. Verify: all services report healthy in docker compose ps
```
