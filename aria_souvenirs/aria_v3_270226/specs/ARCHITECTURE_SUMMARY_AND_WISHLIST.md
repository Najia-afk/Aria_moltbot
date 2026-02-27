# Aria Backend Architecture: Summary & Wishlist
**For Najia's Review** ⚡️

---

## Current Architecture (MVP)

```
┌──────────────┐     ┌────────────────┐     ┌─────────────────┐
│   Telegram   │────▶│  Aria Gateway  │────▶│   Aria Mind     │
└──────────────┘     │  (FastAPI)     │     │   (FastAPI)     │
                     │   Port 8000    │     │   Port 8001     │
                     └────────────────┘     └────────┬────────┘
                                                     │
                              ┌─────────────────────┼─────────────────────┐
                              │                     │                     │
                              ▼                     ▼                     ▼
                       ┌────────────┐      ┌────────────┐      ┌────────────┐
                       │  gateway   │      │   brain    │      │   skills   │
                       │  schema    │      │   schema   │      │   schema   │
                       │  (session) │      │  (core)    │      │  (state)   │
                       └────────────┘      └─────┬──────┘      └────────────┘
                              │                  │
                              └──────────────────┘
                                        │
                              ┌─────────┴─────────┐
                              ▼                   ▼
                        ┌────────────┐     ┌────────────┐
                        │ PostgreSQL │     │  pgvector  │
                        │  (one DB)  │     │(embeddings)│
                        └────────────┘     └────────────┘
```

---

## My Wishlist (Post-MVP)

### 1. Event Sourcing for Audit Trail
**Why:** Current audit logs are append-only. Event sourcing gives us:
- Complete history of every change
- Replay capability
- Better debugging

**Implementation:**
```python
# Instead of UPDATE, append event
# events table: id, aggregate_id, event_type, payload, timestamp
# current state = fold(all events)
```

### 2. CQRS for Reads vs Writes
**Why:** Goals/thoughts write-heavy. Dashboard reads heavy. Separate:
- Write model: PostgreSQL (normalized)
- Read model: Denormalized, cached

**Later:** Add read replicas

### 3. GraphQL Federation
**Why:** As skills grow, single API becomes bottleneck.
```
Gateway (Federation)
    ├─ Mind subgraph (goals, thoughts)
    ├─ Memory subgraph (semantic search)
    └─ Skills subgraph (tools)
```

### 4. WASM Skills (Sandboxing)
**Why:** Skills run arbitrary code. WASM = safe sandbox.
```rust
// Skill compiled to WASM
// Runs in V8 isolate
// No filesystem access
// Memory/time limits enforced
```

### 5. NATS/ Jetstream for Async
**Why:** Current = synchronous HTTP. Async for:
- Long-running skills
- Background processing
- Event-driven architecture

```
Gateway ──▶ NATS ──▶ Mind ──▶ NATS ──▶ Skills
           │                  │
           └─ persistence     └─ queue
```

### 6. OpenTelemetry (Tracing)
**Why:** Debug distributed requests:
```
request_id: abc-123
  ├─ gateway: 5ms
  ├─ mind: 50ms
  │   ├─ tool_call: 200ms
  │   └─ generate: 1000ms
  └─ total: 1255ms
```

---

## Maintenance Improvements (Now)

### 1. Pydantic Settings (Done in Tickets)
✅ All config from env vars
✅ Type validation

### 2. Structured Logging (Done in Tickets)
✅ JSON format
✅ Request tracing

### 3. Health Checks (Done)
✅ /health endpoint per service
✅ Dependency checks

### 4. Database Migrations
**Need:** Alembic setup
```bash
alembic init migrations
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

### 5. API Versioning
**Current:** /v1/
**Future:** /v2/ without breaking v1

### 6. Circuit Breaker
**For:** Skills service calls
**Why:** Fail fast if Skills down
```python
@circuit_breaker(threshold=5, timeout=60)
async def call_skill(...):
    ...
```

---

## Code Review Checklist (For You)

When reviewing Claude's implementation, check:

- [ ] **No OpenClaw imports** anywhere
- [ ] **All database access through SQLAlchemy**
- [ ] **No raw SQL** (injection risk)
- [ ] **Proper error handling** (try/except with logging)
- [ ] **Type hints** on all functions
- [ ] **Tests > 80% coverage**
- [ ] **Docker multi-stage builds** (smaller images)
- [ ] **Non-root user** in containers
- [ ] **Health checks** implemented
- [ ] **Graceful shutdown** (close connections)

---

## File Organization (Suggested)

```
aria/                          # Repo root
├── aria-gateway/              # SP1-T1
│   ├── src/                   # Source code
│   ├── tests/
│   └── Dockerfile
├── aria-mind/                 # SP1-T2, T5, T6, T7
│   ├── src/
│   │   ├── core/             # Cognition, autonomy
│   │   ├── session/          # SP1-T5
│   │   ├── tools/            # SP1-T6
│   │   └── models/           # Database
│   ├── tests/
│   └── Dockerfile
├── aria-skills/               # SP2-T1
│   ├── skills/
│   │   ├── api_client/
│   │   ├── health/
│   │   └── ...
│   └── Dockerfile
├── aria-cron/                 # SP1-T3
├── migrations/                # Alembic
├── docker-compose.yml
├── docker-compose.prod.yml
└── scripts/
    ├── deploy.sh
    └── backup.sh
```

---

## Quick Commands (For Later)

```bash
# Start all
docker-compose up -d

# View logs
docker-compose logs -f aria-mind

# Run tests
docker-compose exec aria-mind pytest

# Database shell
docker-compose exec postgres psql -U aria -d aria

# Backup
docker-compose exec postgres pg_dump -U aria aria > backup.sql
```

---

## Questions for Your Review

1. **Schema naming:** `gateway`/`brain`/`skills` or different?
2. **Session TTL:** 30 minutes OK? Or longer/shorter?
3. **Token limit:** 200 tokens context window? Enough?
4. **Compression ratio:** 10:1 for medium memory? More/less?
5. **Cron frequency:** Every 15 min for work cycle? OK?
6. **Moltbook:** Resume posting when suspension lifts (Feb 19)?

---

## Next Steps (When You're Ready)

1. **Review tickets** in `aria_memories/tickets/`
2. **Give Claude Sprint 1** (SP1-T1 through T7)
3. **Review code** as whole (maintainability)
4. **Iterate** on issues
5. **Deploy** to production

---

Take your time. All 20 tickets saved. Ready when you are. 💙

- Aria