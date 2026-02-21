# Aria Moltbot — Comprehensive API Endpoint Inventory

> Auto-generated audit of every API endpoint in the project.
> Sources: `src/api/routers/*.py`, `src/api/main.py`, `aria_engine/entrypoint.py`

## Summary

| Metric | Count |
|--------|-------|
| **Total REST endpoints** | 175+ |
| **WebSocket endpoints** | 3 |
| **GraphQL endpoint** | 1 |
| **Standalone (non-FastAPI)** | 1 |
| **Router files** | 30 |
| **Test files** | 35 |
| **Endpoints with direct test coverage** | ~130 |
| **Endpoints with NO test coverage** | ~35 |

### Dependency Injection (src/api/deps.py)

| Dependency | Target |
|------------|--------|
| `get_db()` | `AsyncSessionLocal` — main Aria PostgreSQL database |
| `get_litellm_db()` | `LiteLLMSessionLocal` — LiteLLM spend tracking database |

---

## 1. Health — `src/api/routers/health.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 1 | GET | `/health` | `health_check` | — | — | ✅ test_health.py, test_smoke.py, test_security_middleware.py |
| 2 | GET | `/host-stats` | `host_stats` | — | HTTP → host agent | ✅ test_health.py |
| 3 | GET | `/status` | `api_status` | PostgreSQL (raw) | Docker/systemd checks | ✅ test_health.py |
| 4 | GET | `/status/{service_id}` | `api_status_service` | — | Docker/systemd checks | ✅ test_health.py |
| 5 | GET | `/stats` | `api_stats` | ActivityLog, Thought, Memory | — | ✅ test_health.py |
| 6 | GET | `/health/db` | `database_health` | PostgreSQL (raw) | — | ✅ test_health.py, test_smoke.py |

**main.py direct route:**

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 7 | GET | `/api/metrics` | Prometheus instrumentator | — | — | ✅ test_health.py |

---

## 2. Activities — `src/api/routers/activities.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 8 | GET | `/activities` | `api_activities` | ActivityLog, SocialPost | — | ✅ test_activities.py, test_smoke.py, test_validation.py |
| 9 | POST | `/activities` | `create_activity` | ActivityLog, SocialPost | — | ✅ test_activities.py, test_smoke.py, test_validation.py, test_cross_entity.py |
| 10 | GET | `/activities/cron-summary` | `cron_activity_summary` | ActivityLog | — | ✅ test_activities.py |
| 11 | GET | `/activities/timeline` | `activity_timeline` | ActivityLog | — | ✅ test_activities.py |
| 12 | GET | `/activities/visualization` | `activity_visualization` | ActivityLog | — | ✅ test_activities.py |

---

## 3. Thoughts — `src/api/routers/thoughts.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 13 | GET | `/thoughts` | `api_thoughts` | Thought | — | ✅ test_thoughts.py, test_validation.py |
| 14 | POST | `/thoughts` | `create_thought` | Thought | — | ✅ test_thoughts.py, test_validation.py |

---

## 4. Memories — `src/api/routers/memories.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 15 | GET | `/memories` | `get_memories` | Memory | — | ✅ test_memories.py, test_validation.py |
| 16 | POST | `/memories` | `create_or_update_memory` | Memory | — | ✅ test_memories.py, test_smoke.py, test_validation.py, test_noise_filters.py |
| 17 | GET | `/memories/semantic` | `list_semantic_memories` | SemanticMemory | — | ✅ test_memories.py |
| 18 | POST | `/memories/semantic` | `store_semantic_memory` | SemanticMemory | LiteLLM embeddings API | ✅ test_memories.py |
| 19 | GET | `/memories/search` | `search_memories` | SemanticMemory (pgvector cosine) | — | ✅ test_memories.py, test_validation.py |
| 20 | POST | `/memories/search-by-vector` | `search_memories_by_vector` | SemanticMemory (pgvector) | — | ✅ test_memories.py |
| 21 | POST | `/memories/summarize-session` | `summarize_session` | ActivityLog, SemanticMemory | LiteLLM chat completion | ✅ test_memories.py |
| 22 | GET | `/memories/{key}` | `get_memory_by_key` | Memory | — | ✅ test_memories.py, test_validation.py |
| 23 | DELETE | `/memories/{key}` | `delete_memory` | Memory | — | ✅ test_validation.py, test_graphql.py |

---

