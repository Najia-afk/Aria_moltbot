-- ============================================================================
-- MIGRATION: Move all data from public schema → aria_data / aria_engine
-- ONE-TIME migration script — idempotent (uses ON CONFLICT DO NOTHING)
-- ============================================================================

BEGIN;

-- Ensure schemas exist
CREATE SCHEMA IF NOT EXISTS aria_data;
CREATE SCHEMA IF NOT EXISTS aria_engine;

-- ────────────────────────────────────────────────────────────────────
-- aria_data tables
-- ────────────────────────────────────────────────────────────────────

-- 1. memories (67 rows)
INSERT INTO aria_data.memories (id, key, value, category, created_at, updated_at)
SELECT id, key, value, category, created_at, updated_at
FROM public.memories
ON CONFLICT (id) DO NOTHING;

-- 2. thoughts (108 rows)
INSERT INTO aria_data.thoughts (id, content, category, metadata, created_at)
SELECT id, content, COALESCE(category, 'general'), COALESCE(metadata, '{}'::jsonb), COALESCE(created_at, NOW())
FROM public.thoughts
ON CONFLICT (id) DO NOTHING;

-- 3. goals (93 rows) — public has extra parent_goal_id, metadata we skip
INSERT INTO aria_data.goals (id, goal_id, title, description, status, priority, progress, due_date,
    created_at, completed_at, sprint, board_column, position, assigned_to, tags, updated_at)
SELECT id, goal_id, title, description,
    COALESCE(status, 'pending'), COALESCE(priority, 2), COALESCE(progress, 0), due_date,
    COALESCE(created_at, NOW()), completed_at,
    COALESCE(sprint, 'backlog'), COALESCE(board_column, 'backlog'), COALESCE(position, 0),
    assigned_to, COALESCE(tags, '[]'::jsonb), COALESCE(updated_at, NOW())
FROM public.goals
ON CONFLICT (id) DO NOTHING;

-- 4. activity_log (427 rows)
INSERT INTO aria_data.activity_log (id, action, skill, details, success, error_message, created_at)
SELECT id, action, skill, COALESCE(details, '{}'::jsonb), COALESCE(success, true), error_message,
    COALESCE(created_at, NOW())
FROM public.activity_log
ON CONFLICT (id) DO NOTHING;

-- 5. social_posts (145 rows)
INSERT INTO aria_data.social_posts (id, platform, post_id, content, visibility, reply_to, url, posted_at, metadata)
SELECT id, COALESCE(platform, 'moltbook'), post_id, content,
    COALESCE(visibility, 'public'), reply_to, url,
    COALESCE(posted_at, NOW()), COALESCE(metadata, '{}'::jsonb)
FROM public.social_posts
ON CONFLICT (id) DO NOTHING;

-- 6. heartbeat_log (121 rows)
INSERT INTO aria_data.heartbeat_log (id, beat_number, status, details, created_at)
SELECT id, beat_number, COALESCE(status, 'healthy'), COALESCE(details, '{}'::jsonb),
    COALESCE(created_at, NOW())
FROM public.heartbeat_log
ON CONFLICT (id) DO NOTHING;

-- 7. hourly_goals (115 rows)
INSERT INTO aria_data.hourly_goals (id, hour_slot, goal_type, description, status, completed_at, created_at)
SELECT id, hour_slot, goal_type, description,
    COALESCE(status, 'pending'), completed_at, COALESCE(created_at, NOW())
FROM public.hourly_goals
ON CONFLICT (id) DO NOTHING;

-- Fix serial sequence for hourly_goals
SELECT setval('aria_data.hourly_goals_id_seq',
    COALESCE((SELECT MAX(id) FROM aria_data.hourly_goals), 0) + 1, false);

-- 8. performance_log (106 rows)
INSERT INTO aria_data.performance_log (id, review_period, successes, failures, improvements, created_at)
SELECT id, review_period, successes, failures, improvements, COALESCE(created_at, NOW())
FROM public.performance_log
ON CONFLICT (id) DO NOTHING;

-- Fix serial sequence
SELECT setval('aria_data.performance_log_id_seq',
    COALESCE((SELECT MAX(id) FROM aria_data.performance_log), 0) + 1, false);

-- 9. pending_complex_tasks (128 rows)
INSERT INTO aria_data.pending_complex_tasks (id, task_id, task_type, description, agent_type,
    priority, status, result, created_at, completed_at)
