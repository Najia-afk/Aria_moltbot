# S-107: Secure Traefik Dashboard
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
Traefik runs with `--api.insecure=true`, exposing the dashboard on port 8080 without authentication.

## Fix
1. Remove `--api.insecure=true` from traefik command
2. Add `--api.dashboard=true` + basicAuth middleware in `traefik-dynamic.yaml`
3. Add Traefik dashboard credentials to `.env.example`

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1-6 | Only #2 (.env) and #4 (Docker) apply | ✅ | Credentials in .env |

## Verification
```bash
# Dashboard requires auth
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/dashboard/
# EXPECTED: 401
```

---

# S-108: Remove PostgreSQL Port Exposure
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 1 | **Phase:** 1

## Problem
`aria-db` exposes port 5432 to the host, making PostgreSQL accessible from the LAN.

## Fix
Remove `ports: - "5432:5432"` from aria-db in docker-compose.yml. Services access DB via Docker network `aria-net`.

## Verification
```bash
# Port should not be listening on host
netstat -an | grep 5432
# EXPECTED: no matches (or only Docker internal)
```

---

# S-109: Restrict CORS Origins + Set Browserless Token
**Epic:** E4 — Security Hardening | **Priority:** P0 | **Points:** 2 | **Phase:** 1

## Problem
CORS is set to `*` in traefik-dynamic.yaml. Browserless Chrome has no token.

## Fix
1. Change `accessControlAllowOriginList: "*"` to actual domains
2. Set `BROWSERLESS_TOKEN` in .env.example and compose
3. Update aria_skills/sandbox/ to pass Browserless token

## Verification
```bash
# CORS header should NOT be *
curl -s -I http://localhost:8000/ | grep "Access-Control"
# EXPECTED: specific origin, not *
```
