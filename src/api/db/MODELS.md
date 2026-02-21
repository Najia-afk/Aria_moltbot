# Aria Brain ORM Models Reference

> Auto-documented from `src/api/db/models.py` — **37 ORM models**  
> Canonical source of truth for the `aria_warehouse` PostgreSQL database  
> Driver: psycopg 3 via SQLAlchemy 2.0 async  
> **Schemas:** `aria_data` (26 domain tables) · `aria_engine` (11 infrastructure tables)  
> **Zero raw SQL** — all queries use ORM. Only `SELECT 1` health probes remain.

---

## Table of Contents

1. [Schema: aria_data (26 models)](#schema-aria_data-26-models)
2. [Schema: aria_engine (11 models)](#schema-aria_engine-11-models)
3. [ForeignKey Summary](#foreignkey-summary)
4. [Schema Bootstrap](#schema-bootstrap)

---

## Schema: `aria_data` (26 models)

All domain/business data. `__table_args__ = {"schema": "aria_data"}` on every model.

| # | Model | Table | Key Columns |
|---|-------|-------|-------------|
| 1 | `Memory` | `memories` | key (unique), value (JSONB), category |
| 2 | `Thought` | `thoughts` | content, category, metadata_json |
| 3 | `Goal` | `goals` | goal_id (unique), title, status, priority, progress, sprint, board_column, tags |
| 4 | `ActivityLog` | `activity_log` | action, skill, details (JSONB), success |
| 5 | `SocialPost` | `social_posts` | platform, post_id (unique), content, visibility, reply_to → self FK |
| 6 | `HourlyGoal` | `hourly_goals` | hour_slot, goal_type, description, status |
| 7 | `KnowledgeEntity` | `knowledge_entities` | name, type, properties (JSONB) |
| 8 | `KnowledgeRelation` | `knowledge_relations` | from_entity → KnowledgeEntity FK, to_entity → FK, relation_type |
| 9 | `SkillGraphEntity` | `skill_graph_entities` | name, type, properties (JSONB), UNIQUE(name, type) |
| 10 | `SkillGraphRelation` | `skill_graph_relations` | from_entity → SkillGraphEntity FK, to_entity → FK, relation_type |
| 11 | `KnowledgeQueryLog` | `knowledge_query_log` | query_type, params (JSONB), result_count, tokens_saved |
| 12 | `PerformanceLog` | `performance_log` | review_period, successes, failures, improvements |
| 13 | `PendingComplexTask` | `pending_complex_tasks` | task_id (unique), task_type, agent_type, status |
| 14 | `HeartbeatLog` | `heartbeat_log` | beat_number, status, details (JSONB) |
| 15 | `AgentSession` | `agent_sessions` | agent_id, session_type, messages_count, tokens_used, cost_usd |
| 16 | `SessionMessage` | `session_messages` | session_id → AgentSession FK, role, content, content_hash, UNIQUE(ext_id, role, hash) |
| 17 | `SentimentEvent` | `sentiment_events` | message_id → SessionMessage FK, session_id → AgentSession FK, valence, arousal, dominance |
| 18 | `ModelUsage` | `model_usage` | model, provider, input_tokens, output_tokens, cost_usd, session_id → AgentSession FK |
| 19 | `SecurityEvent` | `security_events` | threat_level, threat_type, threat_patterns (JSONB), blocked |
| 20 | `AgentPerformance` | `agent_performance` | agent_id, task_type, success, duration_ms, pheromone_score |
| 21 | `WorkingMemory` | `working_memory` | category, key, value (JSONB), importance, ttl_hours, UNIQUE(category, key) |
| 22 | `SkillStatusRecord` | `skill_status` | skill_name (unique), canonical_name, layer, status, use_count, error_count |
| 23 | `SemanticMemory` | `semantic_memories` | content, embedding (Vector(768)/JSONB), category, importance |
| 24 | `LessonLearned` | `lessons_learned` | error_pattern (unique), error_type, resolution, occurrences, effectiveness |
| 25 | `ImprovementProposal` | `improvement_proposals` | title, category, risk_level, file_path, current_code, proposed_code, status |
| 26 | `SkillInvocation` | `skill_invocations` | skill_name, tool_name, duration_ms, success, model_used |

---

## Schema: `aria_engine` (11 models)

All engine infrastructure data. `__table_args__ = {"schema": "aria_engine"}` on every model.

| # | Model | Table | Key Columns |
|---|-------|-------|-------------|
| 1 | `ScheduledJob` | `scheduled_jobs` | id (PK string), name, schedule_kind, schedule_expr, enabled, run/success/fail counts |
| 2 | `ScheduleTick` | `schedule_tick` | last_tick, tick_count, heartbeat_interval, jobs_total/successful/failed |
| 3 | `RateLimit` | `rate_limits` | skill (unique), action_count, window_start |
| 4 | `ApiKeyRotation` | `api_key_rotations` | service, rotated_at, reason, rotated_by |
| 5 | `EngineChatSession` | `chat_sessions` | agent_id, title, model, temperature, status, message_count, total_cost |
| 6 | `EngineChatMessage` | `chat_messages` | session_id → EngineChatSession FK (CASCADE), role, content, thinking, tool_calls, embedding (Vector(1536)/JSONB) |
| 7 | `EngineCronJob` | `cron_jobs` | name, schedule, agent_id, enabled, payload, session_mode, run/success/fail counts |
| 8 | `EngineAgentState` | `agent_state` | agent_id (PK), model, status, enabled, skills (JSONB), pheromone_score, capabilities |
| 9 | `EngineConfigEntry` | `config` | key (PK), value (JSONB), description — *currently unused* |
| 10 | `EngineAgentTool` | `agent_tools` | agent_id, skill_name, function_name, parameters (JSONB) — *currently unused* |
| 11 | `LlmModelEntry` | `llm_models` | id (PK), name, provider, tier, reasoning, vision, tool_calling, context_window, cost_input/output, litellm_model |

---

## ForeignKey Summary

All ForeignKeys use schema-qualified references.

| Model | Column | References | On Delete |
|-------|--------|------------|-----------|
| `SocialPost` | `reply_to` | `aria_data.social_posts.post_id` | SET NULL |
| `KnowledgeRelation` | `from_entity` | `aria_data.knowledge_entities.id` | CASCADE |
| `KnowledgeRelation` | `to_entity` | `aria_data.knowledge_entities.id` | CASCADE |
| `SkillGraphRelation` | `from_entity` | `aria_data.skill_graph_entities.id` | CASCADE |
| `SkillGraphRelation` | `to_entity` | `aria_data.skill_graph_entities.id` | CASCADE |
| `SessionMessage` | `session_id` | `aria_data.agent_sessions.id` | SET NULL |
| `SentimentEvent` | `message_id` | `aria_data.session_messages.id` | CASCADE |
| `SentimentEvent` | `session_id` | `aria_data.agent_sessions.id` | SET NULL |
| `ModelUsage` | `session_id` | `aria_data.agent_sessions.id` | SET NULL |
| `EngineChatMessage` | `session_id` | `aria_engine.chat_sessions.id` | CASCADE |

---

## Schema Bootstrap

On startup, `session.py` executes:

```sql
CREATE SCHEMA IF NOT EXISTS aria_data;
CREATE SCHEMA IF NOT EXISTS aria_engine;
```

Then `Base.metadata.create_all()` creates all 37 tables in their respective schemas. No manual DDL required.

---

*Last updated: v3.0.0 — Schema Architecture & Swiss-Clock Audit*