SELECT id, task_id, task_type, description, agent_type,
    COALESCE(priority, 'medium'), COALESCE(status, 'pending'), result,
    COALESCE(created_at, NOW()), completed_at
FROM public.pending_complex_tasks
ON CONFLICT (id) DO NOTHING;

-- Fix serial sequence
SELECT setval('aria_data.pending_complex_tasks_id_seq',
    COALESCE((SELECT MAX(id) FROM aria_data.pending_complex_tasks), 0) + 1, false);

-- 10. model_usage (107 rows) — FK to agent_sessions, migrate sessions first
INSERT INTO aria_data.agent_sessions (id, agent_id, session_type, started_at, ended_at,
    messages_count, tokens_used, cost_usd, status, metadata)
SELECT id, agent_id, COALESCE(session_type, 'interactive'), COALESCE(started_at, NOW()),
    ended_at, COALESCE(messages_count, 0), COALESCE(tokens_used, 0),
    COALESCE(cost_usd, 0), COALESCE(status, 'active'), COALESCE(metadata, '{}'::jsonb)
FROM public.agent_sessions
ON CONFLICT (id) DO NOTHING;

INSERT INTO aria_data.model_usage (id, model, provider, input_tokens, output_tokens, cost_usd,
    latency_ms, success, error_message, session_id, created_at)
SELECT id, model, provider, COALESCE(input_tokens, 0), COALESCE(output_tokens, 0),
    COALESCE(cost_usd, 0), latency_ms, COALESCE(success, true), error_message,
    session_id, COALESCE(created_at, NOW())
FROM public.model_usage
ON CONFLICT (id) DO NOTHING;

-- 11. security_events (107 rows) — public has extra resolved/resolved_at, skip
INSERT INTO aria_data.security_events (id, threat_level, threat_type, threat_patterns,
    input_preview, source, user_id, blocked, details, created_at)
SELECT id, threat_level, threat_type, COALESCE(threat_patterns, '[]'::jsonb),
    input_preview, source, user_id, COALESCE(blocked, false),
    COALESCE(details, '{}'::jsonb), COALESCE(created_at, NOW())
FROM public.security_events
ON CONFLICT (id) DO NOTHING;

-- 12. knowledge_entities (334 rows)
INSERT INTO aria_data.knowledge_entities (id, name, type, properties, created_at, updated_at)
SELECT id, name, type, COALESCE(properties, '{}'::jsonb),
    COALESCE(created_at, NOW()), COALESCE(updated_at, NOW())
FROM public.knowledge_entities
ON CONFLICT (id) DO NOTHING;

-- 13. knowledge_relations (145 rows) — FK to knowledge_entities
INSERT INTO aria_data.knowledge_relations (id, from_entity, to_entity, relation_type, properties, created_at)
SELECT id, from_entity, to_entity, relation_type,
    COALESCE(properties, '{}'::jsonb), COALESCE(created_at, NOW())
FROM public.knowledge_relations
ON CONFLICT (id) DO NOTHING;

-- 14. semantic_memories (104 rows)
INSERT INTO aria_data.semantic_memories (id, content, summary, category, embedding, metadata,
    importance, source, created_at, accessed_at, access_count)
SELECT id, content, summary, COALESCE(category, 'general'), embedding,
    COALESCE(metadata, '{}'::jsonb), COALESCE(importance, 0.5), source,
    COALESCE(created_at, NOW()), accessed_at, COALESCE(access_count, 0)
FROM public.semantic_memories
ON CONFLICT (id) DO NOTHING;

-- 15. lessons_learned (207 rows)
INSERT INTO aria_data.lessons_learned (id, error_pattern, error_type, skill_name, context,
    resolution, resolution_code, occurrences, last_occurred, effectiveness, created_at)
SELECT id, error_pattern, error_type, skill_name, COALESCE(context, '{}'::jsonb),
    resolution, resolution_code, COALESCE(occurrences, 1),
    COALESCE(last_occurred, NOW()), COALESCE(effectiveness, 1.0), COALESCE(created_at, NOW())
FROM public.lessons_learned
ON CONFLICT (id) DO NOTHING;

-- 16. improvement_proposals (81 rows)
INSERT INTO aria_data.improvement_proposals (id, title, description, category, risk_level,
    file_path, current_code, proposed_code, rationale, status, reviewed_by, reviewed_at, created_at)
SELECT id, title, description, category, COALESCE(risk_level, 'low'),
    file_path, current_code, proposed_code, rationale,
    COALESCE(status, 'proposed'), reviewed_by, reviewed_at, COALESCE(created_at, NOW())
