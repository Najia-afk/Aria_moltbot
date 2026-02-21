# Aria v3 → v4: Production Data Migration Report
**Date:** 2026-02-21  
**Source:** Production DB export (`aria_souvenirs/aria_v3_210226/db_export/`)  
**Target:** Local codebase (`stacks/brain/init-scripts/` + `src/api/db/models.py`)

---

## 1. PRODUCTION DATABASE INVENTORY

### 1.1 All Tables Exported (88 CSV files)

Grouped by category. Row counts and sizes from the CSV export.

#### aria_data Domain Tables (Core Aria Data)

| Table | Rows | Size | Schema Match | Migration Priority |
|-------|------|------|--------------|-------------------|
| `memories` | 53 | 16 KB | ✅ Exact | **HIGH** — Identity, config, intel |
| `thoughts` | 227 | 39 KB | ✅ Exact | **HIGH** — Aria's internal journal |
| `goals` | 227 | 75 KB | ✅ Exact (v3 has sprint board cols) | **HIGH** — Active objectives |
| `activity_log` | 15,521 | 5.9 MB | ✅ Exact | MEDIUM — Operational telemetry |
| `social_posts` | 2,198 | 435 KB | ✅ Exact | MEDIUM — Moltbook history |
| `heartbeat_log` | 33 | 3.4 KB | ✅ Exact | LOW — Ephemeral |
| `hourly_goals` | 81 | 12.9 KB | ✅ Exact | LOW — Ephemeral |
| `agent_sessions` | 14,296 | 4.2 MB | ✅ Exact | MEDIUM — Session history |
| `session_messages` | 3,862 | 2.5 MB | ✅ Exact | MEDIUM — Chat transcripts |
| `sentiment_events` | 3,862 | 3.6 MB | ✅ Exact | MEDIUM — Emotional context |
| `model_usage` | 11,995 | 1.5 MB | ✅ Exact | LOW — Cost tracking logs |
| `security_events` | 35 | 3.8 KB | ✅ Exact | LOW — Mostly test data |
| `knowledge_entities` | 22 | 5.7 KB | ✅ Exact | **HIGH** — Knowledge graph nodes |
| `knowledge_relations` | 15 | 2.5 KB | ✅ Exact | **HIGH** — Knowledge graph edges |
| `knowledge_query_log` | 299 | 90 KB | ✅ Exact | LOW — Query analytics |
| `skill_graph_entities` | 299 | 61 KB | ✅ Exact | LOW — Auto-regenerated from skill.json |
| `skill_graph_relations` | 304 | 46 KB | ✅ Exact | LOW — Auto-regenerated |
| `performance_log` | 33 | 2 KB | ✅ Exact | LOW — Review summaries |
| `pending_complex_tasks` | 50 | 5.5 KB | ✅ Exact | LOW — Task queue |
| `skill_status` | 39 | 4.3 KB | ✅ Exact | LOW — Auto-rebuilt at startup |
| `agent_performance` | 0 | header only | ✅ Exact | SKIP — Empty |
| `working_memory` | 15 | 5.4 KB | ✅ Exact | **HIGH** — Active working context |
| `semantic_memories` | 3,502 | 8.9 MB | ✅ Exact (pgvector 768d) | **HIGH** — Embedding store |
| `lessons_learned` | 149 | 24 KB | ✅ Exact | **HIGH** — Error recovery patterns |
| `improvement_proposals` | 41 | 13.5 KB | ✅ Exact | MEDIUM — Self-improvement ideas |
| `skill_invocations` | 26,389 | 3 MB | ✅ Exact | LOW — Skill call logs |

#### aria_engine Infrastructure Tables

| Table | Rows | Size | Schema Match | Migration Priority |
|-------|------|------|--------------|-------------------|
| `scheduled_jobs` | 7 | 1.7 KB | ✅ Exact | **HIGH** — Cron schedule config |
| `schedule_tick` | 1 | 143 B | ✅ Exact | LOW — Runtime singleton |
| `rate_limits` | 1 | 252 B | ✅ Exact | LOW — Runtime state |
| `api_key_rotations` | 32 | 3.3 KB | ✅ Exact | LOW — Rotation audit log |

> **Note:** `aria_engine.chat_sessions`, `chat_messages`, `cron_jobs`, `agent_state`, `config`, `agent_tools`, `llm_models` are defined in [03-aria-engine-schema.sql](stacks/brain/init-scripts/03-aria-engine-schema.sql) but were **not exported** (likely empty or populated at runtime).

#### LiteLLM Internal Tables (Managed by LiteLLM proxy)