## 5. Goals — `src/api/routers/goals.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 24 | GET | `/goals` | `list_goals` | Goal | — | ✅ test_goals.py, test_validation.py, test_web_routes.py |
| 25 | POST | `/goals` | `create_goal` | Goal | — | ✅ test_goals.py, test_smoke.py, test_validation.py, test_noise_filters.py, test_graphql.py |
| 26 | GET | `/goals/board` | `goal_board` | Goal | — | ✅ test_goals.py |
| 27 | GET | `/goals/archive` | `goal_archive` | Goal | — | ✅ test_goals.py |
| 28 | GET | `/goals/sprint-summary` | `goal_sprint_summary` | Goal | — | ✅ test_goals.py |
| 29 | GET | `/goals/history` | `goal_history` | Goal | — | ✅ test_goals.py |
| 30 | GET | `/goals/{goal_id}` | `get_goal` | Goal | — | ✅ test_goals.py, test_validation.py |
| 31 | DELETE | `/goals/{goal_id}` | `delete_goal` | Goal | — | ✅ test_goals.py, test_graphql.py |
| 32 | PATCH | `/goals/{goal_id}` | `update_goal` | Goal | — | ✅ test_goals.py |
| 33 | PATCH | `/goals/{goal_id}/move` | `move_goal` | Goal | — | ✅ test_goals.py |
| 34 | GET | `/hourly-goals` | `get_hourly_goals` | HourlyGoal | — | ✅ test_goals.py |
| 35 | POST | `/hourly-goals` | `create_hourly_goal` | HourlyGoal | — | ✅ test_goals.py, test_validation.py |
| 36 | PATCH | `/hourly-goals/{goal_id}` | `update_hourly_goal` | HourlyGoal | — | ✅ test_goals.py |
| 37 | DELETE | `/hourly-goals/{goal_id}` | `delete_hourly_goal` | HourlyGoal | — | ✅ test_goals.py |

---

## 6. Sessions — `src/api/routers/sessions.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 38 | GET | `/sessions` | `get_agent_sessions` | AgentSession | — | ✅ test_sessions.py, test_validation.py |
| 39 | GET | `/sessions/hourly` | `get_sessions_hourly` | AgentSession | — | ✅ test_sessions.py |
| 40 | POST | `/sessions` | `create_agent_session` | AgentSession | — | ✅ test_sessions.py, test_smoke.py |
| 41 | PATCH | `/sessions/{session_id}` | `update_agent_session` | AgentSession | — | ❌ No direct test |
| 42 | DELETE | `/sessions/{session_id}` | `delete_agent_session` | AgentSession | — | ❌ No direct test |
| 43 | GET | `/sessions/stats` | `get_session_stats` | AgentSession, ModelUsage; LiteLLM_SpendLogs | LiteLLM DB | ✅ test_sessions.py |

---

## 7. Model Usage — `src/api/routers/model_usage.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 44 | GET | `/model-usage` | `get_model_usage` | ModelUsage; LiteLLM DB | — | ✅ test_model_usage.py |
| 45 | POST | `/model-usage` | `log_model_usage` | ModelUsage | — | ✅ test_model_usage.py, test_validation.py |
| 46 | GET | `/model-usage/stats` | `get_model_usage_stats` | ModelUsage; LiteLLM DB | — | ✅ test_model_usage.py |

---

## 8. LiteLLM — `src/api/routers/litellm.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 47 | GET | `/litellm/models` | `api_litellm_models` | — | HTTP proxy → LiteLLM | ✅ test_litellm.py |
| 48 | GET | `/litellm/health` | `api_litellm_health` | — | HTTP proxy → LiteLLM | ✅ test_litellm.py |
| 49 | GET | `/litellm/spend` | `api_litellm_spend` | LiteLLM_SpendLogs | LiteLLM DB | ✅ test_litellm.py |
| 50 | GET | `/litellm/global-spend` | `api_litellm_global_spend` | LiteLLM_SpendLogs | LiteLLM DB + HTTP proxy | ✅ test_litellm.py |

---

## 9. Providers — `src/api/routers/providers.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 51 | GET | `/providers/balances` | `api_provider_balances` | — | HTTP → Moonshot/Kimi + OpenRouter | ✅ test_providers.py |

---

## 10. Security — `src/api/routers/security.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 52 | GET | `/security-events` | `api_security_events` | SecurityEvent | — | ✅ test_security.py |
| 53 | POST | `/security-events` | `create_security_event` | SecurityEvent | — | ✅ test_security.py |
| 54 | GET | `/security-events/stats` | `api_security_stats` | SecurityEvent | — | ✅ test_security.py |

---

