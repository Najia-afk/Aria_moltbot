# S-25: Skill Health Dashboard API & OpenTelemetry Foundation
**Epic:** E13 — Observability | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
### Problem A: Skill health data trapped in engine process memory
`aria_mind/skill_health_dashboard.py` L1-199 is a standalone in-memory singleton that records execution metrics via `BaseSkill.execute_with_metrics()` at `base.py` L336. The data is never exposed via API. The web UI has no way to display skill health metrics.

Three separate latency tracking mechanisms exist but aren't unified:
1. `@log_latency` decorator → posts to `/skill-latency` API
2. `execute_with_metrics` → updates in-memory dashboard + Prometheus
3. `telemetry.py` → writes to DB

### Problem B: No OpenTelemetry / distributed tracing
`aria_engine/telemetry.py` L1-113 writes to DB tables. `aria_engine/metrics.py` L1-374 has comprehensive Prometheus metrics. But no OpenTelemetry SDK (no `TracerProvider`, no `trace.get_tracer()`). Cross-service requests (web → API → engine → LiteLLM) cannot be correlated.

## Fix

### Fix 1: Add skill health API endpoint
**File:** `src/api/routers/` — add to existing skills router:
```python
@router.get("/skills/health")
async def skill_health():
    """Return aggregated skill health metrics."""
    dashboard = get_dashboard()
    return dashboard.to_dict()
```

Or if skill health dashboard runs in the engine process, expose via engine API:
```python
# aria_engine/ — add health endpoint to engine's internal HTTP server
@app.get("/engine/skills/health")
def skill_health():
    return get_dashboard().to_dict()
```

### Fix 2: Add skill health web page
**File:** `src/web/templates/skill_health.html` (NEW)
Display:
- Per-skill success rate (pie chart)
- Average latency by skill (bar chart)
- Circuit breaker states (from S-22)
- Last 10 invocations per skill (table)

### Fix 3: Consolidate latency tracking
Pick ONE mechanism as the primary:
- **Recommended:** `execute_with_metrics()` → Prometheus + in-memory dashboard
- Deprecate `@log_latency` decorator (remove API call, keep Prometheus push)
- Keep `telemetry.py` DB writes as secondary persistence

### Fix 4: Add OpenTelemetry foundation
**File:** `aria_engine/tracing.py` (NEW)
```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

def configure_tracing():
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return  # No-op if no collector configured
    
    provider = TracerProvider(resource=Resource.create({
        "service.name": "aria-engine",
        "service.version": os.environ.get("ARIA_VERSION", "3.0"),
    }))
    processor = BatchSpanProcessor(OTLPSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
```

### Fix 5: Add auto-instrumentation
```python
# In entrypoint.py:
from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

AsyncPGInstrumentor().instrument()  # DB traces
HTTPXClientInstrumentor().instrument()  # HTTP client traces
```

### Fix 6: Add dependencies
**File:** `pyproject.toml`
```toml
"opentelemetry-sdk>=1.20",
"opentelemetry-exporter-otlp>=1.20",
"opentelemetry-instrumentation-asyncpg>=0.40",
"opentelemetry-instrumentation-httpx>=0.40",
```

### Fix 7: Optional Jaeger container
**File:** `stacks/brain/docker-compose.yml` — add optional tracing service:
```yaml
  jaeger:
    image: jaegertracing/all-in-one:latest
    profiles: ["tracing"]
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # OTLP gRPC
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ✅ | Observability via API endpoints |
| 2 | .env for secrets | ✅ | OTEL_EXPORTER_OTLP_ENDPOINT from .env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-22 (circuit breakers) — for displaying circuit state in health dashboard
- S-24 (structured logging) — for correlation ID to appear in traces

## Verification
```bash
# 1. Skill health endpoint works:
curl -s http://localhost:8000/engine/skills/health | python -m json.tool
# EXPECTED: JSON with per-skill metrics

# 2. Skill health web page:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050/skills/health
# EXPECTED: 200

# 3. OTel configured (if collector running):
docker compose --profile tracing up -d jaeger
# Open http://localhost:16686, search for aria-engine service
# EXPECTED: Traces visible

# 4. No-op when no collector:
# Without OTEL_EXPORTER_OTLP_ENDPOINT, engine should start without errors
```

## Prompt for Agent
```
Read these files FIRST:
- aria_mind/skill_health_dashboard.py (full)
- aria_skills/base.py (L280-L410 — execute_with_metrics, safe_execute)
- aria_skills/latency.py (full)
- aria_engine/telemetry.py (full)
- aria_engine/metrics.py (full)
- aria_engine/entrypoint.py (L80-L130 — startup sequence)

CONSTRAINTS: OTel must be opt-in (no-op without env var). Skill health must go through API.

STEPS:
1. Add /engine/skills/health API endpoint
2. Create skill_health.html web page with charts
3. Deprecate @log_latency — consolidate into execute_with_metrics
4. Create aria_engine/tracing.py with OTel setup
5. Add auto-instrumentation for asyncpg and httpx
6. Wire configure_tracing() into entrypoint.py startup (after configure_logging)
7. Add jaeger as optional profile service in docker-compose
8. Add OTel dependencies to pyproject.toml
9. Add OTEL_EXPORTER_OTLP_ENDPOINT to .env.example
10. Test with and without OTel collector
```