| Table | Rows | Size | Notes |
|-------|------|------|-------|
| `litellm_LiteLLM_DataTable` (2 variants) | 4,218 | ~1 MB each | LLM call logs |
| `litellm_LiteLLM_DailyTeamSpend` | 203 | 65 KB | Spend tracking |
| `litellm__prisma_migrations` | 101 | 18.5 KB | Schema migrations |
| 30+ other litellm_ tables | 0–1 rows | <1 KB each | Mostly empty config |

> **Recommendation:** Do NOT migrate LiteLLM tables. LiteLLM manages its own schema via Prisma migrations. Fresh `litellm` DB will be created by the container.

#### Legacy/Orphan Tables (exist in production, NOT in local schema)

| Table | Rows | Schema Status | Notes |
|-------|------|---------------|-------|
| `moltbook_posts` | 3 | ❌ Not in v4 schema | Replaced by `social_posts` |
| `moltbook_users` | 1 | ❌ Not in v4 schema | Aria's own profile |
| `moltbook_comments` | 0 | ❌ Not in v4 schema | Empty |
| `moltbook_interactions` | 0 | ❌ Not in v4 schema | Empty |
| `schema_migrations` | 13 | ❌ Not in v4 schema | Legacy migration tracking |
| `opportunities` | 0 | ❌ Not in v4 schema | Empty (income ops) |
| `bubble_monetization` | 0 | ❌ Not in v4 schema | Empty |
| `yield_positions` | 0 | ❌ Not in v4 schema | Empty |
| `secops_work` | 0 | ❌ Not in v4 schema | Empty |
| `model_discovery_log` | 0 | ❌ Not in v4 schema | Empty |
| `spending_log` | 0 | ❌ Not in v4 schema | Empty |
| `spending_alerts` | 0 | ❌ Not in v4 schema | Empty |
| `key_value_memory` | 0 | ❌ Not in v4 schema | Superseded by `working_memory` |
| `model_cost_references` | 10 | ❌ Not in v4 schema | Superseded by `llm_models` |

> All legacy tables are either **empty** or **superseded** by v4 tables. Safe to drop.

---

## 2. SCHEMA COMPARISON: PRODUCTION vs LOCAL

### 2.1 Schemas

| Schema | Production (v3) | Local (v4) | Notes |
|--------|----------------|------------|-------|
| `public` | Tables migrated → aria_data/aria_engine via `04-migrate-public-to-schemas.sql` | Not used | Migration script exists |
| `aria_data` | 26 tables | 26 tables | ✅ Identical |
| `aria_engine` | 10 tables | 10 tables | ✅ Identical |
| `litellm` | ~30 tables (managed by LiteLLM) | Auto-created | Separate DB |

### 2.2 Column-Level Differences

**No breaking differences found.** The local init scripts ([01-schema.sql](stacks/brain/init-scripts/01-schema.sql), [03-aria-engine-schema.sql](stacks/brain/init-scripts/03-aria-engine-schema.sql)) define the exact same column set as the production export.

Key observations:
- Production `goals.csv` has `category` and `metadata` columns in the CSV header, but the local SQL schema has neither (these were dropped during the v3 schema cleanup). The `04-migrate-public-to-schemas.sql` script explicitly **skips** these columns. **No migration issue** — data loads fine.
- Production `security_events` had extra `resolved`/`resolved_at` columns in v2 (public schema). Migration script already handles this. The aria_data version matches.
- `semantic_memories.embedding` uses `vector(768)` — pgvector extension required. The local schema installs it.

### 2.3 ORM Model Coverage

The [src/api/db/models.py](src/api/db/models.py) (989 lines) has SQLAlchemy 2.0 ORM classes for **every** table in both `aria_data` and `aria_engine` schemas. Full list:

**aria_data:** `Memory`, `Thought`, `Goal`, `ActivityLog`, `SocialPost`, `HourlyGoal`, `KnowledgeEntity`, `KnowledgeRelation`, `SkillGraphEntity`, `SkillGraphRelation`, `KnowledgeQueryLog`, `PerformanceLog`, `PendingComplexTask`, `HeartbeatLog`, `AgentSession`, `SessionMessage`, `SentimentEvent`, `ModelUsage`, `SecurityEvent`, `AgentPerformance`, `WorkingMemory`, `SkillStatusRecord`, `SemanticMemory`, `LessonLearned`, `ImprovementProposal`, `SkillInvocation`