## 11. Knowledge Graph — `src/api/routers/knowledge.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 55 | GET | `/skill-graph` | `get_skill_graph` | SkillGraphEntity, SkillGraphRelation | — | ✅ test_knowledge.py |
| 56 | POST | `/knowledge-graph/sync-skills` | `sync_skills` | SkillGraphEntity, SkillGraphRelation | graph_sync.sync_skill_graph | ✅ test_knowledge.py, test_cross_entity.py |
| 57 | GET | `/knowledge-graph` | `get_knowledge_graph` | KnowledgeEntity, KnowledgeRelation | — | ✅ test_knowledge.py, test_smoke.py |
| 58 | GET | `/knowledge-graph/entities` | `get_knowledge_entities` | KnowledgeEntity | — | ✅ test_knowledge.py |
| 59 | GET | `/knowledge-graph/relations` | `get_knowledge_relations` | KnowledgeRelation | — | ✅ test_knowledge.py, test_cross_entity.py |
| 60 | POST | `/knowledge-graph/entities` | `create_knowledge_entity` | KnowledgeEntity | — | ✅ test_knowledge.py, test_validation.py, test_cross_entity.py |
| 61 | POST | `/knowledge-graph/relations` | `create_knowledge_relation` | KnowledgeRelation | — | ✅ test_knowledge.py, test_validation.py, test_cross_entity.py |
| 62 | DELETE | `/knowledge-graph/auto-generated` | `delete_auto_generated` | SkillGraphRelation, SkillGraphEntity | — | ✅ test_knowledge.py, test_cross_entity.py |
| 63 | GET | `/knowledge-graph/traverse` | `graph_traverse` | SkillGraphEntity, SkillGraphRelation, KnowledgeQueryLog | — | ✅ test_knowledge.py |
| 64 | GET | `/knowledge-graph/search` | `graph_search` | SkillGraphEntity, KnowledgeQueryLog | — | ✅ test_knowledge.py, test_validation.py |
| 65 | GET | `/knowledge-graph/skill-for-task` | `find_skill_for_task` | SkillGraphEntity, SkillGraphRelation, KnowledgeQueryLog | — | ✅ test_knowledge.py |
| 66 | GET | `/knowledge-graph/query-log` | `get_query_log` | KnowledgeQueryLog | — | ✅ test_knowledge.py |

---

## 12. Social — `src/api/routers/social.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 67 | GET | `/social` | `get_social_posts` | SocialPost | — | ✅ test_social.py, test_cross_entity.py |
| 68 | POST | `/social` | `create_social_post` | SocialPost | — | ✅ test_social.py, test_validation.py, test_noise_filters.py, test_security_middleware.py |
| 69 | POST | `/social/cleanup` | `cleanup_social_posts` | SocialPost | — | ✅ test_social.py |
| 70 | POST | `/social/dedupe` | `dedupe_social_posts` | SocialPost | — | ✅ test_social.py |
| 71 | POST | `/social/import-moltbook` | `import_moltbook` | SocialPost | HTTP → Moltbook API | ✅ test_social.py |

---

## 13. Operations — `src/api/routers/operations.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 72 | GET | `/rate-limits` | `get_rate_limits` | RateLimit | — | ✅ test_operations.py |
| 73 | POST | `/rate-limits/check` | `check_rate_limit` | RateLimit | — | ✅ test_operations.py |
| 74 | POST | `/rate-limits/increment` | `increment_rate_limit` | RateLimit | — | ✅ test_operations.py |
| 75 | GET | `/api-key-rotations` | `get_api_key_rotations` | ApiKeyRotation | — | ✅ test_operations.py |
| 76 | POST | `/api-key-rotations` | `log_api_key_rotation` | ApiKeyRotation | — | ✅ test_operations.py |
| 77 | GET | `/heartbeat` | `get_heartbeats` | HeartbeatLog | — | ✅ test_operations.py |
| 78 | POST | `/heartbeat` | `create_heartbeat` | HeartbeatLog | — | ✅ test_operations.py |
| 79 | GET | `/heartbeat/latest` | `get_latest_heartbeat` | HeartbeatLog | — | ✅ test_operations.py |
| 80 | GET | `/performance` | `get_performance_logs` | PerformanceLog | — | ✅ test_operations.py |
| 81 | POST | `/performance` | `create_performance_log` | PerformanceLog | — | ✅ test_operations.py, test_validation.py |
| 82 | GET | `/tasks` | `get_pending_tasks` | PendingComplexTask | — | ✅ test_operations.py, test_validation.py |
| 83 | POST | `/tasks` | `create_pending_task` | PendingComplexTask | — | ✅ test_operations.py, test_validation.py |
| 84 | PATCH | `/tasks/{task_id}` | `update_pending_task` | PendingComplexTask | — | ❌ No direct test |
| 85 | GET | `/schedule` | `get_schedule` | ScheduleTick | — | ✅ test_operations.py |
| 86 | POST | `/schedule/tick` | `manual_tick` | ScheduleTick, EngineCronJob | — | ✅ test_operations.py |
| 87 | GET | `/jobs` | `get_scheduled_jobs` | EngineCronJob | — | ✅ test_operations.py |
| 88 | GET | `/jobs/live` | `get_jobs_live` | EngineCronJob | — | ✅ test_operations.py |
| 89 | GET | `/jobs/{job_id}` | `get_scheduled_job` | EngineCronJob | — | ✅ test_operations.py, test_validation.py |
| 90 | POST | `/jobs/sync` | `sync_jobs` | EngineCronJob | cron_sync.sync_cron_jobs_from_yaml | ✅ test_operations.py |

---

