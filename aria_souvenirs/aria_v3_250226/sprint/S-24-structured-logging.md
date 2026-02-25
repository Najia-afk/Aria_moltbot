# S-24: Structured Logging & Docker Log Rotation
**Epic:** E13 — Observability | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
### Problem A: Engine uses plain-text logging, not structured JSON
`aria_mind/logging_config.py` L1-47 configures structlog with JSON rendering for production. However, `aria_engine/entrypoint.py` L199 uses `logging.basicConfig()` directly and **never calls `configure_logging()`**. The engine writes plain text logs:
```
2026-02-25 14:32:01 [aria_engine.scheduler] INFO Processing cron job...
```
Instead of structured JSON:
```json
{"timestamp": "2026-02-25T14:32:01Z", "level": "info", "logger": "aria_engine.scheduler", "message": "Processing cron job", "job_id": "memory-consolidation"}
```

### Problem B: No Docker log rotation
No `RotatingFileHandler`, `TimedRotatingFileHandler`, or `logrotate` configuration found. Docker's default `json-file` log driver has no size limits → logs grow unbounded on disk.

## Fix

### Fix 1: Call configure_logging() in entrypoint.py
**File:** `aria_engine/entrypoint.py` L199
```python
from aria_mind.logging_config import configure_logging

def main():
    configure_logging()  # Structured JSON in production, console in debug
    # ... rest of startup
```

### Fix 2: Add Docker log rotation
**File:** `stacks/brain/docker-compose.yml` — add to each service:
```yaml
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
```

Apply to: aria-engine, aria-api, aria-web, aria-brain, litellm, traefik. Optionally create a YAML anchor:
```yaml
x-logging: &default-logging
  logging:
    driver: json-file
    options:
      max-size: "50m"
      max-file: "5"

services:
  aria-engine:
    <<: *default-logging
    ...
```

### Fix 3: Add correlation IDs
**File:** `aria_engine/entrypoint.py` or middleware
Add a `correlation_id` (UUID) to each request context so all log lines from a single request can be traced:
```python
import contextvars
correlation_id = contextvars.ContextVar('correlation_id', default='')

# In middleware or at request start:
correlation_id.set(str(uuid4()))
```

Configure structlog to include `correlation_id` in every log line.

### Fix 4: Verify aria-api also uses structured logging
Check `src/api/main.py` startup — ensure it calls `configure_logging()` or has its own equivalent.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Infrastructure |
| 2 | .env for secrets | ❌ | |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- Should be done BEFORE S-20 (exception logging) so new logs are structured.

## Verification
```bash
# 1. Engine logs are JSON:
docker compose logs aria-engine --tail 5 | python -c "import sys,json; [json.loads(l.split('|',1)[-1].strip()) for l in sys.stdin]"
# EXPECTED: No parse errors (valid JSON)

# 2. Log rotation configured:
grep -A3 'max-size' stacks/brain/docker-compose.yml
# EXPECTED: max-size: "50m", max-file: "5"

# 3. configure_logging called:
grep 'configure_logging' aria_engine/entrypoint.py
# EXPECTED: Call found before main logic

# 4. Correlation ID present:
docker compose logs aria-engine --tail 10 | grep 'correlation_id'
# EXPECTED: UUID in every log line
```

## Prompt for Agent
```
Read these files FIRST:
- aria_mind/logging_config.py (full)
- aria_engine/entrypoint.py (L190-L215 — logging setup)
- src/api/main.py (find logging configuration)
- stacks/brain/docker-compose.yml (first 100 lines — check logging config)

STEPS:
1. Add configure_logging() call to entrypoint.py before any other logic
2. Add YAML anchor x-logging with json-file driver, 50m max-size, 5 max-file
3. Apply x-logging anchor to ALL services in docker-compose.yml
4. Add correlation_id contextvars to engine request handling
5. Wire correlation_id into structlog processor chain
6. Verify aria-api uses structured logging too
7. Run verification commands
```