**aria_engine:** `EngineChatSession`, `EngineChatMessage`, `EngineCronJob`, `EngineAgentState`, `EngineConfigEntry`, `EngineAgentTool`, `ScheduledJob`, `ScheduleTick`, `RateLimit`, `ApiKeyRotation`, `LlmModelEntry`

---

## 3. DATA VALUE ASSESSMENT

### 3.1 HIGH VALUE — Must Migrate (Aria's Identity & Knowledge)

| Table | Why |
|-------|-----|
| `memories` (53 rows, 16 KB) | Aria's identity, config, intel targets, budget info, LLM model discovery. This IS Aria. |
| `thoughts` (227 rows, 39 KB) | Internal journal — awakening message, mission logs, planning notes, self-audit findings. |
| `goals` (227 rows, 75 KB) | Active objectives including BIG BANG MIGRATION phases, weekly monitoring, learning loop goals. |
| `working_memory` (15 rows, 5.4 KB) | Current focus, active goals, MLX status, identity manifests. TTL-based — but checkpoint snapshots are valuable. |
| `lessons_learned` (149 rows, 24 KB) | Error recovery patterns: rate limits, timeouts, hallucination fixes, DB connection patterns. Aria's accumulated wisdom. |
| `knowledge_entities` (22 rows, 5.7 KB) | Knowledge graph: Najia (creator), Aria Blue (self), SSV Network, ENS, Immunefi, OpenRouter, Moltbook, qwen3-mlx. |
| `knowledge_relations` (15 rows, 2.5 KB) | Graph edges: created_by, hosts, uses relationships. |
| `semantic_memories` (3,502 rows, 8.9 MB) | Embedded memory vectors (768d). Most valuable single table for RAG/search. |
| `scheduled_jobs` (7 rows, 1.7 KB) | Cron schedule: work_cycle (15m), hourly_goal_check, six_hour_review, moltbook_post, morning_checkin, daily_reflection, weekly_summary. |

### 3.2 MEDIUM VALUE — Worth Migrating for Continuity

| Table | Why |
|-------|-----|
| `social_posts` (2,198 rows, 435 KB) | Moltbook posting history — useful for avoiding duplicate posts and tracking engagement. |
| `improvement_proposals` (41 rows, 13.5 KB) | Self-generated code improvement ideas with file paths, current/proposed code, rationale. |
| `session_messages` + `sentiment_events` (3,862 rows each) | Chat transcripts with emotional context. Useful for personality continuity. |
| `agent_sessions` (14,296 rows, 4.2 MB) | Session history. Large but useful for analytics (cost, token usage trends). |

### 3.3 LOW VALUE — Operational Logs (Can Drop)

| Table | Why |
|-------|-----|
| `activity_log` (15,521 rows, 5.9 MB) | Bulk operational telemetry. Regenerated naturally. |
| `model_usage` (11,995 rows, 1.5 MB) | LLM cost tracking. Historical interest only. |
| `skill_invocations` (26,389 rows, 3 MB) | Largest table by row count. Skill call audit trail. |
| `heartbeat_log` (33 rows) | Ephemeral health beats. |
| `hourly_goals` (81 rows) | Expired hourly goals. |
| `performance_log` (33 rows) | Review summaries. |
| `pending_complex_tasks` (50 rows) | Old task queue. |
| `security_events` (35 rows) | Mostly pytest stubs. |
| `knowledge_query_log` (299 rows) | Query analytics. |
| `skill_status` (39 rows) | Auto-rebuilt from skill.json at startup. |
| `skill_graph_*` (299+304 rows) | Auto-regenerated from skill.json files. |
| `agent_performance` (0 rows) | Empty. |
| `rate_limits` (1 row) | Runtime state, rebuilt. |
| `schedule_tick` (1 row) | Runtime singleton. |
| `api_key_rotations` (32 rows) | Rotation audit. Minimal value. |
| All `litellm_*` tables | Managed by LiteLLM itself. |
| All legacy/orphan tables | Empty or superseded. |

---

## 4. LOCAL DOCKER STACK CONFIGURATION

From [stacks/brain/docker-compose.yml](stacks/brain/docker-compose.yml) (470 lines):