FROM public.improvement_proposals
ON CONFLICT (id) DO NOTHING;

-- 17. working_memory (51 rows)
INSERT INTO aria_data.working_memory (id, category, key, value, importance, ttl_hours,
    source, checkpoint_id, created_at, updated_at, accessed_at, access_count)
SELECT id, category, key, value, COALESCE(importance, 0.5), ttl_hours,
    source, checkpoint_id, COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW()), accessed_at, COALESCE(access_count, 0)
FROM public.working_memory
ON CONFLICT (id) DO NOTHING;

-- 18. skill_invocations (206 rows)
INSERT INTO aria_data.skill_invocations (id, skill_name, tool_name, duration_ms, success,
    error_type, tokens_used, model_used, created_at)
SELECT id, skill_name, tool_name, duration_ms, COALESCE(success, true),
    error_type, tokens_used, model_used, COALESCE(created_at, NOW())
FROM public.skill_invocations
ON CONFLICT (id) DO NOTHING;

-- 19. agent_performance (0 rows but migrate anyway)
INSERT INTO aria_data.agent_performance (id, agent_id, task_type, success, duration_ms,
    token_cost, pheromone_score, created_at)
SELECT id, agent_id, task_type, success, duration_ms,
    token_cost, COALESCE(pheromone_score, 0.500), COALESCE(created_at, NOW())
FROM public.agent_performance
ON CONFLICT (id) DO NOTHING;

-- Fix serial sequence
SELECT setval('aria_data.agent_performance_id_seq',
    COALESCE((SELECT MAX(id) FROM aria_data.agent_performance), 0) + 1, false);

-- ────────────────────────────────────────────────────────────────────
-- aria_engine tables (migrate missing data only)
-- ────────────────────────────────────────────────────────────────────

-- rate_limits: 70 in public, 0 in aria_engine
INSERT INTO aria_engine.rate_limits (id, skill, last_action, action_count, window_start,
    created_at, last_post, updated_at)
SELECT id, skill, last_action, COALESCE(action_count, 0), COALESCE(window_start, NOW()),
    COALESCE(created_at, NOW()), last_post, COALESCE(updated_at, NOW())
FROM public.rate_limits
ON CONFLICT (id) DO NOTHING;

-- api_key_rotations: 106 in public, 0 in aria_engine
INSERT INTO aria_engine.api_key_rotations (id, service, rotated_at, reason, rotated_by, metadata)
SELECT id, service, COALESCE(rotated_at, NOW()), reason,
    COALESCE(rotated_by, 'system'), COALESCE(metadata, '{}'::jsonb)
FROM public.api_key_rotations
ON CONFLICT (id) DO NOTHING;

-- schedule_tick: 1 in public, 0 in aria_engine
INSERT INTO aria_engine.schedule_tick (id, last_tick, tick_count, heartbeat_interval, enabled,
    jobs_total, jobs_successful, jobs_failed, last_job_name, last_job_status, next_job_at, updated_at)
SELECT id, last_tick, COALESCE(tick_count, 0), COALESCE(heartbeat_interval, 3600),
    COALESCE(enabled, true), COALESCE(jobs_total, 0), COALESCE(jobs_successful, 0),
    COALESCE(jobs_failed, 0), last_job_name, last_job_status, next_job_at,
    COALESCE(updated_at, NOW())
FROM public.schedule_tick
ON CONFLICT (id) DO NOTHING;

-- ────────────────────────────────────────────────────────────────────
-- Verify migration counts
-- ────────────────────────────────────────────────────────────────────
DO $$
DECLARE
    v_count INT;
BEGIN
    SELECT COUNT(*) INTO v_count FROM aria_data.thoughts;
    RAISE NOTICE 'aria_data.thoughts: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_data.goals;
    RAISE NOTICE 'aria_data.goals: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_data.memories;
    RAISE NOTICE 'aria_data.memories: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_data.activity_log;
    RAISE NOTICE 'aria_data.activity_log: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_data.heartbeat_log;
    RAISE NOTICE 'aria_data.heartbeat_log: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_data.social_posts;
    RAISE NOTICE 'aria_data.social_posts: % rows', v_count;
    SELECT COUNT(*) INTO v_count FROM aria_engine.rate_limits;
    RAISE NOTICE 'aria_engine.rate_limits: % rows', v_count;
END $$;

COMMIT;
