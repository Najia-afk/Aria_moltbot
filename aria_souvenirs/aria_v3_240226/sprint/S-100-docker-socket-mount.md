# S-100: Remove Docker Socket Mount from aria-api
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
`stacks/brain/docker-compose.yml` mounts the Docker socket into the `aria-api` container:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```
This gives the FastAPI application **full root-level control over the Docker host**, including the ability to create privileged containers, read host filesystems, and execute commands on the host OS.

The socket mount exists to support the `ARIA_SERVICE_CMD_*` environment variables that allow Aria to restart/stop Docker services via API endpoints (likely in `src/api/routers/admin.py` or similar).

## Root Cause
The service control feature was implemented by directly mounting the Docker socket instead of using a safer alternative. This is the most critical security vulnerability in the stack — any RCE in the FastAPI app escalates to full host control.

## Fix
**Option A (Recommended): Use docker-socket-proxy**

Add a new service to docker-compose.yml:
```yaml
# BEFORE: aria-api has direct socket access
aria-api:
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock

# AFTER: Use socket proxy with limited permissions
docker-socket-proxy:
  image: tecnativa/docker-socket-proxy:0.1.2
  restart: unless-stopped
  environment:
    CONTAINERS: 1      # Allow container listing and control
    POST: 1            # Allow POST (restart/stop)
    SERVICES: 0
    TASKS: 0
    NETWORKS: 0
    VOLUMES: 0
    IMAGES: 0
    EXEC: 0            # Block exec into containers
    SWARM: 0
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
  networks:
    - aria-net
  mem_limit: 64m

aria-api:
  # Remove: /var/run/docker.sock volume mount
  environment:
    DOCKER_HOST: tcp://docker-socket-proxy:2375
```

Then update any Python code that uses `docker.from_env()` or `docker.DockerClient()` to connect via TCP:
```python
# BEFORE
client = docker.from_env()

# AFTER
import os
client = docker.DockerClient(base_url=os.environ.get("DOCKER_HOST", "unix:///var/run/docker.sock"))
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure change only |
| 2 | .env for secrets | ✅ | DOCKER_HOST is a config, not secret — OK in compose |
| 3 | models.yaml single source | ❌ | No model changes |
| 4 | Docker-first testing | ✅ | Must test in Docker Compose |
| 5 | aria_memories writable path | ❌ | No memory changes |
| 6 | No soul modification | ❌ | No soul changes |

## Dependencies
- None — standalone fix

## Verification
```bash
# 1. Verify socket is NOT mounted in aria-api
docker compose -f stacks/brain/docker-compose.yml config | grep -A5 "aria-api" | grep "docker.sock"
# EXPECTED: no output (socket removed)

# 2. Verify docker-socket-proxy is running
docker compose -f stacks/brain/docker-compose.yml ps docker-socket-proxy
# EXPECTED: running

# 3. Test service control still works (if applicable)
curl -s http://localhost:8000/admin/services | jq .
# EXPECTED: service list response (via proxy)

# 4. Verify proxy blocks dangerous operations
docker compose exec aria-api curl -s http://docker-socket-proxy:2375/exec
# EXPECTED: 403 Forbidden
```

## Prompt for Agent
```
Read these files first:
- stacks/brain/docker-compose.yml (full file)
- Search for "docker.sock" or "docker" in src/api/ directory
- Read any file that imports docker or uses docker.DockerClient

Steps:
1. Add docker-socket-proxy service to stacks/brain/docker-compose.yml
2. Remove /var/run/docker.sock volume from aria-api
3. Add DOCKER_HOST: tcp://docker-socket-proxy:2375 to aria-api environment
4. Update any Python code using docker.from_env() to use DOCKER_HOST env var
5. Test: docker compose up -d, verify proxy running, verify aria-api can still list/restart services
6. Test: verify aria-api CANNOT exec into containers or access host filesystem

Constraints: Docker-first testing required. .env for sensitive config.
```