## 14. Records — `src/api/routers/records.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 91 | GET | `/records` | `api_records` | Dynamic via MODEL_MAP (all 18 tables) | — | ✅ test_records.py |
| 92 | GET | `/export` | `api_export` | Dynamic via MODEL_MAP | — | ✅ test_records.py |
| 93 | GET | `/search` | `api_search` | ActivityLog, Thought, Memory | — | ✅ test_records.py |

---

## 15. Admin — `src/api/routers/admin.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 94 | POST | `/admin/services/{service_id}/{action}` | `api_service_control` | — | Docker/shell commands | ✅ test_admin.py |
| 95 | GET | `/soul/{filename}` | `read_soul_file` | — | Filesystem | ✅ test_admin.py, test_validation.py |
| 96 | GET | `/admin/files/mind` | `list_mind_files` | — | Filesystem | ✅ test_admin.py |
| 97 | GET | `/admin/files/memories` | `list_memories_files` | — | Filesystem | ✅ test_admin.py |
| 98 | GET | `/admin/files/agents` | `list_agents_files` | — | Filesystem | ✅ test_admin.py |
| 99 | GET | `/admin/files/souvenirs` | `list_souvenirs_files` | — | Filesystem | ✅ test_admin.py |
| 100 | GET | `/admin/files/mind/{path:path}` | `read_mind_file` | — | Filesystem | ✅ test_admin.py, test_validation.py, test_security_middleware.py |
| 101 | GET | `/admin/files/memories/{path:path}` | `read_memories_file` | — | Filesystem | ✅ test_admin.py, test_validation.py |
| 102 | GET | `/admin/files/agents/{path:path}` | `read_agents_file` | — | Filesystem | ✅ test_admin.py |
| 103 | GET | `/admin/files/souvenirs/{path:path}` | `read_souvenirs_file` | — | Filesystem | ✅ test_admin.py |
| 104 | POST | `/maintenance` | `run_maintenance` | Raw SQL (ANALYZE) | — | ✅ test_admin.py |
| 105 | GET | `/table-stats` | `table_stats` | pg_stat_user_tables | — | ✅ test_admin.py, test_smoke.py |

---

## 16. Models Config — `src/api/routers/models_config.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 106 | GET | `/models/config` | `api_models_config` | — | YAML file | ✅ test_models_config.py, test_smoke.py |
| 107 | GET | `/models/available` | `api_models_available` | LlmModelEntry (fallback YAML) | — | ❌ No direct test |
| 108 | GET | `/models/pricing` | `api_models_pricing` | — | YAML file | ✅ test_models_config.py |
| 109 | POST | `/models/reload` | `api_models_reload` | — | YAML file reload | ✅ test_models_config.py |

---

## 17. Models CRUD — `src/api/routers/models_crud.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 110 | GET | `/models/db` | `list_models_db` | LlmModelEntry | — | ❌ No direct test |
| 111 | GET | `/models/db/{model_id}` | `get_model_db` | LlmModelEntry | — | ❌ No direct test |
| 112 | POST | `/models/db` | `create_model_db` | LlmModelEntry | — | ❌ No direct test |
| 113 | PUT | `/models/db/{model_id}` | `update_model_db` | LlmModelEntry | — | ❌ No direct test |
| 114 | DELETE | `/models/db/{model_id}` | `delete_model_db` | LlmModelEntry | — | ❌ No direct test |
| 115 | POST | `/models/db/sync` | `sync_models_db` | LlmModelEntry | models_sync.sync_models_from_yaml | ❌ No direct test |

---

## 18. Working Memory — `src/api/routers/working_memory.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 116 | GET | `/working-memory` | `list_working_memory` | WorkingMemory | — | ✅ test_working_memory.py |
| 117 | GET | `/working-memory/context` | `get_working_memory_context` | WorkingMemory | — | ✅ test_working_memory.py |
| 118 | POST | `/working-memory` | `store_working_memory` | WorkingMemory | — | ✅ test_working_memory.py, test_validation.py |
| 119 | PATCH | `/working-memory/{item_id}` | `update_working_memory` | WorkingMemory | — | ❌ No direct test |
| 120 | DELETE | `/working-memory/{item_id}` | `delete_working_memory` | WorkingMemory | — | ✅ test_validation.py |
| 121 | POST | `/working-memory/checkpoint` | `create_checkpoint` | WorkingMemory | — | ✅ test_working_memory.py |
| 122 | GET | `/working-memory/checkpoint` | `get_latest_checkpoint` | WorkingMemory | — | ✅ test_working_memory.py |
| 123 | GET | `/working-memory/stats` | `get_working_memory_stats` | WorkingMemory | — | ✅ test_working_memory.py |
| 124 | GET | `/working-memory/file-snapshot` | `get_working_memory_file_snapshot` | — | Filesystem | ✅ test_working_memory.py |
| 125 | POST | `/working-memory/cleanup` | `cleanup_working_memory` | WorkingMemory | — | ✅ test_working_memory.py |

