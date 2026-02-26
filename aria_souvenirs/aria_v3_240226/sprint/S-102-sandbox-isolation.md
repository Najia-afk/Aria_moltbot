# S-102: Sandbox Isolation (Network, Read-Only, Non-Root)
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 3 | **Phase:** 1

## Problem
The `aria-sandbox` service in `stacks/brain/docker-compose.yml` executes arbitrary user-submitted Python code as root with full network access to all internal services (PostgreSQL, LiteLLM, etc.).

## Root Cause
Sandbox container was created without network isolation or filesystem restrictions.

## Fix
Update docker-compose.yml sandbox service:
```yaml
aria-sandbox:
  # Add these:
  read_only: true
  tmpfs:
    - /tmp:size=100m
  security_opt:
    - no-new-privileges:true
  networks:
    - sandbox-net  # Isolated network, NOT aria-net
  cap_drop:
    - ALL
  # USER: aria (after S-101)
```

Add isolated network:
```yaml
networks:
  sandbox-net:
    driver: bridge
    internal: true  # No outbound internet
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No models |
| 4 | Docker-first testing | ✅ | Test in Docker |
| 5 | aria_memories writable | ✅ | Sandbox writes need tmpfs |
| 6 | No soul modification | ❌ | No soul |

## Dependencies
- S-101 (non-root USER) should be done first

## Verification
```bash
# 1. Verify sandbox cannot reach database
docker compose exec aria-sandbox curl -s http://aria-db:5432
# EXPECTED: connection refused or DNS failure

# 2. Verify read-only filesystem
docker compose exec aria-sandbox touch /test
# EXPECTED: Read-only file system error

# 3. Verify tmpfs works
docker compose exec aria-sandbox python -c "open('/tmp/test', 'w').write('ok')"
# EXPECTED: success
```

## Prompt for Agent
```
Read: stacks/brain/docker-compose.yml (sandbox section)
Steps: Add read_only, tmpfs, security_opt, cap_drop, isolated network.
Test: sandbox cannot reach aria-db, filesystem is read-only, /tmp works.
```
