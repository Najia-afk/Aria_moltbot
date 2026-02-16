# Aria Brain API — Complete Endpoint Reference
## FastAPI v3.0 | Snapshot: 2026-02-16

**Base path:** `/api`  
**Total REST endpoints:** ~105  
**GraphQL:** `/api/graphql` (Strawberry)  
**Stack:** FastAPI + SQLAlchemy 2.0 async + psycopg3 + pgvector

---

## Middleware Stack

| Layer | Description |
|-------|-------------|
| CORS | Origins: localhost:5000, aria-web:5000 |
| SecurityMiddleware | Rate limit 120/min 2000/hr, injection scanning, 2MB body max |
| Prometheus | Auto-instrumented at `/api/metrics` |
| Request Timing | `X-Response-Time-Ms` header, logs >100ms |
| Correlation ID | `X-Correlation-ID` propagation |

---

## REST Endpoints

### Health
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Status + uptime + DB state |
| GET | `/health/db` | Missing tables, pgvector, extensions |
| GET | `/host-stats` | RAM/swap/disk from host agent |
| GET | `/status` | All registered services + postgres |
| GET | `/stats` | Counts: activities, thoughts, memories |

### Activities
| Method | Path | Description |
|--------|------|-------------|
| GET | `/activities` | Paginated log (page, limit, action) |
| POST | `/activities` | Log activity (auto-mirrors to social) |
| GET | `/activities/cron-summary` | Cron execution summary (days) |
| GET | `/activities/timeline` | Daily counts for charts |
| GET | `/activities/visualization` | Rich dashboard payload |

### Thoughts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/thoughts` | Paginated reasoning logs |
| POST | `/thoughts` | Create thought (content, category) |

### Memories (KEY endpoints for memory systems)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/memories` | Paginated key-value memories |
| POST | `/memories` | Upsert by key (noise-filtered) |
| **POST** | **`/memories/semantic`** | **Store with pgvector embedding** |
| **GET** | **`/memories/search`** | **Semantic similarity search (cosine)** |
| **POST** | **`/memories/summarize-session`** | **LLM-summarize → episodic memory** |
| GET | `/memories/{key}` | Fetch by key |
| DELETE | `/memories/{key}` | Delete by key |

### Goals
| Method | Path | Description |
|--------|------|-------------|
| GET | `/goals` | List (page, limit, status) |
| POST | `/goals` | Create (noise-filtered) |
| DELETE | `/goals/{goal_id}` | Delete |
| PATCH | `/goals/{goal_id}` | Partial update |
| GET | `/goals/board` | Kanban board view |
| GET | `/goals/archive` | Completed/cancelled |
| PATCH | `/goals/{goal_id}/move` | Board drag-drop |
| GET | `/goals/sprint-summary` | ~200 token summary |
| GET | `/goals/history` | Status distribution by day |

### Hourly Goals
| Method | Path | Description |
|--------|------|-------------|
| GET | `/hourly-goals` | List (status filter) |
| POST | `/hourly-goals` | Create |
| PATCH | `/hourly-goals/{id}` | Update status |

### Sessions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | Paginated (auto-syncs OpenClaw) |
| POST | `/sessions` | Create |
| PATCH | `/sessions/{id}` | Update |
| DELETE | `/sessions/{id}` | Delete |
| GET | `/sessions/live` | Live OpenClaw sessions |
| POST | `/sessions/sync-live` | Force-ingest to DB |
| GET | `/sessions/hourly` | Hourly counts by agent |
| GET | `/sessions/stats` | Full stats + LiteLLM costs |

### Model Usage
| Method | Path | Description |
|--------|------|-------------|
| GET | `/model-usage` | Merged skill + LiteLLM logs |
| POST | `/model-usage` | Log usage entry |
| GET | `/model-usage/stats` | Aggregate stats (hours) |

### LiteLLM
| Method | Path | Description |
|--------|------|-------------|
| GET | `/litellm/models` | Available models |
| GET | `/litellm/health` | Liveliness |
| GET | `/litellm/spend` | Spend logs (direct PG) |
| GET | `/litellm/global-spend` | Aggregate spend/tokens |

### Providers
| Method | Path | Description |
|--------|------|-------------|
| GET | `/providers/balances` | Moonshot, OpenRouter, local |

### Security
| Method | Path | Description |
|--------|------|-------------|
| GET | `/security-events` | Paginated (threat_level, blocked_only) |
| POST | `/security-events` | Log event |
| GET | `/security-events/stats` | By-level, by-type, blocked count |