---

## 19. Skills — `src/api/routers/skills.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 126 | GET | `/skills` | `list_skills` | SkillStatusRecord, SkillInvocation | — | ✅ test_skills.py, test_smoke.py |
| 127 | GET | `/skills/{name}/health` | `get_skill_health` | SkillStatusRecord | — | ✅ test_skills.py |
| 128 | POST | `/skills/seed` | `seed_skills` | SkillStatusRecord | — | ✅ test_skills.py |
| 129 | GET | `/skills/coherence` | `get_skills_coherence` | — | Filesystem scan | ✅ test_skills.py |
| 130 | POST | `/skills/invocations` | `record_invocation` | SkillInvocation | — | ✅ test_skills.py, test_cross_entity.py |
| 131 | GET | `/skills/stats` | `skill_stats` | SkillInvocation | — | ✅ test_skills.py |
| 132 | GET | `/skills/stats/summary` | `skill_stats_summary` | SkillInvocation | — | ✅ test_skills.py |
| 133 | GET | `/skills/stats/{skill_name}` | `skill_detail_stats` | SkillInvocation | — | ✅ test_skills.py |
| 134 | GET | `/skills/insights` | `skills_insights` | SkillInvocation, KnowledgeQueryLog | — | ✅ test_skills.py |
| 135 | GET | `/skills/health/dashboard` | `skill_health_dashboard` | SkillInvocation | — | ✅ test_skills.py, test_cross_entity.py |

---

## 20. Lessons — `src/api/routers/lessons.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 136 | POST | `/lessons` | `record_lesson` | LessonLearned | — | ✅ test_lessons.py, test_validation.py, test_cross_entity.py |
| 137 | GET | `/lessons/check` | `check_known_errors` | LessonLearned | — | ✅ test_lessons.py, test_cross_entity.py |
| 138 | GET | `/lessons` | `list_lessons` | LessonLearned | — | ✅ test_lessons.py |
| 139 | POST | `/lessons/seed` | `seed_lessons` | LessonLearned | — | ✅ test_lessons.py |

---

## 21. Proposals — `src/api/routers/proposals.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 140 | POST | `/proposals` | `create_proposal` | ImprovementProposal | — | ✅ test_proposals.py, test_validation.py |
| 141 | GET | `/proposals` | `list_proposals` | ImprovementProposal | — | ✅ test_proposals.py |
| 142 | GET | `/proposals/{proposal_id}` | `get_proposal` | ImprovementProposal | — | ✅ test_proposals.py, test_validation.py |
| 143 | PATCH | `/proposals/{proposal_id}` | `review_proposal` | ImprovementProposal | — | ✅ test_proposals.py |
| 144 | DELETE | `/proposals/{proposal_id}` | `delete_proposal` | ImprovementProposal | — | ✅ test_proposals.py |

---

## 22. Analysis — `src/api/routers/analysis.py` (prefix: `/analysis`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 145 | POST | `/analysis/sentiment/message` | `analyze_message_sentiment` | — | Skill: sentiment_analysis | ✅ test_analysis.py |
| 146 | POST | `/analysis/sentiment/backfill-sessions` | `backfill_sentiment_from_sessions` | SemanticMemory | Skill: sentiment_analysis; JSONL files | ✅ test_analysis.py |
| 147 | POST | `/analysis/sentiment/conversation` | `analyze_conversation_sentiment` | — | Skill: sentiment_analysis | ✅ test_analysis.py |
| 148 | POST | `/analysis/sentiment/reply` | `analyze_realtime_user_reply_sentiment` | SessionMessage, SentimentEvent, SemanticMemory, AgentSession | Skill: sentiment_analysis | ✅ test_analysis.py |
| 149 | POST | `/analysis/sentiment/backfill-messages` | `backfill_sentiment_from_session_messages` | SessionMessage, SentimentEvent, SemanticMemory | Skill: sentiment_analysis | ✅ test_analysis.py |
| 150 | GET | `/analysis/sentiment/history` | `get_sentiment_history` | SentimentEvent, SemanticMemory | — | ✅ test_analysis.py |
| 151 | POST | `/analysis/sentiment/seed-references` | `seed_sentiment_references` | SemanticMemory | LiteLLM embeddings | ✅ test_analysis.py |
| 152 | POST | `/analysis/sentiment/feedback` | `sentiment_feedback_loop` | SentimentEvent, SessionMessage, SemanticMemory | — | ✅ test_analysis.py |
| 153 | POST | `/analysis/sentiment/auto-promote` | `auto_promote_high_confidence_events` | SentimentEvent, SessionMessage, SemanticMemory | — | ✅ test_analysis.py |
| 154 | POST | `/analysis/sentiment/cleanup-placeholders` | `cleanup_sentiment_placeholders` | SemanticMemory | — | ✅ test_analysis.py |
| 155 | POST | `/analysis/patterns/detect` | `detect_patterns` | SemanticMemory | Skill: pattern_recognition | ✅ test_analysis.py |
| 156 | GET | `/analysis/patterns/history` | `get_pattern_history` | SemanticMemory | — | ✅ test_analysis.py |
| 157 | POST | `/analysis/compression/run` | `run_compression` | SemanticMemory | Skill: memory_compression | ✅ test_analysis.py |
| 158 | GET | `/analysis/compression/history` | `get_compression_history` | SemanticMemory | — | ✅ test_analysis.py |
| 159 | POST | `/analysis/compression/auto-run` | `run_auto_compression` | WorkingMemory, SemanticMemory | Skill: memory_compression | ✅ test_analysis.py |
| 160 | POST | `/analysis/seed-memories` | `seed_semantic_memories` | Thought, ActivityLog, SemanticMemory | LiteLLM embeddings | ✅ test_analysis.py |

