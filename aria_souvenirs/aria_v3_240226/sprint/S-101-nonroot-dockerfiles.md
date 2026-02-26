# S-101: Add Non-Root USER to All Dockerfiles
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 5 | **Phase:** 1

## Problem
All 4 Dockerfiles in the project run as root (PID 1):
- `Dockerfile` (aria-engine, aria-brain) — no USER directive
- `src/api/Dockerfile` (aria-api) — no USER directive  
- `src/web/Dockerfile` (aria-web) — no USER directive
- `stacks/sandbox/Dockerfile` (aria-sandbox) — no USER directive

Any vulnerability exploitation gives the attacker root privileges inside the container.

## Root Cause
User creation was never added during initial Dockerfile development. All COPY and RUN commands assume root.

## Fix
For each Dockerfile, add a non-root user after the pip install step:

```dockerfile
# Add to each Dockerfile AFTER pip install, BEFORE COPY application code:
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria

# After all COPY commands:
USER aria
```

**Specific changes per Dockerfile:**

### Dockerfile (aria-engine/brain)
```dockerfile
# AFTER: pip install -e .
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria
# BEFORE: CMD
RUN chown -R aria:aria /app
USER aria
```

### src/api/Dockerfile
```dockerfile
# AFTER: pip install
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria
RUN chown -R aria:aria /app
USER aria
```

### src/web/Dockerfile
```dockerfile
# AFTER: pip install
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria
RUN chown -R aria:aria /app
USER aria
```

### stacks/sandbox/Dockerfile
```dockerfile
# AFTER: pip install
RUN addgroup --system --gid 1001 aria && \
    adduser --system --uid 1001 --ingroup aria aria
RUN chown -R aria:aria /app
USER aria
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure only |
| 2 | .env for secrets | ❌ | No secrets changed |
| 3 | models.yaml single source | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Must rebuild and test all containers |
| 5 | aria_memories writable path | ✅ | Must ensure aria user can write to mounted volumes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None — standalone fix
- Note: S-100 (docker socket) can be done in parallel

## Verification
```bash
# 1. Rebuild all images
docker compose -f stacks/brain/docker-compose.yml build

# 2. Verify non-root in each container
docker compose exec aria-api whoami
# EXPECTED: aria

docker compose exec aria-engine whoami
# EXPECTED: aria

docker compose exec aria-web whoami
# EXPECTED: aria

# 3. Verify services still start and respond
curl -s http://localhost:8000/health | jq .status
# EXPECTED: "healthy"

# 4. Verify aria_memories write access
docker compose exec aria-engine python -c "open('/app/aria_memories/test_write', 'w').write('ok')"
# EXPECTED: no permission error
```

## Prompt for Agent
```
Read these files first:
- Dockerfile (lines 1-end)
- src/api/Dockerfile (lines 1-end)
- src/web/Dockerfile (lines 1-end)
- stacks/sandbox/Dockerfile (lines 1-end)

Steps:
1. In each Dockerfile, add non-root user creation AFTER pip install step
2. Add chown -R aria:aria /app BEFORE USER directive
3. Add USER aria as second-to-last directive (before CMD/ENTRYPOINT)
4. Check if any volume mounts need permission fixes in docker-compose.yml
5. Rebuild: docker compose -f stacks/brain/docker-compose.yml build
6. Test: verify each container runs as non-root (whoami)
7. Test: verify all services respond to health checks
8. Test: verify aria_memories is writable

Constraints: Docker-first testing. aria_memories must remain writable.
```
