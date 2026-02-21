# Aria Brain API — Complete Audit Report

> Generated: 2026-02-20 | Source: `src/api/` (FastAPI v3.0)

---

## Table of Contents

1. [Complete Endpoint Map](#1-complete-endpoint-map)
2. [DB Models & Schema](#2-db-models--schema)
3. [Entity Relationships](#3-entity-relationships)
4. [CRUD Completeness Matrix](#4-crud-completeness-matrix)
5. [Real Workflow Chains](#5-real-workflow-chains)
6. [NOT NULL / Required Fields Analysis](#6-not-null--required-fields-analysis)

---

## 1. Complete Endpoint Map

### 1.1 Goals (`routers/goals.py`) — tag: `Goals`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/goals` | `?page, limit, status` | Paginated goals list | Ordered by priority ASC, created DESC |
| POST | `/goals` | `{goal_id?, title, description?, status?, progress?, priority?, due_date?, sprint?, board_column?, position?, assigned_to?, tags?}` | `{id, goal_id, created}` | Noise filter skips test payloads |
| GET | `/goals/{goal_id}` | UUID or goal_id string | Goal dict | Tries UUID parse first |
| PATCH | `/goals/{goal_id}` | `{status?, progress?, priority?, sprint?, board_column?, position?, assigned_to?, tags?, title?, description?, due_date?}` | `{updated: true}` | Auto-syncs board_column from status |
| DELETE | `/goals/{goal_id}` | — | `{deleted: true}` | By UUID or goal_id |
| GET | `/goals/board` | `?sprint` | `{sprint, columns:{backlog,todo,doing,on_hold,done}, counts, total}` | Kanban view, auto-reconciles status↔column |
| GET | `/goals/archive` | `?page, limit` | Paginated completed/cancelled goals | |
| PATCH | `/goals/{goal_id}/move` | `{board_column, position?}` | `{moved, board_column, position}` | Drag-and-drop, auto-sets status |
| GET | `/goals/sprint-summary` | `?sprint` | `{sprint, status_counts, total, top_active, summary}` | Lightweight ~200 token summary |
| GET | `/goals/history` | `?days=14` | `{days, data:{day→{status→count}}, labels}` | Status distribution by day |
| GET | `/hourly-goals` | `?status` | `{goals, count}` | |
| POST | `/hourly-goals` | `{hour_slot, goal_type, description, status?}` | `{created}` | |
| PATCH | `/hourly-goals/{goal_id}` | `{status}` | `{updated}` | |

### 1.2 Engine Chat (`routers/engine_chat.py`) — tag: `Engine Chat`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| POST | `/engine/chat/sessions` | `CreateSessionRequest{agent_id?, model?, session_type?, system_prompt?, temperature?, max_tokens?, context_window?, metadata?}` | `CreateSessionResponse{id, agent_id, model, status, session_type, created_at}` | 201 status |
| GET | `/engine/chat/sessions` | `?page, page_size, agent_id, status` | `PaginatedSessions{items, total, page, page_size, pages}` | |
| GET | `/engine/chat/sessions/{session_id}` | — | `SessionDetail` with messages array | Full message history |
| POST | `/engine/chat/sessions/{session_id}/messages` | `SendMessageRequest{content, enable_thinking?, enable_tools?}` | `SendMessageResponse{message_id, session_id, content, thinking, tool_calls, tool_results, model, input_tokens, output_tokens, total_tokens, cost_usd, latency_ms, finish_reason}` | Non-streaming |
| DELETE | `/engine/chat/sessions/{session_id}` | — | `{status: "ended", session_id}` | Marks as ended, preserves history |
| GET | `/engine/chat/sessions/{session_id}/export` | `?format=jsonl|markdown` | File download (JSONL or Markdown) | |
| WS | `/ws/chat/{session_id}` | JSON messages `{type, content, enable_thinking}` | Streaming tokens | WebSocket |

### 1.3 Engine Sessions (`routers/engine_sessions.py`) — tag: `engine-sessions`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/engine/sessions` | `?agent_id, session_type, search, date_from, date_to, sort, order, limit, offset` | `SessionListResponse{sessions, total, limit, offset, has_more}` | Full-text search, date range |
| GET | `/engine/sessions/stats` | — | `SessionStatsResponse{total_sessions, total_messages, active_agents, oldest_session, newest_activity}` | |
| GET | `/engine/sessions/{session_id}` | — | `SessionDetailResponse` with recent_messages (last 10) | |
| GET | `/engine/sessions/{session_id}/messages` | `?limit, offset, since` | `list[MessageResponse]` | Incremental loading via `since` |
| DELETE | `/engine/sessions/{session_id}` | — | `{status: "deleted", session_id}` | Hard delete |
| POST | `/engine/sessions/{session_id}/end` | — | `{status: "ended", session_id}` | Soft end |

### 1.4 Agent Sessions (`routers/sessions.py`) — tag: `Sessions`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/sessions` | `?page, limit, status, agent_id, session_type, search, include_runtime_events, include_cron_events` | Paginated sessions | Filters out skill_exec/cron by default |
| GET | `/sessions/hourly` | `?hours, include_runtime_events, include_cron_events, status, agent_id` | `{hours, timezone, items:[{hour, agent_id, count}]}` | Time-series chart data |
| POST | `/sessions` | `{agent_id?, session_type?, messages_count?, tokens_used?, cost_usd?, status?, started_at?, ended_at?, metadata?, external_session_id?}` | `{id, created}` | |
| PATCH | `/sessions/{session_id}` | `{status?, messages_count?, tokens_used?, cost_usd?}` | `{updated}` | Auto-sets ended_at on completion |
| DELETE | `/sessions/{session_id}` | — | `{deleted, id}` | |
| GET | `/sessions/stats` | `?include_runtime_events, include_cron_events, status, agent_id` | Stats object with LiteLLM enrichment | Merges skills DB + LiteLLM DB |

### 1.5 Knowledge Graph (`routers/knowledge.py`) — tag: `Knowledge Graph`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/knowledge-graph` | `?limit, offset` | `{entities, relations, stats}` | Full KG dump |
| GET | `/knowledge-graph/entities` | `?limit, offset, type` | `{entities}` | |
| GET | `/knowledge-graph/relations` | `?limit` | `{relations}` | With from_name/to_name resolved |
| POST | `/knowledge-graph/entities` | `EntityCreate{name, type, properties?}` | `{id, created}` | Pydantic validated |
| POST | `/knowledge-graph/relations` | `RelationCreate{from_entity, to_entity, relation_type, properties?}` | `{id, created}` | FK to entities |
| GET | `/knowledge-graph/traverse` | `?start, relation_type, max_depth, direction` | `{nodes, edges, traversal_depth, total_nodes, total_edges}` | BFS on skill graph |
| GET | `/knowledge-graph/search` | `?q, entity_type, limit` | `{results, query, count}` | ILIKE on skill graph |
| GET | `/knowledge-graph/skill-for-task` | `?task, limit` | `{task, candidates, count, tools_searched}` | Skill discovery |
| GET | `/knowledge-graph/query-log` | `?limit, query_type` | `{logs, count}` | Query audit trail |
| DELETE | `/knowledge-graph/auto-generated` | — | `{deleted_entities, deleted_relations, status}` | Clears skill graph only |
| POST | `/knowledge-graph/sync-skills` | — | `{status, stats}` | Trigger graph sync |
| GET | `/skill-graph` | `?limit, offset` | `{entities, relations, stats}` | Dedicated skill graph tables |

### 1.6 Memories (`routers/memories.py`) — tag: `Memories`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/memories` | `?page, limit, category` | Paginated memories | Key-value store |
| POST | `/memories` | `{key, value, category?}` | `{id, key, upserted}` | Upsert by key |
| GET | `/memories/{key}` | — | Memory dict | By key string |
| DELETE | `/memories/{key}` | — | `{deleted, key}` | |
| GET | `/memories/semantic` | `?category, source, limit, page, min_importance` | Paginated semantic memories | No embedding needed |
| POST | `/memories/semantic` | `{content, category?, importance?, source?, summary?, metadata?}` | `{id, stored}` | Auto-generates embedding |
| GET | `/memories/search` | `?query, limit, category, min_importance` | `{memories, query}` | pgvector cosine search |
| POST | `/memories/search-by-vector` | `{embedding, category?, limit?, min_importance?}` | `{memories, count}` | Pre-computed embedding |
| POST | `/memories/summarize-session` | `{hours_back?}` | `{summary, decisions, stored, ids}` | LLM-powered episodic memory |

### 1.7 Activities (`routers/activities.py`) — tag: `Activities`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/activities` | `?page, limit, action` | Paginated activity log | |
| POST | `/activities` | `{action, skill?, details?, success?, error_message?}` | `{id, created}` | Mirrors commits/comments to social feed; six_hour_review has 5h cooldown |
| GET | `/activities/cron-summary` | `?days=7` | Cron execution stats | |
| GET | `/activities/timeline` | `?days=7` | `[{day, count}]` | Daily aggregation |
| GET | `/activities/visualization` | `?hours, limit, include_creative` | Rich dashboard payload | Hourly, action, skill breakdowns + creative insights |

### 1.8 Social (`routers/social.py`) — tag: `Social`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/social` | `?page, limit, platform` | Paginated social posts | |
| POST | `/social` | `{platform?, content, visibility?, reply_to?, url?, post_id?, metadata?}` | `{id, created}` | |
| POST | `/social/cleanup` | `{patterns?, platform?, dry_run?}` | `{matched, deleted, dry_run}` | Remove test/noise posts |
| POST | `/social/dedupe` | `{dry_run?, platform?}` | `{duplicates_found, deleted, dry_run}` | Dedup by (platform, post_id) |
| POST | `/social/import-moltbook` | `{include_comments?, cleanup_test?, dry_run?, max_items?, api_url?, api_key?}` | `{fetched_posts, fetched_comments, prepared, imported, skipped_existing, cleanup, dry_run}` | Full Moltbook backfill |

### 1.9 Thoughts (`routers/thoughts.py`) — tag: `Thoughts`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/thoughts` | `?page, limit` | Paginated thoughts | |
| POST | `/thoughts` | `{content, category?, metadata?}` | `{id, created}` | |

### 1.10 Working Memory (`routers/working_memory.py`) — tag: `Working Memory`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/working-memory` | `?page, category, key, limit` | Paginated items | |
| POST | `/working-memory` | `{key, value, category?, importance?, ttl_hours?, source?}` | `{id, key, upserted}` | Upsert by (category, key) |
| PATCH | `/working-memory/{item_id}` | `{value?, importance?}` | Item dict | |
| DELETE | `/working-memory/{item_id}` | — | `{deleted, id}` | |
| GET | `/working-memory/context` | `?limit, weight_recency, weight_importance, weight_access, touch_access, category` | `{context:[{...item, relevance}], count}` | Weighted retrieval |
| POST | `/working-memory/checkpoint` | — | `{checkpoint_id, items_checkpointed, created_at}` | Snapshots entire WM state |
| GET | `/working-memory/checkpoint` | — | `{checkpoint_id, items, count}` | Latest checkpoint |
| GET | `/working-memory/stats` | — | `{total_items, categories, avg_importance, checkpoint_count, expired_count, by_category}` | |
| GET | `/working-memory/file-snapshot` | — | File-based context.json | Reads from disk |
| POST | `/working-memory/cleanup` | `CleanupRequest{category?, source?, delete_expired?, dry_run?}` | `{matched, deleted, dry_run}` | |

### 1.11 Lessons (`routers/lessons.py`) — tag: `Lessons`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| POST | `/lessons` | `{error_pattern, error_type, resolution?, skill_name?, context?, resolution_code?, effectiveness?}` | `{created|updated, id}` | Upsert by error_pattern (increments occurrences) |
| GET | `/lessons` | `?page, per_page` | Paginated lessons | |
| GET | `/lessons/check` | `?error_type, skill_name, error_message` | `{lessons, has_resolution}` | Error resolution lookup |
| POST | `/lessons/seed` | — | `{seeded, total}` | Seeds 5 known patterns (idempotent) |

### 1.12 Proposals (`routers/proposals.py`) — tag: `Proposals`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| POST | `/proposals` | `{title, description, category?, risk_level?, file_path?, current_code?, proposed_code?, rationale?}` | `{created, id}` | Cannot modify soul/ paths |
| GET | `/proposals` | `?status, page, per_page` | Paginated | |
| GET | `/proposals/{proposal_id}` | — | Proposal dict | |
| PATCH | `/proposals/{proposal_id}` | `{status: "approved"|"rejected"|"implemented", reviewed_by?}` | `{updated, id, status}` | Review workflow |

### 1.13 Skills (`routers/skills.py`) — tag: `Skills`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/skills` | `?status` | `{skills, count, healthy, degraded, unavailable}` | Auto-seeds on first access |
| GET | `/skills/{name}/health` | — | Skill health dict | |
| POST | `/skills/seed` | — | `{seeded, total}` | 37 known skills (idempotent) |
| GET | `/skills/coherence` | `?include_support` | Filesystem coherence scan | Checks init, skill.json, SKILL.md |
| POST | `/skills/invocations` | `{skill_name, tool_name, duration_ms?, success?, error_type?, tokens_used?, model_used?}` | `{recorded}` | |
| GET | `/skills/stats` | `?hours` | Per-skill performance stats | |
| GET | `/skills/stats/summary` | `?hours` | Compact aggregate summary | |
| GET | `/skills/stats/{skill_name}` | `?hours` | Detail stats + recent invocations | |
| GET | `/skills/insights` | `?hours, limit` | Rich dashboard payload | Stats + timeline + graph queries |
| GET | `/skills/health/dashboard` | `?hours` | `{overall, skills, patterns, unhealthy_skills, degraded_skills, slow_skills}` | Health scores + failure patterns |

### 1.14 Operations (`routers/operations.py`) — tag: `Operations`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/rate-limits` | — | `{rate_limits, count}` | |
| POST | `/rate-limits/check` | `{skill, max_actions?, window_seconds?}` | `{allowed, remaining, window_age}` | |
| POST | `/rate-limits/increment` | `{skill, action_type?}` | `{incremented, skill}` | Upsert on conflict |
| GET | `/api-key-rotations` | `?limit, service` | `{rotations, count}` | |
| POST | `/api-key-rotations` | `{service, reason?, rotated_by?, metadata?}` | `{id, created}` | |
| GET | `/heartbeat` | `?limit` | `{heartbeats, count}` | |
| POST | `/heartbeat` | `{beat_number, status?, details?}` | `{id, created}` | |
| GET | `/heartbeat/latest` | — | Latest heartbeat dict | |
| GET | `/performance` | `?limit` | `{logs, count}` | |
| POST | `/performance` | `{review_period, successes?, failures?, improvements?}` | `{created}` | |
| GET | `/tasks` | `?status` | `{tasks, count}` | PendingComplexTask |
| POST | `/tasks` | `{task_id?, task_type, description, agent_type, priority?, status?}` | `{task_id, created}` | |
| PATCH | `/tasks/{task_id}` | `{status, result?}` | `{updated}` | |
| GET | `/schedule` | — | Schedule tick singleton | |
| POST | `/schedule/tick` | — | `{ticked, at, jobs_total}` | Reads jobs.json |
| GET | `/jobs` | — | `{jobs, count}` | DB synced jobs |
| GET | `/jobs/live` | — | `{jobs, count, source: "live"}` | Direct from jobs.json |
| GET | `/jobs/{job_id}` | — | Job dict | |
| POST | `/jobs/sync` | — | `{synced, source, total_in_file}` | jobs.json → DB sync |

### 1.15 Engine Cron (`routers/engine_cron.py`) — tag: `engine-cron`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/engine/cron` | — | `CronJobListResponse{total, jobs, scheduler_running}` | |
| POST | `/engine/cron` | `CronJobCreate{id?, name, schedule, agent_id?, enabled?, payload_type, payload, session_mode?, max_duration_seconds?, retry_count?}` | `CronJobResponse` | 201, schedule validated |
| GET | `/engine/cron/status` | — | `SchedulerStatusResponse{running, active_executions, active_job_ids, max_concurrent}` | |
| GET | `/engine/cron/{job_id}` | — | `CronJobResponse` | |
| PUT | `/engine/cron/{job_id}` | `CronJobUpdate{name?, schedule?, agent_id?, enabled?, ...}` | `CronJobResponse` | Full update |
| DELETE | `/engine/cron/{job_id}` | — | 204 No Content | |
| POST | `/engine/cron/{job_id}/trigger` | — | `TriggerResponse{triggered, job_id, message}` | Manual run |
| GET | `/engine/cron/{job_id}/history` | `?limit` | `CronHistoryResponse{job_id, total, entries}` | Execution history |

### 1.16 Engine Agents (`routers/engine_agents.py`) — tag: `engine-agents`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/engine/agents` | — | `AgentPoolStatus{total_agents, max_concurrent, status_counts, agents}` | |
| GET | `/engine/agents/{agent_id}` | — | `AgentSummary` | |

### 1.17 Agent Metrics (`routers/engine_agent_metrics.py`) — tag: `engine-agents`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/engine/agents/metrics` | — | `AgentMetricsResponse{agents, total_messages, total_errors, avg_pheromone, timestamp}` | Raw SQL on aria_engine schema |
| GET | `/engine/agents/metrics/{agent_id}` | — | `AgentMetricDetail` with recent_sessions, last_error | |
| GET | `/engine/agents/metrics/{agent_id}/history` | `?days` | `{agent_id, days, data_points:[{timestamp, score, interactions}]}` | Pheromone trend |

### 1.18 Model Usage (`routers/model_usage.py`) — tag: `Model Usage`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/model-usage` | `?page, limit, hours, model, provider, source` | Paginated merged list (skills DB + LiteLLM) | |
| POST | `/model-usage` | `{model, provider?, input_tokens?, output_tokens?, cost_usd?, latency_ms?, success?, error_message?, session_id?}` | `{id, created}` | |
| GET | `/model-usage/stats` | `?hours` | Merged stats: per-model breakdown, sources split | |

### 1.19 Security (`routers/security.py`) — tag: `Security`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/security-events` | `?page, limit, threat_level, blocked_only` | Paginated | |
| POST | `/security-events` | `{threat_level?, threat_type?, threat_patterns?, input_preview?, source?, user_id?, blocked?, details?}` | `{id, created}` | |
| GET | `/security-events/stats` | — | `{total_events, blocked_count, last_24h, by_level, by_type}` | |

### 1.20 LiteLLM (`routers/litellm.py`) — tag: `LiteLLM`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/litellm/models` | — | Model list (proxied) | |
| GET | `/litellm/health` | — | `{status}` | |
| GET | `/litellm/spend` | `?limit, offset, lite` | `{logs, total, offset, limit}` | Direct DB query |
| GET | `/litellm/global-spend` | — | `{spend, max_budget, total_tokens, ...}` | |

### 1.21 Providers (`routers/providers.py`) — tag: `Providers`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/providers/balances` | — | `{kimi, openrouter, local}` | Parallel balance fetch |

### 1.22 Models Config (`routers/models_config.py`) — tag: `Models`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/models/config` | — | Full model catalog (YAML-driven) | |
| GET | `/models/pricing` | — | Lightweight pricing-only view | |
| POST | `/models/reload` | — | `{status, models_count}` | Hot reload |

### 1.23 Analysis (`routers/analysis.py`) — prefix: `/analysis`, tag: `Analysis`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| POST | `/analysis/sentiment/message` | `{text, role?, context?}` | Sentiment analysis result | Per-message scoring |
| POST | `/analysis/sentiment/backfill-sessions` | `{session_ids?, max_messages?, ...}` | Backfill from JSONL session files | |
| POST | `/analysis/sentiment/conversation` | `{messages, context?}` | Conversation-level sentiment | |
| POST | `/analysis/sentiment/reply` | `{text, history?}` | Sentiment-aware reply guidance | |
| POST | `/analysis/sentiment/backfill-messages` | `{...}` | Backfill from session_messages table | |
| GET | `/analysis/sentiment/history` | `?hours, session_id, limit` | `{events, count}` | SentimentEvent query |
| POST | `/analysis/sentiment/seed-references` | — | Seeds reference embeddings | |
| POST | `/analysis/sentiment/feedback` | `{event_id, correct_label, ...}` | Feedback for sentiment model | |
| POST | `/analysis/sentiment/auto-promote` | — | Auto-promote high-confidence corrections | |
| POST | `/analysis/sentiment/cleanup-placeholders` | — | Remove placeholder sentiment rows | |
| POST | `/analysis/patterns/detect` | `{text, context?}` | Pattern recognition | |
| GET | `/analysis/patterns/history` | `?hours, limit` | Activity-based pattern history | |
| POST | `/analysis/compression/run` | `{content, target_ratio?}` | Memory compression result | |
| GET | `/analysis/compression/history` | `?hours, limit` | Compression activity history | |
| POST | `/analysis/compression/auto-run` | `{...}` | Automatic compression pipeline | |
| POST | `/analysis/seed-memories` | — | Seed semantic memories | |

### 1.24 Health (`routers/health.py`) — tag: `Health`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/health` | — | `{status, uptime_seconds, database, version}` | |
| GET | `/host-stats` | — | RAM/swap/disk/SMART | Proxied from host agent |
| GET | `/status` | — | All service health checks | Parallel HTTP checks |
| GET | `/status/{service_id}` | — | Single service health | |
| GET | `/stats` | — | `{activities_count, thoughts_count, memories_count, last_activity}` | |
| GET | `/health/db` | — | DB health: tables, pgvector, extensions | |

### 1.25 Admin (`routers/admin.py`) — tag: `Admin`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| POST | `/admin/services/{service_id}/{action}` | Header: `X-Admin-Token` | `{status, code, stdout, stderr}` | restart/stop/start via Docker socket |
| GET | `/soul/{filename}` | — | `{filename, content}` | Whitelisted soul .md files |
| GET | `/admin/files/mind` | — | File tree of /aria_mind | |
| GET | `/admin/files/memories` | — | File tree of /aria_memories | |
| GET | `/admin/files/agents` | — | File tree of /aria_agents | |
| GET | `/admin/files/souvenirs` | — | File tree of /aria_souvenirs | |
| GET | `/admin/files/mind/{path}` | — | File content | Safe extensions only |
| GET | `/admin/files/memories/{path}` | — | File content | |
| GET | `/admin/files/agents/{path}` | — | File content | |
| GET | `/admin/files/souvenirs/{path}` | — | File content | |
| POST | `/maintenance` | — | `{maintenance, tables}` | ANALYZE on high-write tables |
| GET | `/table-stats` | — | Dead tuple counts | pg_stat_user_tables |

### 1.26 Records (`routers/records.py`) — tag: `Records`

| Method | Path | Payload / Params | Response | Notes |
|--------|------|-----------------|----------|-------|
| GET | `/records` | `?table, limit, page` | `{records, total, page, limit}` | Generic table browser (18 tables) |
| GET | `/export` | `?table` | `{records}` | Up to 10K rows |
| GET | `/search` | `?q, activities, thoughts, memories` | `{activities, thoughts, memories}` | Cross-table ILIKE search |

---

## 2. DB Models & Schema

### 2.1 All Tables (29 total)

| Table | Primary Key | Key Columns |
|-------|-------------|-------------|
| `memories` | UUID `id` | `key` (UNIQUE, NOT NULL), `value` (JSONB, NOT NULL), `category` |
| `thoughts` | UUID `id` | `content` (NOT NULL), `category`, `metadata` (JSONB) |
| `goals` | UUID `id` | `goal_id` (UNIQUE, NOT NULL), `title` (NOT NULL), `status`, `priority`, `progress`, sprint/board fields |
| `activity_log` | UUID `id` | `action` (NOT NULL), `skill`, `details` (JSONB), `success` |
| `social_posts` | UUID `id` | `post_id` (UNIQUE), `content` (NOT NULL), `platform`, `visibility`, `reply_to` (FK self) |
| `hourly_goals` | INT `id` (auto) | `hour_slot` (NOT NULL), `goal_type` (NOT NULL), `description` (NOT NULL), `status` |
| `knowledge_entities` | UUID `id` | `name` (NOT NULL), `type` (NOT NULL), `properties` (JSONB) |
| `knowledge_relations` | UUID `id` | `from_entity` (FK, NOT NULL), `to_entity` (FK, NOT NULL), `relation_type` (NOT NULL) |
| `skill_graph_entities` | UUID `id` | `name` (NOT NULL), `type` (NOT NULL) — UNIQUE(name, type) |
| `skill_graph_relations` | UUID `id` | `from_entity` (FK, NOT NULL), `to_entity` (FK, NOT NULL), `relation_type` (NOT NULL) |
| `knowledge_query_log` | UUID `id` | `query_type` (NOT NULL), `params` (JSONB), `result_count`, `source` |
| `performance_log` | INT `id` (auto) | `review_period` (NOT NULL) |
| `pending_complex_tasks` | INT `id` (auto) | `task_id` (UNIQUE, NOT NULL), `task_type` (NOT NULL), `description` (NOT NULL), `agent_type` (NOT NULL) |
| `heartbeat_log` | UUID `id` | `beat_number` (NOT NULL), `status`, `details` (JSONB) |
| `scheduled_jobs` | STRING `id` | `name` (NOT NULL), `schedule_expr` (NOT NULL), `enabled` |
| `security_events` | UUID `id` | `threat_level` (NOT NULL), `threat_type` (NOT NULL), `blocked` |
| `schedule_tick` | INT `id` | Singleton control row |
| `agent_sessions` | UUID `id` | `agent_id` (NOT NULL), `session_type`, `status`, `metadata` (JSONB) |
| `session_messages` | UUID `id` | `role` (NOT NULL), `content` (NOT NULL), `content_hash` (NOT NULL), `session_id` (FK), `external_session_id` |
| `sentiment_events` | UUID `id` | `message_id` (FK, NOT NULL, UNIQUE), `sentiment_label` (NOT NULL), `valence`, `arousal`, `dominance`, `confidence` |
| `model_usage` | UUID `id` | `model` (NOT NULL), `session_id` (FK) |
| `rate_limits` | UUID `id` | `skill` (UNIQUE, NOT NULL) |
| `api_key_rotations` | UUID `id` | `service` (NOT NULL) |
| `agent_performance` | INT `id` (auto) | `agent_id` (NOT NULL), `task_type` (NOT NULL), `success` (NOT NULL) |
| `working_memory` | UUID `id` | `category` (NOT NULL), `key` (NOT NULL), `value` (JSONB, NOT NULL) — UNIQUE(category, key) |
| `skill_status` | UUID `id` | `skill_name` (UNIQUE, NOT NULL), `canonical_name` (NOT NULL), `status` |
| `semantic_memories` | UUID `id` | `content` (NOT NULL), `embedding` (Vector(768), NOT NULL) |
| `lessons_learned` | UUID `id` | `error_pattern` (NOT NULL, UNIQUE), `error_type` (NOT NULL), `resolution` (NOT NULL) |
| `improvement_proposals` | UUID `id` | `title` (NOT NULL), `description` (NOT NULL), `status`, `risk_level` |
| `skill_invocations` | UUID `id` | `skill_name` (NOT NULL), `tool_name` (NOT NULL), `success` |
| `engine_chat_sessions` | UUID `id` | `agent_id` (NOT NULL), `session_type` (NOT NULL), `status` (NOT NULL) |
| `engine_chat_messages` | UUID `id` | `session_id` (FK, NOT NULL), `role` (NOT NULL), `content` (NOT NULL) |
| `engine_cron_jobs` | STRING `id` | `name` (NOT NULL), `schedule` (NOT NULL), `payload` (NOT NULL) |
| `engine_agent_state` | STRING `agent_id` | `model` (NOT NULL) |
| `engine_config` | STRING `key` | `value` (JSONB, NOT NULL) |
| `engine_agent_tools` | UUID `id` | `agent_id` (NOT NULL), `skill_name` (NOT NULL), `function_name` (NOT NULL) |

---

## 3. Entity Relationships

```
┌──────────────────────────────────────────────────────────────────────┐
│                         ENTITY RELATIONSHIP DIAGRAM                  │
└──────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐       1:N       ┌──────────────────────┐
  │ EngineChatSession│───────────────→│ EngineChatMessage     │
  │  (engine_chat_   │                │  session_id (FK, NOT  │
  │   sessions)      │                │  NULL, CASCADE)       │
  └─────────────────┘                └──────────────────────┘

  ┌─────────────────┐       1:N       ┌──────────────────────┐
  │ AgentSession     │───────────────→│ ModelUsage            │
  │  (agent_sessions)│                │  session_id (FK, SET  │
  └─────────────────┘                │  NULL)                │
          │                           └──────────────────────┘
          │  1:N
          ▼
  ┌──────────────────────┐
  │ SessionMessage        │
  │  session_id (FK, SET  │──── 1:1 ───→ SentimentEvent
  │  NULL)                │              message_id (FK, CASCADE)
  └──────────────────────┘

  ┌─────────────────┐       1:N       ┌──────────────────────┐
  │ KnowledgeEntity  │←──────────────│ KnowledgeRelation     │
  │  (organic)       │  from_entity   │  from_entity (FK,     │
  │                  │  to_entity     │  CASCADE)             │
  │                  │←──────────────│  to_entity (FK,       │
  └─────────────────┘                │  CASCADE)             │
                                      └──────────────────────┘

  ┌─────────────────┐       1:N       ┌──────────────────────┐
  │ SkillGraphEntity │←──────────────│ SkillGraphRelation    │
  │  (skill-specific)│  from/to       │  from_entity (FK,     │
  │  UQ(name, type)  │               │  CASCADE)             │
  └─────────────────┘                └──────────────────────┘

  ┌─────────────────┐                 ┌──────────────────────┐
  │ SocialPost       │── reply_to ──→│ SocialPost (self-FK)  │
  │                  │   (post_id,    │  SET NULL             │
  └─────────────────┘    optional)   └──────────────────────┘

  ┌─────────────────────────────────────────────────────────┐
  │  STANDALONE ENTITIES (no FK relationships)              │
  │                                                         │
  │  Memory, Thought, Goal, HourlyGoal, ActivityLog,        │
  │  HeartbeatLog, PerformanceLog, PendingComplexTask,      │
  │  ScheduledJob, ScheduleTick, SecurityEvent, RateLimit,  │
  │  ApiKeyRotation, AgentPerformance, WorkingMemory,       │
  │  SkillStatusRecord, SemanticMemory, LessonLearned,      │
  │  ImprovementProposal, SkillInvocation,                  │
  │  EngineCronJob, EngineAgentState, EngineConfigEntry,    │
  │  EngineAgentTool, KnowledgeQueryLog                     │
  └─────────────────────────────────────────────────────────┘
```

### Foreign Key Summary

| Child Table | FK Column | Parent Table | On Delete |
|-------------|-----------|--------------|-----------|
| `engine_chat_messages` | `session_id` | `engine_chat_sessions` | CASCADE |
| `model_usage` | `session_id` | `agent_sessions` | SET NULL |
| `session_messages` | `session_id` | `agent_sessions` | SET NULL |
| `sentiment_events` | `message_id` | `session_messages` | CASCADE |
| `sentiment_events` | `session_id` | `agent_sessions` | SET NULL |
| `knowledge_relations` | `from_entity` | `knowledge_entities` | CASCADE |
| `knowledge_relations` | `to_entity` | `knowledge_entities` | CASCADE |
| `skill_graph_relations` | `from_entity` | `skill_graph_entities` | CASCADE |
| `skill_graph_relations` | `to_entity` | `skill_graph_entities` | CASCADE |
| `social_posts` | `reply_to` | `social_posts.post_id` | SET NULL |

---

## 4. CRUD Completeness Matrix

| Entity | CREATE | READ (List) | READ (Single) | UPDATE | DELETE | Notes |
|--------|--------|-------------|---------------|--------|--------|-------|
| **Goal** | ✅ POST | ✅ GET (paginated) | ✅ GET by id/goal_id | ✅ PATCH | ✅ DELETE | Full CRUD + board/archive/summary |
| **HourlyGoal** | ✅ POST | ✅ GET | ❌ | ✅ PATCH (status only) | ❌ | Missing single-read and delete |
| **Memory (KV)** | ✅ POST (upsert) | ✅ GET (paginated) | ✅ GET by key | ❌ (upsert only) | ✅ DELETE by key | No PATCH — upsert replaces |
| **SemanticMemory** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ | No single-read, update, or delete |
| **Thought** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ | Read+Create only |
| **ActivityLog** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ | Append-only log |
| **SocialPost** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ (via cleanup) | No single-read, no update, bulk delete only |
| **WorkingMemory** | ✅ POST (upsert) | ✅ GET (paginated) | ❌ (by filter) | ✅ PATCH | ✅ DELETE | Full CRUD via ID |
| **LessonLearned** | ✅ POST (upsert) | ✅ GET (paginated) | ❌ | ❌ (via upsert) | ❌ | No single-read, no delete |
| **ImprovementProposal** | ✅ POST | ✅ GET (paginated) | ✅ GET by ID | ✅ PATCH (review) | ❌ | No delete |
| **KnowledgeEntity** | ✅ POST | ✅ GET | ❌ | ❌ | ❌ (bulk via auto-generated) | No single-read, update, or individual delete |
| **KnowledgeRelation** | ✅ POST | ✅ GET | ❌ | ❌ | ❌ (bulk via auto-generated) | Same as entities |
| **SkillGraphEntity** | ❌ (via sync) | ✅ GET | ❌ | ❌ | ✅ (bulk delete) | Read-only + sync |
| **SkillStatusRecord** | ✅ (via seed) | ✅ GET | ✅ GET health | ❌ | ❌ | Seed only |
| **SkillInvocation** | ✅ POST | ✅ GET (via stats) | ❌ | ❌ | ❌ | Write + aggregate-only |
| **AgentSession** | ✅ POST | ✅ GET (paginated) | ❌ | ✅ PATCH | ✅ DELETE | |
| **SessionMessage** | ❌ (engine-created) | ✅ GET (via engine) | ❌ | ❌ | ❌ | Managed by engine |
| **SentimentEvent** | ✅ (via analysis) | ✅ GET history | ❌ | ❌ | ❌ | Created by analysis pipeline |
| **ModelUsage** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ | Append-only |
| **SecurityEvent** | ✅ POST | ✅ GET (paginated) | ❌ | ❌ | ❌ | Append-only |
| **HeartbeatLog** | ✅ POST | ✅ GET | ❌ | ❌ | ❌ | Append-only |
| **PerformanceLog** | ✅ POST | ✅ GET | ❌ | ❌ | ❌ | Append-only |
| **PendingComplexTask** | ✅ POST | ✅ GET | ❌ | ✅ PATCH | ❌ | No single-read, no delete |
| **RateLimit** | ✅ (via increment) | ✅ GET | ❌ | ❌ | ❌ | Upsert via check/increment |
| **ApiKeyRotation** | ✅ POST | ✅ GET | ❌ | ❌ | ❌ | Append-only |
| **ScheduledJob** | ❌ (via sync) | ✅ GET | ✅ GET by ID | ❌ | ❌ | DB is sync target |
| **EngineChatSession** | ✅ POST | ✅ GET | ✅ GET detail | ❌ | ✅ DELETE (end) | Via engine router |
| **EngineChatMessage** | ✅ POST (send) | ✅ GET (in session) | ❌ | ❌ | ❌ | Created via send_message |
| **EngineCronJob** | ✅ POST | ✅ GET | ✅ GET by ID | ✅ PUT | ✅ DELETE | Full CRUD via scheduler |

---

## 5. Real Workflow Chains

### Chain 1: Interactive Chat Session (E2E)
```
POST /engine/chat/sessions            → creates session {id}
  ↓
POST /engine/chat/sessions/{id}/messages {content: "Hello"}
  ↓                                    → returns AI response
POST /engine/chat/sessions/{id}/messages {content: "Tell me about goals"}
  ↓
GET  /engine/chat/sessions/{id}        → full session with all messages
  ↓
GET  /engine/chat/sessions/{id}/export?format=markdown
  ↓                                    → downloadable .md file
DELETE /engine/chat/sessions/{id}      → ends session
```

### Chain 2: Goal Lifecycle (Kanban)
```
POST /goals {title: "Deploy v3", goal_id: "deploy-v3", priority: 1}
  ↓                                    → {id, goal_id, created}
PATCH /goals/deploy-v3 {status: "active"}
  ↓                                    → auto-sets board_column="doing"
PATCH /goals/deploy-v3/move {board_column: "doing", position: 0}
  ↓
GET  /goals/board?sprint=current       → Kanban columns
  ↓
PATCH /goals/deploy-v3 {status: "completed", progress: 100}
  ↓                                    → auto-sets completed_at, board_column="done"
GET  /goals/sprint-summary             → status counts summary
GET  /goals/archive                    → completed goals (archived after 24h)
```

### Chain 3: Knowledge Graph Build + Query
```
POST /knowledge-graph/entities {name: "sentiment_analysis", type: "skill"}
  ↓                                    → {id: entity_a}
POST /knowledge-graph/entities {name: "detect_emotion", type: "tool"}
  ↓                                    → {id: entity_b}
POST /knowledge-graph/relations {from_entity: entity_a, to_entity: entity_b, relation_type: "provides"}
  ↓
GET  /knowledge-graph/search?q=emotion → finds entities by ILIKE
GET  /knowledge-graph/skill-for-task?task=emotion → skill discovery
GET  /knowledge-graph/traverse?start=entity_a&max_depth=2
  ↓
GET  /knowledge-graph/query-log        → audit trail
```

### Chain 4: Memory Pipeline (KV → Semantic → Search)
```
POST /memories {key: "user_preference_theme", value: {"theme": "dark"}, category: "preferences"}
  ↓                                    → stores KV memory
POST /memories/semantic {content: "User prefers dark theme with blue accents", category: "preferences", importance: 0.8}
  ↓                                    → generates embedding, stores
GET  /memories/search?query=color+preferences&limit=5
  ↓                                    → pgvector cosine similarity
POST /memories/summarize-session {hours_back: 24}
  ↓                                    → LLM summarizes activities → episodic memory
GET  /memories/semantic?category=episodic → list episodic memories
```

### Chain 5: Working Memory Lifecycle
```
POST /working-memory {key: "current_task", value: {"task": "deploy"}, category: "context", importance: 0.9, ttl_hours: 4}
  ↓
POST /working-memory {key: "user_mood", value: {"mood": "focused"}, category: "context", importance: 0.6}
  ↓
GET  /working-memory/context?limit=10&weight_importance=0.5
  ↓                                    → weighted retrieval with relevance scores
POST /working-memory/checkpoint         → snapshot
  ↓
GET  /working-memory/checkpoint         → retrieve snapshot
GET  /working-memory/stats              → aggregate stats
POST /working-memory/cleanup {delete_expired: true}
```

### Chain 6: Skill Observability Pipeline
```
POST /skills/invocations {skill_name: "brainstorm", tool_name: "generate_ideas", success: true, duration_ms: 1200, tokens_used: 500}
  ↓
POST /skills/invocations {skill_name: "brainstorm", tool_name: "generate_ideas", success: false, error_type: "TimeoutError", duration_ms: 30000}
  ↓
GET  /skills/stats?hours=24            → per-skill aggregation
GET  /skills/health/dashboard?hours=24  → health scores + recurring patterns
GET  /skills/insights?hours=24          → full dashboard payload with timeline
  ↓
POST /lessons {error_pattern: "brainstorm_timeout", error_type: "timeout", resolution: "Reduce max_tokens to 2000"}
GET  /lessons/check?error_type=timeout  → known resolution lookup
```

### Chain 7: Operations: Task → Activity → Social
```
POST /tasks {task_type: "deployment", description: "Deploy v3 to prod", agent_type: "coder", priority: "high"}
  ↓
POST /activities {action: "deployment_started", skill: "ci_cd", details: {"version": "3.0"}}
  ↓                                    → auto-mirrors to social feed if commit/comment
PATCH /tasks/{task_id} {status: "completed", result: "Deployed successfully"}
  ↓
POST /activities {action: "commit", skill: "ci_cd", details: {"message": "Release v3.0"}}
  ↓                                    → auto-creates SocialPost (platform="activity")
GET  /social?platform=activity          → see activity-mirrored posts
```

### Chain 8: Self-Improvement Loop (Proposals)
```
POST /proposals {title: "Optimize brainstorm timeout", description: "Reduce default timeout from 30s to 15s", category: "performance", risk_level: "low", file_path: "aria_skills/brainstorm/skill.json", rationale: "3x timeout errors in 24h"}
  ↓
GET  /proposals?status=proposed         → review queue
GET  /proposals/{id}                    → full proposal detail
PATCH /proposals/{id} {status: "approved", reviewed_by: "najia"}
  ↓
PATCH /proposals/{id} {status: "implemented"}
```

### Chain 9: Cron Job Management
```
POST /engine/cron {name: "Hourly health check", schedule: "0 * * * *", payload_type: "skill", payload: "health.check_all", agent_id: "main"}
  ↓
GET  /engine/cron                       → list with scheduler_running
GET  /engine/cron/status                → active executions
POST /engine/cron/{job_id}/trigger      → manual run
GET  /engine/cron/{job_id}/history      → execution log
PUT  /engine/cron/{job_id} {enabled: false} → disable
DELETE /engine/cron/{job_id}            → remove
```

### Chain 10: Security Event Flow
```
POST /security-events {threat_level: "HIGH", threat_type: "injection", threat_patterns: ["DROP TABLE"], input_preview: "'; DROP TABLE users;--", blocked: true}
  ↓
GET  /security-events?threat_level=HIGH&blocked_only=true
GET  /security-events/stats             → {total, blocked, last_24h, by_level, by_type}
```

---

## 6. NOT NULL / Required Fields Analysis

### Fields that are NOT NULL in DB but could be missed in test payloads:

| Table | Column | NOT NULL | Has Server Default | Risk |
|-------|--------|----------|-------------------|------|
| **memories** | `key` | ✅ | ❌ | ⚠️ **HIGH** — POST /memories MUST include `key` |
| **memories** | `value` | ✅ | ❌ | ⚠️ **HIGH** — POST /memories MUST include `value` |
| **thoughts** | `content` | ✅ | ❌ | ⚠️ **HIGH** — POST /thoughts MUST include `content` |
| **goals** | `goal_id` | ✅ | ❌ | ✅ Low — auto-generated if missing |
| **goals** | `title` | ✅ | ❌ | ⚠️ **HIGH** — POST /goals MUST include `title` |
| **activity_log** | `action` | ✅ | ❌ | ⚠️ **HIGH** — POST /activities MUST include `action` |
| **social_posts** | `content` | ✅ | ❌ | ⚠️ **HIGH** — POST /social MUST include `content` |
| **hourly_goals** | `hour_slot` | ✅ | ❌ | ⚠️ **HIGH** — POST /hourly-goals MUST include `hour_slot` |
| **hourly_goals** | `goal_type` | ✅ | ❌ | ⚠️ **HIGH** — POST /hourly-goals MUST include `goal_type` |
| **hourly_goals** | `description` | ✅ | ❌ | ⚠️ **HIGH** — POST /hourly-goals MUST include `description` |
| **knowledge_entities** | `name` | ✅ | ❌ | ✅ Validated by Pydantic |
| **knowledge_entities** | `type` | ✅ | ❌ | ✅ Validated by Pydantic |
| **knowledge_relations** | `from_entity` | ✅ | ❌ | ✅ Validated by Pydantic |
| **knowledge_relations** | `to_entity` | ✅ | ❌ | ✅ Validated by Pydantic |
| **knowledge_relations** | `relation_type` | ✅ | ❌ | ✅ Validated by Pydantic |
| **pending_complex_tasks** | `task_id` | ✅ | ❌ | ✅ Low — auto-generated |
| **pending_complex_tasks** | `task_type` | ✅ | ❌ | ⚠️ **HIGH** — POST /tasks MUST include `task_type` |
| **pending_complex_tasks** | `description` | ✅ | ❌ | ⚠️ **HIGH** — POST /tasks MUST include `description` |
| **pending_complex_tasks** | `agent_type` | ✅ | ❌ | ⚠️ **HIGH** — POST /tasks MUST include `agent_type` |
| **performance_log** | `review_period` | ✅ | ❌ | ⚠️ **HIGH** — POST /performance MUST include `review_period` |
| **heartbeat_log** | `beat_number` | ✅ | ❌ | ✅ Low — defaults to 0 in handler |
| **security_events** | `threat_level` | ✅ | ❌ | ✅ Low — defaults to "LOW" in handler |
| **security_events** | `threat_type` | ✅ | ❌ | ✅ Low — defaults to "unknown" in handler |
| **model_usage** | `model` | ✅ | ❌ | ⚠️ **HIGH** — POST /model-usage MUST include `model` |
| **working_memory** | `category` | ✅ | ❌ | ✅ Low — defaults to "general" in handler |
| **working_memory** | `key` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **working_memory** | `value` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **semantic_memories** | `content` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **semantic_memories** | `embedding` | ✅ | ❌ | ⚠️ Auto-generated via LiteLLM |
| **skill_status** | `skill_name` | ✅ | ❌ | ✅ Managed by seed endpoint |
| **skill_status** | `canonical_name` | ✅ | ❌ | ✅ Managed by seed endpoint |
| **skill_status** | `status` | ✅ | `'unavailable'` | ✅ Has default |
| **skill_invocations** | `skill_name` | ✅ | ❌ | ✅ Low — defaults to "unknown" in handler |
| **skill_invocations** | `tool_name` | ✅ | ❌ | ✅ Low — defaults to "unknown" in handler |
| **lessons_learned** | `error_pattern` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **lessons_learned** | `error_type` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **lessons_learned** | `resolution` | ✅ | ❌ | ✅ Low — defaults to placeholder in handler |
| **improvement_proposals** | `title` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **improvement_proposals** | `description` | ✅ | ❌ | ⚠️ Validated in handler (400 if missing) |
| **agent_sessions** | `agent_id` | ✅ | ❌ | ✅ Low — defaults to "main" in handler |
| **session_messages** | `role` | ✅ | ❌ | N/A — engine-managed |
| **session_messages** | `content` | ✅ | ❌ | N/A — engine-managed |
| **session_messages** | `content_hash` | ✅ | ❌ | N/A — engine-managed |
| **engine_chat_sessions** | `agent_id` | ✅ | `'main'` | ✅ Has default |
| **engine_chat_sessions** | `session_type` | ✅ | `'interactive'` | ✅ Has default |
| **engine_chat_sessions** | `status` | ✅ | `'active'` | ✅ Has default |
| **engine_chat_messages** | `session_id` | ✅ | ❌ | N/A — engine-managed |
| **engine_chat_messages** | `role` | ✅ | ❌ | N/A — engine-managed |
| **engine_chat_messages** | `content` | ✅ | ❌ | N/A — engine-managed |
| **engine_cron_jobs** | `name` | ✅ | ❌ | ✅ Validated by Pydantic |
| **engine_cron_jobs** | `schedule` | ✅ | ❌ | ✅ Validated by Pydantic |
| **engine_cron_jobs** | `payload` | ✅ | ❌ | ✅ Validated by Pydantic |
| **engine_agent_state** | `model` | ✅ | ❌ | N/A — managed by engine |

### Minimum Required Payloads for Testing

```json
// POST /goals — minimum
{"title": "My Goal"}

// POST /thoughts — minimum 
{"content": "A thought"}

// POST /memories — minimum
{"key": "some-key", "value": {"data": 1}}

// POST /activities — minimum
{"action": "test_action"}

// POST /social — minimum
{"content": "A post"}

// POST /hourly-goals — minimum
{"hour_slot": 10, "goal_type": "coding", "description": "Write tests"}

// POST /tasks — minimum
{"task_type": "coding", "description": "Fix bugs", "agent_type": "coder"}

// POST /performance — minimum
{"review_period": "2026-02"}

// POST /heartbeat — minimum
{"beat_number": 1}

// POST /model-usage — minimum
{"model": "gpt-4"}

// POST /security-events — minimum
{"threat_level": "LOW", "threat_type": "scan"}

// POST /working-memory — minimum
{"key": "ctx", "value": {"data": 1}}

// POST /memories/semantic — minimum (needs LiteLLM)
{"content": "Important fact about the system"}

// POST /lessons — minimum
{"error_pattern": "timeout_pattern", "error_type": "timeout", "resolution": "retry with backoff"}

// POST /proposals — minimum
{"title": "Improve X", "description": "Description of improvement"}

// POST /skills/invocations — minimum
{"skill_name": "test_skill", "tool_name": "test_tool"}

// POST /knowledge-graph/entities — minimum (Pydantic validated)
{"name": "entity_name", "type": "concept"}

// POST /knowledge-graph/relations — minimum (Pydantic validated)
{"from_entity": "uuid", "to_entity": "uuid", "relation_type": "related_to"}

// POST /engine/chat/sessions — minimum
{}  // all fields have defaults

// POST /engine/chat/sessions/{id}/messages — minimum
{"content": "Hello"}

// POST /engine/cron — minimum
{"name": "Test Job", "schedule": "*/5 * * * *", "payload": "test prompt"}
```

### Noise Filters (may silently skip valid test data)

**WARNING:** Multiple routers include noise/test detection that **silently returns `{created: false, skipped: true}`** instead of a 400 error. This can cause test assertions to fail silently:

| Router | Filter Function | Skipped Markers |
|--------|----------------|-----------------|
| Goals | `_is_noisy_goal_payload()` | "test goal", "test-*", "goal-test-*", "abc123", etc. |
| Knowledge | `_is_test_kg_payload()` | "[test]", "pytest", "test-*", "testentity_*", "rel_a_*", etc. |
| Memories | `_is_noise_memory_payload()` | "test-*", source="pytest", key starts with "test-", etc. |
| Social | `_is_test_social_payload()` | "live test", "test post", "moltbook test", metadata.test=true |

**Impact on testing:** Test payloads must avoid these markers OR tests must account for the `{skipped: true}` response.

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total routers | 26 (+ 1 WebSocket) |
| Total REST endpoints | ~130 |
| DB tables (ORM models) | 35 |
| Tables with full CRUD | 5 (Goal, WorkingMemory, EngineChatSession, EngineCronJob, AgentSession) |
| Tables that are append-only | 12 (ActivityLog, Thought, HeartbeatLog, PerformanceLog, SecurityEvent, ModelUsage, SkillInvocation, ApiKeyRotation, SentimentEvent, KnowledgeQueryLog, SessionMessage, EngineChatMessage) |
| Foreign key relationships | 10 |
| Unique constraints | 8 |
| Endpoints with Pydantic validation | ~20 (engine_chat, engine_cron, knowledge, engine_sessions, engine_agents, engine_agent_metrics) |
| Endpoints using raw `request.json()` | ~30 (legacy pattern in most routers) |