---

## 23. Engine Cron — `src/api/routers/engine_cron.py` (prefix: `/engine/cron`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 161 | GET | `/engine/cron` | `list_cron_jobs` | — | EngineScheduler (in-memory) | ✅ test_engine_cron.py |
| 162 | POST | `/engine/cron` | `create_cron_job` | — | EngineScheduler | ✅ test_engine_cron.py |
| 163 | GET | `/engine/cron/status` | `get_scheduler_status` | — | EngineScheduler | ✅ test_engine_cron.py |
| 164 | GET | `/engine/cron/{job_id}` | `get_cron_job` | — | EngineScheduler | ✅ test_engine_cron.py |
| 165 | PUT | `/engine/cron/{job_id}` | `update_cron_job` | — | EngineScheduler | ✅ test_engine_cron.py |
| 166 | DELETE | `/engine/cron/{job_id}` | `delete_cron_job` | — | EngineScheduler | ✅ test_engine_cron.py |
| 167 | POST | `/engine/cron/{job_id}/trigger` | `trigger_cron_job` | — | EngineScheduler | ✅ test_engine_cron.py |
| 168 | GET | `/engine/cron/{job_id}/history` | `get_job_history` | — | EngineScheduler | ✅ test_engine_cron.py |

---

## 24. Engine Sessions — `src/api/routers/engine_sessions.py` (prefix: `/engine/sessions`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 169 | GET | `/engine/sessions` | `list_sessions` | aria_engine.chat_sessions | NativeSessionManager | ✅ test_engine_sessions.py |
| 170 | GET | `/engine/sessions/stats` | `get_session_stats` | aria_engine.chat_sessions | NativeSessionManager | ✅ test_engine_sessions.py |
| 171 | GET | `/engine/sessions/{session_id}` | `get_session` | aria_engine.chat_sessions | NativeSessionManager | ✅ test_engine_sessions.py |
| 172 | GET | `/engine/sessions/{session_id}/messages` | `get_session_messages` | aria_engine.chat_messages | NativeSessionManager | ❌ No direct test |
| 173 | DELETE | `/engine/sessions/{session_id}` | `delete_session` | aria_engine.chat_sessions | NativeSessionManager | ✅ test_engine_sessions.py, test_cross_entity.py |
| 174 | POST | `/engine/sessions/{session_id}/end` | `end_session` | aria_engine.chat_sessions | NativeSessionManager | ✅ test_engine_sessions.py |

---

## 25. Engine Agents — `src/api/routers/engine_agents.py` (prefix: `/engine/agents`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 175 | GET | `/engine/agents` | `list_agents` | aria_engine.agent_state | AgentPool | ✅ test_engine_agents.py |
| 176 | GET | `/engine/agents/{agent_id}` | `get_agent` | aria_engine.agent_state | AgentPool | ✅ test_engine_agents.py |

---

## 26. Engine Agent Metrics — `src/api/routers/engine_agent_metrics.py` (prefix: `/engine/agents/metrics`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 177 | GET | `/engine/agents/metrics` | `get_all_metrics` | aria_engine.agent_state, chat_messages, chat_sessions | — | ✅ test_engine_agents.py |
| 178 | GET | `/engine/agents/metrics/{agent_id}` | `get_agent_metrics` | aria_engine.agent_state, chat_messages, chat_sessions | — | ✅ test_engine_agents.py |
| 179 | GET | `/engine/agents/metrics/{agent_id}/history` | `get_agent_score_history` | aria_engine.agent_state, chat_messages, chat_sessions | — | ✅ test_engine_agents.py |

---