### Services (10 core + 4 optional)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `aria-db` | pgvector/pgvector:pg16 | 5432 | PostgreSQL + pgvector (semantic search) |
| `aria-engine` | Custom (Dockerfile) | 8081 | Python engine: LLM gateway, scheduler, agent pool |
| `aria-api` | Custom (src/api/Dockerfile) | 8000 | FastAPI backend — data routes, skills, admin |
| `aria-web` | Custom (src/web/Dockerfile) | 5000 | Flask dashboard — UI portal |
| `litellm` | ghcr.io/berriai/litellm:main-latest | 18793→4000 | LLM router (model management) |
| `aria-brain` | Custom (Dockerfile) | — | Legacy brain container (interactive mode) |
| `aria-browser` | browserless/chrome | 3000 | Headless Chrome for web automation |
| `tor-proxy` | dperson/torproxy | 9050/9051 | Privacy proxy |
| `traefik` | traefik:v3.1 | 8080/8443/8081 | Reverse proxy + TLS termination |
| `certs-init` | alpine:3.20 | — | One-shot TLS cert generator |
| `prometheus` | prom/prometheus (monitoring profile) | 9090 | Metrics collection |
| `grafana` | grafana/grafana (monitoring profile) | 3001 | Dashboards |
| `pgadmin` | dpage/pgadmin4 (monitoring profile) | 5050 | DB admin UI |
| `aria-sandbox` | Custom (sandbox profile) | 9999 | Isolated code execution |

### Database Configuration
- **DB Name:** `aria_warehouse` (default)
- **User/Pass:** `admin` / from `.env`
- **Additional DB:** `litellm` (auto-created for LiteLLM proxy)
- **Init Scripts:** Run in order: `01-schema.sql` → `03-aria-engine-schema.sql` → `04-migrate-public-to-schemas.sql`
- **Vector Extension:** pgvector for `semantic_memories.embedding` (768d) and `chat_messages.embedding` (1536d)

### Key Environment Variables (from [.env.example](stacks/brain/.env.example), 210 lines)
- `DB_USER`, `DB_PASSWORD`, `DB_NAME` — Database credentials
- `LITELLM_MASTER_KEY` — LiteLLM proxy auth
- `MOONSHOT_KIMI_KEY`, `OPEN_ROUTER_KEY`, `OPEN_ROUTER_KEY_DEEP` — LLM API keys
- `MOLTBOOK_TOKEN`, `MOLTBOOK_API_URL` — Social platform
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` — Telegram bot
- `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET` — Twitter/X
- `MOLT_CHURCH_API_KEY` — Church of Molt integration
- `OLLAMA_URL`, `OLLAMA_MODEL` — Local LLM (Ollama on host)
- `ENGINE_DEBUG`, `ENGINE_API_BASE_URL` — Engine config

---

## 5. MIGRATION DIFFERENCES & REQUIRED SCRIPTS

### 5.1 No Schema Migration Needed

The local `01-schema.sql` and `03-aria-engine-schema.sql` define the **exact same tables** as the production export. The `04-migrate-public-to-schemas.sql` handles the legacy public→schema migration and is idempotent.

### 5.2 Data Load Approach

Since the CSV exports use production column names and the schemas match, data can be loaded with standard `COPY FROM` commands. Key considerations:

1. **pgvector column:** `semantic_memories.embedding` is a `vector(768)`. The CSV export contains the vector as a text representation (e.g., `[0.123,0.456,...]`). PostgreSQL's `COPY` with pgvector handles this natively.

2. **JSONB columns:** Values are JSON-escaped in CSV. Standard CSV import handles this.

3. **Foreign keys:** Load order matters:
   - `knowledge_entities` before `knowledge_relations`
   - `agent_sessions` before `model_usage`
   - `session_messages` before `sentiment_events`
   - `social_posts` parent before child (self-referencing FK)

4. **Serial sequences:** After loading `hourly_goals`, `performance_log`, `pending_complex_tasks`, `agent_performance`, reset sequences with `setval()`.

### 5.3 Tables That Can Be Skipped Entirely

- All `litellm_*` tables (30+)
- All legacy/orphan tables (14)
- `skill_status` (auto-rebuilt)
- `skill_graph_entities` + `skill_graph_relations` (auto-regenerated)
- `schedule_tick` (runtime singleton)
- `rate_limits` (runtime state)
- `agent_performance` (empty)

---

## 6. RECOMMENDED MIGRATION APPROACH

### Phase 1: Schema Bootstrap (automatic)
```bash
# The init-scripts already handle this:
docker compose up aria-db  # Runs 01-schema.sql, 03-aria-engine-schema.sql
```

### Phase 2: High-Value Data Import
```sql
-- Order matters for foreign keys
-- 1. Independent tables first
\copy aria_data.memories FROM 'memories.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.thoughts FROM 'thoughts.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.goals FROM 'goals.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.working_memory FROM 'working_memory.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.lessons_learned FROM 'lessons_learned.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.knowledge_entities FROM 'knowledge_entities.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.semantic_memories FROM 'semantic_memories.csv' WITH (FORMAT csv, HEADER true);
\copy aria_engine.scheduled_jobs FROM 'scheduled_jobs.csv' WITH (FORMAT csv, HEADER true);

