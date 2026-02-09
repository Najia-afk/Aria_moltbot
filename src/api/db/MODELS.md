# Aria Brain ORM Models Reference

> Auto-documented from `src/api/db/models.py` — 18 ORM models  
> Canonical source of truth for the `aria_warehouse` PostgreSQL database  
> Driver: psycopg 3 via SQLAlchemy 2.0 async

---

## Table of Contents

1. [Core Domain](#core-domain)
2. [Social / Community](#social--community)
3. [Scheduling / Operations](#scheduling--operations)
4. [Knowledge Graph](#knowledge-graph)
5. [Performance / Review](#performance--review)
6. [Heartbeat](#heartbeat)
7. [OpenClaw Scheduling](#openclaw-scheduling)
8. [Security](#security)
9. [Schedule Tick](#schedule-tick)
10. [Operations: Sessions / Usage](#operations-sessions--usage)
11. [Cross-Reference: ORM vs Init SQL](#cross-reference-orm-vs-init-sql)

---

## Core Domain

### 1. Memory

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `key` | `key` | `String(255)` | UNIQUE, NOT NULL |
| `value` | `value` | `JSONB` | NOT NULL |
| `category` | `category` | `String(100)` | default `'general'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |
| `updated_at` | `updated_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `memories`  
**Indexes:** `idx_memories_key`, `idx_memories_category`, `idx_memories_updated` (DESC)

---

### 2. Thought

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `content` | `content` | `Text` | NOT NULL |
| `category` | `category` | `String(100)` | default `'general'` |
| `metadata_json` | `metadata` | `JSONB` | default `'{}'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `thoughts`  
**Indexes:** `idx_thoughts_category`, `idx_thoughts_created` (DESC)

---

### 3. Goal

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `goal_id` | `goal_id` | `String(100)` | UNIQUE, NOT NULL |
| `title` | `title` | `String(255)` | NOT NULL |
| `description` | `description` | `Text` | nullable |
| `status` | `status` | `String(50)` | default `'pending'` |
| `priority` | `priority` | `Integer` | default `2` |
| `progress` | `progress` | `Numeric(5,2)` | default `0` |
| `due_date` | `due_date` | `DateTime(tz)` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |
| `completed_at` | `completed_at` | `DateTime(tz)` | nullable |

**Table:** `goals`  
**Indexes:** `idx_goals_status`, `idx_goals_priority` (DESC)  
**⚠ DRIFT:** SQL schema includes `parent_goal_id UUID` (FK→goals.id) and `metadata JSONB` — both missing from ORM

---

### 4. ActivityLog

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `action` | `action` | `String(100)` | NOT NULL |
| `skill` | `skill` | `String(100)` | nullable |
| `details` | `details` | `JSONB` | default `'{}'` |
| `success` | `success` | `Boolean` | default `true` |
| `error_message` | `error_message` | `Text` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `activity_log`  
**Indexes:** `idx_activity_action`, `idx_activity_skill`, `idx_activity_created` (DESC)

---

## Social / Community

### 5. SocialPost

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `platform` | `platform` | `String(50)` | default `'moltbook'` |
| `post_id` | `post_id` | `String(100)` | nullable |
| `content` | `content` | `Text` | NOT NULL |
| `visibility` | `visibility` | `String(50)` | default `'public'` |
| `reply_to` | `reply_to` | `String(100)` | nullable |
| `url` | `url` | `Text` | nullable |
| `posted_at` | `posted_at` | `DateTime(tz)` | default `NOW()` |
| `metadata_json` | `metadata` | `JSONB` | default `'{}'` |

**Table:** `social_posts`  
**Indexes:** `idx_posts_platform`, `idx_posts_posted` (DESC)

---

## Scheduling / Operations

### 6. HourlyGoal

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `Integer` | PK, autoincrement |
| `hour_slot` | `hour_slot` | `Integer` | NOT NULL |
| `goal_type` | `goal_type` | `String(50)` | NOT NULL |
| `description` | `description` | `Text` | NOT NULL |
| `status` | `status` | `String(20)` | default `'pending'` |
| `completed_at` | `completed_at` | `DateTime(tz)` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `hourly_goals`  
**Indexes:** none  
**⚠ DRIFT:** Table exists only in ORM — no corresponding SQL init script

---

## Knowledge Graph

### 7. KnowledgeEntity

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `name` | `name` | `Text` | NOT NULL |
| `type` | `type` | `Text` | NOT NULL |
| `properties` | `properties` | `JSONB` | default `'{}'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |
| `updated_at` | `updated_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `knowledge_entities`  
**Indexes:** `idx_kg_entity_name`  
**⚠ DRIFT:** SQL column is `entity_type VARCHAR(100)` — ORM maps to `type` as `Text`. Column name + type mismatch.  
**⚠ DRIFT:** SQL uses `VARCHAR(255)` for `name` — ORM uses `Text`

---

### 8. KnowledgeRelation

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `from_entity` | `from_entity` | `UUID` | NOT NULL |
| `to_entity` | `to_entity` | `UUID` | NOT NULL |
| `relation_type` | `relation_type` | `Text` | NOT NULL |
| `properties` | `properties` | `JSONB` | default `'{}'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `knowledge_relations`  
**Indexes:** `idx_kg_relation_from`, `idx_kg_relation_to`  
**⚠ DRIFT:** SQL columns are `from_entity_id` / `to_entity_id` with FK→knowledge_entities(id) ON DELETE CASCADE — ORM uses `from_entity` / `to_entity` (no FK). Column name mismatch.  
**⚠ DRIFT:** SQL uses `VARCHAR(100)` for `relation_type` — ORM uses `Text`

---

## Performance / Review

### 9. PerformanceLog

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `Integer` | PK, autoincrement |
| `review_period` | `review_period` | `String(20)` | NOT NULL |
| `successes` | `successes` | `Text` | nullable |
| `failures` | `failures` | `Text` | nullable |
| `improvements` | `improvements` | `Text` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `performance_log`  
**Indexes:** none  
**⚠ DRIFT:** Table exists only in ORM — no corresponding SQL init script

---

### 10. PendingComplexTask

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `Integer` | PK, autoincrement |
| `task_id` | `task_id` | `String(50)` | UNIQUE, NOT NULL |
| `task_type` | `task_type` | `String(50)` | NOT NULL |
| `description` | `description` | `Text` | NOT NULL |
| `agent_type` | `agent_type` | `String(50)` | NOT NULL |
| `priority` | `priority` | `String(20)` | default `'medium'` |
| `status` | `status` | `String(20)` | default `'pending'` |
| `result` | `result` | `Text` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |
| `completed_at` | `completed_at` | `DateTime(tz)` | nullable |

**Table:** `pending_complex_tasks`  
**Indexes:** none  
**⚠ DRIFT:** Table exists only in ORM — no corresponding SQL init script

---

## Heartbeat

### 11. HeartbeatLog

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `beat_number` | `beat_number` | `Integer` | NOT NULL |
| `status` | `status` | `String(50)` | default `'healthy'` |
| `details` | `details` | `JSONB` | default `'{}'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `heartbeat_log`  
**Indexes:** `idx_heartbeat_created` (DESC)

---

## OpenClaw Scheduling

### 12. ScheduledJob

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `String(50)` | PK |
| `agent_id` | `agent_id` | `String(50)` | default `'main'` |
| `name` | `name` | `String(100)` | NOT NULL |
| `enabled` | `enabled` | `Boolean` | default `true` |
| `schedule_kind` | `schedule_kind` | `String(20)` | default `'cron'` |
| `schedule_expr` | `schedule_expr` | `String(50)` | NOT NULL |
| `session_target` | `session_target` | `String(50)` | nullable |
| `wake_mode` | `wake_mode` | `String(50)` | nullable |
| `payload_kind` | `payload_kind` | `String(50)` | nullable |
| `payload_text` | `payload_text` | `Text` | nullable |
| `next_run_at` | `next_run_at` | `DateTime(tz)` | nullable |
| `last_run_at` | `last_run_at` | `DateTime(tz)` | nullable |
| `last_status` | `last_status` | `String(20)` | nullable |
| `last_duration_ms` | `last_duration_ms` | `Integer` | nullable |
| `run_count` | `run_count` | `Integer` | default `0` |
| `success_count` | `success_count` | `Integer` | default `0` |
| `fail_count` | `fail_count` | `Integer` | default `0` |
| `created_at_ms` | `created_at_ms` | `Integer` | nullable |
| `updated_at_ms` | `updated_at_ms` | `Integer` | nullable |
| `synced_at` | `synced_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `scheduled_jobs`  
**Indexes:** `idx_jobs_name`, `idx_jobs_enabled`, `idx_jobs_next_run`  
**⚠ DRIFT:** Table exists only in ORM — no corresponding SQL init script

---

## Security

### 13. SecurityEvent

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `threat_level` | `threat_level` | `String(20)` | NOT NULL |
| `threat_type` | `threat_type` | `String(100)` | NOT NULL |
| `threat_patterns` | `threat_patterns` | `JSONB` | default `'[]'` |
| `input_preview` | `input_preview` | `Text` | nullable |
| `source` | `source` | `String(100)` | nullable |
| `user_id` | `user_id` | `String(100)` | nullable |
| `blocked` | `blocked` | `Boolean` | default `false` |
| `details` | `details` | `JSONB` | default `'{}'` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `security_events`  
**Indexes:** `idx_security_threat_level`, `idx_security_threat_type`, `idx_security_created` (DESC), `idx_security_blocked`  
**⚠ DRIFT:** SQL has `resolved BOOLEAN DEFAULT false` and `resolved_at TIMESTAMP WITH TIME ZONE` — both missing from ORM  
**⚠ DRIFT:** SQL has `idx_security_resolved` index — ORM has `idx_security_blocked` (different index names / logic)  
**⚠ DRIFT:** ORM has `threat_patterns`, `input_preview`, `user_id`, `blocked` columns not in original migration 6 SQL (added later in 01-schema.sql)

---

## Schedule Tick

### 14. ScheduleTick

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `Integer` | PK |
| `last_tick` | `last_tick` | `DateTime(tz)` | nullable |
| `tick_count` | `tick_count` | `Integer` | default `0` |
| `heartbeat_interval` | `heartbeat_interval` | `Integer` | default `3600` |
| `enabled` | `enabled` | `Boolean` | default `true` |
| `jobs_total` | `jobs_total` | `Integer` | default `0` |
| `jobs_successful` | `jobs_successful` | `Integer` | default `0` |
| `jobs_failed` | `jobs_failed` | `Integer` | default `0` |
| `last_job_name` | `last_job_name` | `String(255)` | nullable |
| `last_job_status` | `last_job_status` | `String(50)` | nullable |
| `next_job_at` | `next_job_at` | `DateTime(tz)` | nullable |
| `updated_at` | `updated_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `schedule_tick`  
**Indexes:** none  
**⚠ DRIFT:** Table exists only in ORM — no corresponding SQL init script

---

## Operations: Sessions / Usage

### 15. AgentSession

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `agent_id` | `agent_id` | `String(100)` | NOT NULL |
| `session_type` | `session_type` | `String(50)` | default `'interactive'` |
| `started_at` | `started_at` | `DateTime(tz)` | default `NOW()` |
| `ended_at` | `ended_at` | `DateTime(tz)` | nullable |
| `messages_count` | `messages_count` | `Integer` | default `0` |
| `tokens_used` | `tokens_used` | `Integer` | default `0` |
| `cost_usd` | `cost_usd` | `Numeric(10,6)` | default `0` |
| `status` | `status` | `String(50)` | default `'active'` |
| `metadata_json` | `metadata` | `JSONB` | default `'{}'` |

**Table:** `agent_sessions`  
**Indexes:** `idx_agent_sessions_agent`, `idx_agent_sessions_started` (DESC), `idx_agent_sessions_status`

---

### 16. ModelUsage

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `model` | `model` | `String(100)` | NOT NULL |
| `provider` | `provider` | `String(50)` | nullable |
| `input_tokens` | `input_tokens` | `Integer` | default `0` |
| `output_tokens` | `output_tokens` | `Integer` | default `0` |
| `cost_usd` | `cost_usd` | `Numeric(10,6)` | default `0` |
| `latency_ms` | `latency_ms` | `Integer` | nullable |
| `success` | `success` | `Boolean` | default `true` |
| `error_message` | `error_message` | `Text` | nullable |
| `session_id` | `session_id` | `UUID` | nullable |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `model_usage`  
**Indexes:** `idx_model_usage_model`, `idx_model_usage_created` (DESC), `idx_model_usage_session`  
**⚠ DRIFT:** SQL has `session_id UUID REFERENCES agent_sessions(id)` FK — ORM column has no `ForeignKey`

---

### 17. RateLimit

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `skill` | `skill` | `String(100)` | UNIQUE, NOT NULL |
| `last_action` | `last_action` | `DateTime(tz)` | nullable |
| `action_count` | `action_count` | `Integer` | default `0` |
| `window_start` | `window_start` | `DateTime(tz)` | default `NOW()` |
| `created_at` | `created_at` | `DateTime(tz)` | default `NOW()` |
| `last_post` | `last_post` | `DateTime(tz)` | nullable |
| `updated_at` | `updated_at` | `DateTime(tz)` | default `NOW()` |

**Table:** `rate_limits`  
**Indexes:** `idx_rate_limits_skill`

---

### 18. ApiKeyRotation

| Property | DB Column | Type | Constraints |
|----------|-----------|------|-------------|
| `id` | `id` | `UUID` | PK, default `uuid_generate_v4()` |
| `service` | `service` | `String(100)` | NOT NULL |
| `rotated_at` | `rotated_at` | `DateTime(tz)` | default `NOW()` |
| `reason` | `reason` | `Text` | nullable |
| `rotated_by` | `rotated_by` | `String(100)` | default `'system'` |
| `metadata_json` | `metadata` | `JSONB` | default `'{}'` |

**Table:** `api_key_rotations`  
**Indexes:** none in ORM  
**⚠ DRIFT:** SQL has `reason VARCHAR(255)` — ORM uses `Text`. SQL has indexes `idx_api_rotation_service`, `idx_api_rotation_rotated` — ORM has none.

---

## Cross-Reference: ORM vs Init SQL

### Tables in SQL but NOT in ORM

| SQL Table | Status | Notes |
|-----------|--------|-------|
| `schema_migrations` | Expected gap | Migration tracking — managed by init scripts, not ORM |
| `key_value_memory` | **MISSING from ORM** | Has `key`, `value`, `category`, `ttl_seconds`, `expires_at`, `created_at`, `updated_at` |

### Tables in ORM but NOT in SQL init scripts

| ORM Model | Table | Status |
|-----------|-------|--------|
| `HourlyGoal` | `hourly_goals` | **No SQL init script** — created by `ensure_schema()` only |
| `PerformanceLog` | `performance_log` | **No SQL init script** — created by `ensure_schema()` only |
| `PendingComplexTask` | `pending_complex_tasks` | **No SQL init script** — created by `ensure_schema()` only |
| `ScheduledJob` | `scheduled_jobs` | **No SQL init script** — created by `ensure_schema()` only |
| `ScheduleTick` | `schedule_tick` | **No SQL init script** — created by `ensure_schema()` only |

### Column-Level Drift

| Table | Issue | Severity |
|-------|-------|----------|
| `goals` | Missing `parent_goal_id` (FK) and `metadata` (JSONB) in ORM | **HIGH** |
| `security_events` | Missing `resolved` and `resolved_at` in ORM | **MEDIUM** |
| `knowledge_entities` | Column `entity_type` (SQL) vs `type` (ORM) — name mismatch | **HIGH** |
| `knowledge_entities` | `VARCHAR(255)` (SQL) vs `Text` (ORM) for `name` | LOW |
| `knowledge_relations` | Columns `from_entity_id`/`to_entity_id` (SQL) vs `from_entity`/`to_entity` (ORM) — name mismatch | **HIGH** |
| `knowledge_relations` | Missing FK constraints to `knowledge_entities(id)` and `ON DELETE CASCADE` in ORM | **MEDIUM** |
| `model_usage` | Missing FK `session_id → agent_sessions(id)` in ORM | LOW |
| `api_key_rotations` | `VARCHAR(255)` (SQL) vs `Text` (ORM) for `reason`; missing indexes | LOW |

### Extra SQL Indexes Not in ORM

- `idx_thoughts_created_category` (composite)
- `idx_goals_parent` 
- `idx_goals_status_priority` (composite)
- `idx_activity_created_action` (composite)
- `idx_kg_entities_type`
- `idx_kg_relations_type`
- `idx_security_resolved`
- `idx_api_rotation_service`
- `idx_api_rotation_rotated`