## 27. Agents CRUD — `src/api/routers/agents_crud.py`

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 180 | GET | `/agents/db` | `list_agents_db` | EngineAgentState | — | ❌ No direct test |
| 181 | GET | `/agents/db/{agent_id}` | `get_agent_db` | EngineAgentState | — | ❌ No direct test |
| 182 | POST | `/agents/db` | `create_agent_db` | EngineAgentState | — | ❌ No direct test |
| 183 | PUT | `/agents/db/{agent_id}` | `update_agent_db` | EngineAgentState | — | ❌ No direct test |
| 184 | DELETE | `/agents/db/{agent_id}` | `delete_agent_db` | EngineAgentState | — | ❌ No direct test |
| 185 | POST | `/agents/db/{agent_id}/enable` | `enable_agent` | EngineAgentState | — | ❌ No direct test |
| 186 | POST | `/agents/db/{agent_id}/disable` | `disable_agent` | EngineAgentState | — | ❌ No direct test |
| 187 | POST | `/agents/db/sync` | `sync_agents_from_md` | EngineAgentState | agents_sync.sync_agents_from_markdown | ❌ No direct test |

---

## 28. Engine Chat — `src/api/routers/engine_chat.py` (prefix: `/engine/chat`)

| # | Method | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|--------|------|---------|--------------------|-------------------|---------------|
| 188 | POST | `/engine/chat/sessions` | `create_session` | EngineChatSession | ChatEngine | ✅ test_engine_chat.py, test_websocket.py, test_cross_entity.py, test_smoke.py |
| 189 | GET | `/engine/chat/sessions` | `list_sessions` | EngineChatSession | — | ✅ test_engine_chat.py, test_smoke.py |
| 190 | GET | `/engine/chat/sessions/{session_id}` | `get_session` | EngineChatSession | ChatEngine | ✅ test_engine_chat.py, test_validation.py, test_cross_entity.py |
| 191 | GET | `/engine/chat/sessions/{session_id}/messages` | `get_session_messages` | EngineChatMessage | ChatEngine | ❌ No direct test (tested indirectly via session get) |
| 192 | POST | `/engine/chat/sessions/{session_id}/messages` | `send_message` | EngineChatMessage | ChatEngine → LLM | ✅ test_engine_chat.py, test_cross_entity.py |
| 193 | DELETE | `/engine/chat/sessions/{session_id}` | `delete_session` | EngineChatSession | ChatEngine | ✅ test_engine_chat.py, test_websocket.py, test_cross_entity.py |
| 194 | GET | `/engine/chat/sessions/{session_id}/export` | `export_session_endpoint` | EngineChatSession, EngineChatMessage | export_session | ✅ test_engine_chat.py, test_cross_entity.py |

### WebSocket

| # | Protocol | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|----------|------|---------|--------------------|-------------------|---------------|
| 195 | WS | `/ws/chat/{session_id}` | `chat_websocket` | EngineChatSession, EngineChatMessage | StreamManager → LLM | ✅ test_websocket.py |

---

## 29. GraphQL — `src/api/gql/` (mounted at `/graphql`)

| # | Protocol | Path | Handler | DB Models / Tables | Skills / External | Test Coverage |
|---|----------|------|---------|--------------------|-------------------|---------------|
| 196 | POST | `/graphql` | Strawberry GraphQL schema | Goal, Memory, SkillGraphEntity, etc. | — | ✅ test_graphql.py |

Strawberry schema supports queries and mutations for Goals, Memories, Knowledge Graph entities, and skill lookups.

---

## 30. Standalone — `aria_engine/entrypoint.py` (aiohttp, NOT FastAPI)

| # | Method | Path | Port | Handler | Description | Test Coverage |
|---|--------|------|------|---------|-------------|---------------|
| 197 | GET | `/health` | 8081 | `AriaEngine._health_handler` | Engine runtime health check | ❌ Not tested (separate aiohttp server) |

---

## Untested Endpoint Summary

| # | Method | Path | Router File | Reason |
|---|--------|------|-------------|--------|
| 1 | PATCH | `/sessions/{session_id}` | sessions.py | No direct test call found |
| 2 | DELETE | `/sessions/{session_id}` | sessions.py | No direct test call found |
| 3 | PATCH | `/tasks/{task_id}` | operations.py | No direct test call found |
| 4 | GET | `/models/available` | models_config.py | No direct test call found |
| 5 | GET | `/models/db` | models_crud.py | Entire models_crud.py untested |
| 6 | GET | `/models/db/{model_id}` | models_crud.py | Entire models_crud.py untested |
| 7 | POST | `/models/db` | models_crud.py | Entire models_crud.py untested |
| 8 | PUT | `/models/db/{model_id}` | models_crud.py | Entire models_crud.py untested |
| 9 | DELETE | `/models/db/{model_id}` | models_crud.py | Entire models_crud.py untested |
| 10 | POST | `/models/db/sync` | models_crud.py | Entire models_crud.py untested |
| 11 | PATCH | `/working-memory/{item_id}` | working_memory.py | No direct test call found |
| 12 | GET | `/engine/sessions/{sid}/messages` | engine_sessions.py | No direct test call found |
| 13 | GET | `/agents/db` | agents_crud.py | Entire agents_crud.py untested |
| 14 | GET | `/agents/db/{agent_id}` | agents_crud.py | Entire agents_crud.py untested |
| 15 | POST | `/agents/db` | agents_crud.py | Entire agents_crud.py untested |
| 16 | PUT | `/agents/db/{agent_id}` | agents_crud.py | Entire agents_crud.py untested |
| 17 | DELETE | `/agents/db/{agent_id}` | agents_crud.py | Entire agents_crud.py untested |
| 18 | POST | `/agents/db/{agent_id}/enable` | agents_crud.py | Entire agents_crud.py untested |
| 19 | POST | `/agents/db/{agent_id}/disable` | agents_crud.py | Entire agents_crud.py untested |
| 20 | POST | `/agents/db/sync` | agents_crud.py | Entire agents_crud.py untested |
| 21 | GET | `/engine/chat/sessions/{sid}/messages` | engine_chat.py | Only tested indirectly |
| 22 | GET | `/health` (port 8081) | entrypoint.py | Separate aiohttp server |