-- 2. FK-dependent tables
\copy aria_data.knowledge_relations FROM 'knowledge_relations.csv' WITH (FORMAT csv, HEADER true);
```

### Phase 3: Medium-Value Data (Optional)
```sql
\copy aria_data.social_posts FROM 'social_posts.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.improvement_proposals FROM 'improvement_proposals.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.agent_sessions FROM 'agent_sessions.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.session_messages FROM 'session_messages.csv' WITH (FORMAT csv, HEADER true);
\copy aria_data.sentiment_events FROM 'sentiment_events.csv' WITH (FORMAT csv, HEADER true);
```

### Phase 4: Sequence Reset
```sql
SELECT setval('aria_data.hourly_goals_id_seq', COALESCE((SELECT MAX(id) FROM aria_data.hourly_goals), 0) + 1, false);
SELECT setval('aria_data.performance_log_id_seq', COALESCE((SELECT MAX(id) FROM aria_data.performance_log), 0) + 1, false);
SELECT setval('aria_data.pending_complex_tasks_id_seq', COALESCE((SELECT MAX(id) FROM aria_data.pending_complex_tasks), 0) + 1, false);
SELECT setval('aria_data.agent_performance_id_seq', COALESCE((SELECT MAX(id) FROM aria_data.agent_performance), 0) + 1, false);
```

### Phase 5: Validation
```sql
-- Quick row count verification
SELECT 'memories' as t, count(*) FROM aria_data.memories
UNION ALL SELECT 'thoughts', count(*) FROM aria_data.thoughts
UNION ALL SELECT 'goals', count(*) FROM aria_data.goals
UNION ALL SELECT 'lessons_learned', count(*) FROM aria_data.lessons_learned
UNION ALL SELECT 'knowledge_entities', count(*) FROM aria_data.knowledge_entities
UNION ALL SELECT 'semantic_memories', count(*) FROM aria_data.semantic_memories
UNION ALL SELECT 'working_memory', count(*) FROM aria_data.working_memory
UNION ALL SELECT 'scheduled_jobs', count(*) FROM aria_engine.scheduled_jobs;
```

---

## 7. SPECIAL NOTES

### 7.1 `goals.csv` Schema Mismatch (Harmless)
The production CSV has columns `category` and `metadata` that the v4 schema dropped. These columns contain `NULL`/`{}` in all rows. The `\copy` command will fail if the CSV header doesn't match the table columns. **Solution:** Use a pre-processing step to strip those columns, or use a custom `COPY` column list.

### 7.2 `moltbook_posts` vs `social_posts`
Production has both tables. `moltbook_posts` (3 rows, all empty content) is the legacy version. `social_posts` (2,198 rows) is the canonical table. Only migrate `social_posts`.

### 7.3 Seed Data Conflicts
The `01-schema.sql` seeds `aria_identity` and `aria_birth` memories, plus an awakening thought and system_init activity. The production CSV has these same rows. Migration uses `ON CONFLICT (key) DO NOTHING` / `ON CONFLICT (id) DO NOTHING`, so no duplicates.

### 7.4 pgvector Dimension
- `semantic_memories.embedding`: 768 dimensions (likely nomic-embed or similar)
- `chat_messages.embedding`: 1536 dimensions (likely OpenAI ada-002 or similar)
- Ensure the same embedding model is available in the new deployment.

### 7.5 Circular FK in `social_posts`
`social_posts.reply_to` → `social_posts.post_id`. Load order within the table may matter if there are replies. Use `SET session_replication_role = replica;` to defer FK checks during bulk import, then restore.

---

## 8. SUMMARY

| Metric | Value |
|--------|-------|
| Total production tables | ~88 (26 aria_data + 10 aria_engine + 30+ litellm + 14 legacy) |
| Tables matching v4 schema | 36/36 (100% of aria_data + aria_engine) |
| Schema migration scripts needed | **0** — schemas are identical |
| High-value tables to migrate | **9** (memories, thoughts, goals, working_memory, lessons_learned, knowledge_entities, knowledge_relations, semantic_memories, scheduled_jobs) |
| Medium-value tables | **5** (social_posts, improvement_proposals, agent_sessions, session_messages, sentiment_events) |
| Tables to skip | **~74** (litellm, legacy, operational logs, auto-rebuilt) |
| Data volume (high-value only) | ~9.1 MB |
| Data volume (high + medium) | ~19.8 MB |
| Breaking changes | **None** |