### Knowledge Graph
| Method | Path | Description |
|--------|------|-------------|
| GET | `/skill-graph` | Skill entities + relations |
| POST | `/knowledge-graph/sync-skills` | Trigger skill graph sync |
| GET | `/knowledge-graph` | Full organic KG |
| GET/POST | `/knowledge-graph/entities` | List/create entities |
| GET/POST | `/knowledge-graph/relations` | List/create relations |
| DELETE | `/knowledge-graph/auto-generated` | Clear skill graph |
| GET | `/knowledge-graph/traverse` | BFS traversal (start, depth) |
| GET | `/knowledge-graph/search` | ILIKE text search |
| GET | `/knowledge-graph/skill-for-task` | Find best skill for task |
| GET | `/knowledge-graph/query-log` | Query analytics |

### Social
| Method | Path | Description |
|--------|------|-------------|
| GET | `/social` | Paginated posts (platform filter) |
| POST | `/social` | Create post (test-filtered) |
| POST | `/social/cleanup` | Remove test/noise |
| POST | `/social/dedupe` | Remove duplicates |
| POST | `/social/import-moltbook` | Backfill Moltbook |

### Working Memory
| Method | Path | Description |
|--------|------|-------------|
| GET | `/working-memory` | List (category, key filters) |
| **GET** | **`/working-memory/context`** | **Weighted-relevance for LLM injection** |
| POST | `/working-memory` | Upsert by (category, key) |
| PATCH | `/working-memory/{id}` | Partial update |
| DELETE | `/working-memory/{id}` | Delete |
| POST | `/working-memory/checkpoint` | Snapshot all items |
| GET | `/working-memory/checkpoint` | Latest checkpoint |
| GET | `/working-memory/stats` | Aggregate stats |
| POST | `/working-memory/cleanup` | Smart cleanup (dry_run) |

### Skills
| Method | Path | Description |
|--------|------|-------------|
| GET | `/skills` | List all (auto-seeds 35 known) |
| GET | `/skills/{name}/health` | Single skill health |
| POST | `/skills/seed` | Seed skill_status (idempotent) |
| GET | `/skills/coherence` | Filesystem integrity scan |
| POST | `/skills/invocations` | Record invocation |
| GET | `/skills/stats` | Per-skill performance |
| GET | `/skills/stats/summary` | Compact aggregate |
| GET | `/skills/insights` | Rich dashboard payload |
| GET | `/skills/health/dashboard` | Health scores + patterns |

### Lessons
| Method | Path | Description |
|--------|------|-------------|
| POST | `/lessons` | Record/increment lesson |
| GET | `/lessons/check` | Lookup known resolutions |
| GET | `/lessons` | All lessons |
| POST | `/lessons/seed` | Seed 5 known patterns |

### Proposals
| Method | Path | Description |
|--------|------|-------------|
| POST | `/proposals` | Submit improvement (blocks soul/) |
| GET | `/proposals` | List (status filter) |
| PATCH | `/proposals/{id}` | Approve/reject |

### Admin
| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/services/{id}/{action}` | Docker service control (auth) |
| GET | `/soul/{filename}` | Read soul/identity files |
| GET | `/admin/files/{scope}` | List files (mind/memories/agents/souvenirs) |
| GET | `/admin/files/{scope}/{path}` | Read file content |
| POST | `/maintenance` | ANALYZE high-write tables |
| GET | `/table-stats` | Dead tuple counts |

### Records (Generic)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/records` | Generic table browser (20 whitelisted) |
| GET | `/export` | Full table export (max 10K rows) |
| GET | `/search` | Cross-table ILIKE search |

---

## GraphQL (`/api/graphql`)

### Queries
activities, thoughts, memories, memory(key), goals, knowledge_entities, knowledge_relations, sessions, stats, graph_traverse, skill_for_task

### Mutations
upsert_memory(key, value, category), update_goal(goal_id, status, progress, priority)

---

## api_client Method → Endpoint Map

The `AriaAPIClient` in `aria_skills/api_client/` wraps all endpoints:

| Client Method | Endpoint |
|---------------|----------|
| `store_memory_semantic()` | POST `/memories/semantic` |
| `search_memories_semantic()` | GET `/memories/search` |
| `summarize_session()` | POST `/memories/summarize-session` |
| `remember()` / `recall()` | POST/GET `/working-memory` |
| `get_working_memory_context()` | GET `/working-memory/context` |
| `create_activity()` | POST `/activities` |
| `create_thought()` | POST `/thoughts` |
| `set_memory()` / `get_memory()` | POST/GET `/memories` |
| `create_goal()` / `update_goal()` | POST/PATCH `/goals` |
| `graph_traverse()` / `graph_search()` | GET `/knowledge-graph/*` |
| `find_skill_for_task()` | GET `/knowledge-graph/skill-for-task` |
| `create_social_post()` | POST `/social` |
| `record_lesson()` / `check_known_errors()` | POST/GET `/lessons` |
| `propose_improvement()` | POST `/proposals` |
| `record_invocation()` | POST `/skills/invocations` |

**Features:** Circuit breaker (5 fails → 30s), retry (3x, 0.5s backoff), auto-pagination via `get_all_pages()`