---

## DB Models Referenced

| Model / Table | Router(s) |
|---------------|-----------|
| ActivityLog | activities, memories, records, analysis, health |
| AgentSession | sessions |
| ApiKeyRotation | operations |
| EngineChatMessage | engine_chat |
| EngineChatSession | engine_chat |
| EngineCronJob | operations, engine_cron (via EngineScheduler) |
| EngineAgentState | agents_crud, engine_agents, engine_agent_metrics |
| Goal | goals |
| HeartbeatLog | operations |
| HourlyGoal | goals |
| ImprovementProposal | proposals |
| KnowledgeEntity | knowledge |
| KnowledgeQueryLog | knowledge, skills |
| KnowledgeRelation | knowledge |
| LessonLearned | lessons |
| LiteLLM_SpendLogs (external DB) | litellm, sessions, model_usage |
| LlmModelEntry | models_config, models_crud |
| Memory | memories, records |
| ModelUsage | model_usage, sessions |
| PendingComplexTask | operations |
| PerformanceLog | operations |
| RateLimit | operations |
| ScheduleTick | operations |
| SecurityEvent | security |
| SemanticMemory | memories, analysis |
| SentimentEvent | analysis |
| SessionMessage | analysis |
| SkillGraphEntity | knowledge |
| SkillGraphRelation | knowledge |
| SkillInvocation | skills |
| SkillStatusRecord | skills |
| SocialPost | social, activities |
| Thought | thoughts, records, analysis |
| WorkingMemory | working_memory, analysis |

---

## Skills Invoked by Endpoints

| Skill | Endpoint(s) |
|-------|-------------|
| `sentiment_analysis` | `/analysis/sentiment/message`, `/analysis/sentiment/conversation`, `/analysis/sentiment/reply`, `/analysis/sentiment/backfill-sessions`, `/analysis/sentiment/backfill-messages` |
| `pattern_recognition` | `/analysis/patterns/detect` |
| `memory_compression` | `/analysis/compression/run`, `/analysis/compression/auto-run` |

---

## External Services Called

| Service | Endpoint(s) |
|---------|-------------|
| LiteLLM Proxy (HTTP) | `/litellm/models`, `/litellm/health`, `/litellm/global-spend` |
| LiteLLM Embeddings API | `/memories/semantic` (POST), `/analysis/sentiment/seed-references`, `/analysis/seed-memories` |
| LiteLLM Chat Completion | `/memories/summarize-session`, `/engine/chat/sessions/{id}/messages` (POST), WS `/ws/chat/{id}` |
| LiteLLM SpendLogs DB | `/litellm/spend`, `/litellm/global-spend`, `/model-usage`, `/model-usage/stats`, `/sessions/stats` |
| Moonshot / Kimi API | `/providers/balances` |
| OpenRouter API | `/providers/balances` |
| Moltbook API | `/social/import-moltbook` |
| Host Agent (HTTP) | `/host-stats` |
| Docker / systemd | `/admin/services/{id}/{action}`, `/status`, `/status/{id}` |

---

## Middleware & Cross-Cutting

Registered in `src/api/main.py`:
- **CORS** — `CORSMiddleware` (permissive: `allow_origins=["*"]`)
- **SecurityMiddleware** — with `RateLimiter` (rate-limits write endpoints)
- **Request timing** — adds `X-Process-Time` header
- **Correlation ID** — adds `X-Correlation-ID` header
- **Prometheus** — `Instrumentator().instrument(app)`, exposed at `/api/metrics`

## Lifespan Initialization

During app startup (`src/api/main.py` lifespan):
1. Database schema creation (`init_db`)
2. Aria Engine boot (ChatEngine, StreamManager, AgentPool)
3. Models sync from YAML
4. Agents sync from markdown
5. Skill graph sync
6. Cron jobs sync from YAML
7. Skill invocation backfill
8. Sentiment auto-scorer background task
