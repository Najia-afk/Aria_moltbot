-- Aria Blue Database Migrations
-- Version tracking and incremental schema updates

-- ============================================================================
-- Migration Tracking Table
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- ============================================================================
-- Migration 1: Add metadata to goals (for sub-goals, blockers, etc.)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 1) THEN
        ALTER TABLE goals ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
        INSERT INTO schema_migrations (version, description) VALUES (1, 'Add metadata column to goals');
        RAISE NOTICE 'Migration 1 applied: Add metadata to goals';
    END IF;
END $$;

-- ============================================================================
-- Migration 2: Add parent_goal_id for sub-goals hierarchy
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 2) THEN
        ALTER TABLE goals ADD COLUMN IF NOT EXISTS parent_goal_id UUID REFERENCES goals(id);
        CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id);
        INSERT INTO schema_migrations (version, description) VALUES (2, 'Add parent_goal_id for sub-goals');
        RAISE NOTICE 'Migration 2 applied: Add parent_goal_id for sub-goals';
    END IF;
END $$;

-- ============================================================================
-- Migration 3: Rate limits tracking table
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 3) THEN
        CREATE TABLE IF NOT EXISTS rate_limits (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            skill VARCHAR(100) NOT NULL UNIQUE,
            last_action TIMESTAMP WITH TIME ZONE,
            last_post TIMESTAMP WITH TIME ZONE,
            action_count INTEGER DEFAULT 0,
            window_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_rate_limits_skill ON rate_limits(skill);
        
        INSERT INTO schema_migrations (version, description) VALUES (3, 'Create rate_limits table');
        RAISE NOTICE 'Migration 3 applied: Create rate_limits table';
    END IF;
END $$;

-- ============================================================================
-- Migration 4: Agent sessions tracking table
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 4) THEN
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            agent_id VARCHAR(100) NOT NULL,
            session_type VARCHAR(50) DEFAULT 'interactive',
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            ended_at TIMESTAMP WITH TIME ZONE,
            messages_count INTEGER DEFAULT 0,
            tokens_used INTEGER DEFAULT 0,
            cost_usd NUMERIC(10, 6) DEFAULT 0,
            status VARCHAR(50) DEFAULT 'active',
            metadata JSONB DEFAULT '{}'
        );
        
        CREATE INDEX IF NOT EXISTS idx_agent_sessions_agent ON agent_sessions(agent_id);
        CREATE INDEX IF NOT EXISTS idx_agent_sessions_status ON agent_sessions(status);
        CREATE INDEX IF NOT EXISTS idx_agent_sessions_started ON agent_sessions(started_at DESC);
        
        INSERT INTO schema_migrations (version, description) VALUES (4, 'Create agent_sessions table');
        RAISE NOTICE 'Migration 4 applied: Create agent_sessions table';
    END IF;
END $$;

-- ============================================================================
-- Migration 5: Model usage tracking table
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 5) THEN
        CREATE TABLE IF NOT EXISTS model_usage (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            model VARCHAR(100) NOT NULL,
            provider VARCHAR(50),
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd NUMERIC(10, 6) DEFAULT 0,
            latency_ms INTEGER,
            success BOOLEAN DEFAULT true,
            error_message TEXT,
            session_id UUID REFERENCES agent_sessions(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_model_usage_model ON model_usage(model);
        CREATE INDEX IF NOT EXISTS idx_model_usage_created ON model_usage(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_model_usage_session ON model_usage(session_id);
        
        INSERT INTO schema_migrations (version, description) VALUES (5, 'Create model_usage table');
        RAISE NOTICE 'Migration 5 applied: Create model_usage table';
    END IF;
END $$;

-- ============================================================================
-- Migration 6: Security events table
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 6) THEN
        CREATE TABLE IF NOT EXISTS security_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            threat_level VARCHAR(20) NOT NULL,
            threat_type VARCHAR(100) NOT NULL,
            source VARCHAR(100),
            details JSONB DEFAULT '{}',
            resolved BOOLEAN DEFAULT false,
            resolved_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_security_threat_level ON security_events(threat_level);
        CREATE INDEX IF NOT EXISTS idx_security_created ON security_events(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_security_resolved ON security_events(resolved);
        
        INSERT INTO schema_migrations (version, description) VALUES (6, 'Create security_events table');
        RAISE NOTICE 'Migration 6 applied: Create security_events table';
    END IF;
END $$;

-- ============================================================================
-- Migration 7: API key rotation tracking
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 7) THEN
        CREATE TABLE IF NOT EXISTS api_key_rotations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            service VARCHAR(100) NOT NULL,
            rotated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            reason VARCHAR(255),
            rotated_by VARCHAR(100) DEFAULT 'system',
            metadata JSONB DEFAULT '{}'
        );
        
        CREATE INDEX IF NOT EXISTS idx_api_rotation_service ON api_key_rotations(service);
        CREATE INDEX IF NOT EXISTS idx_api_rotation_rotated ON api_key_rotations(rotated_at DESC);
        
        INSERT INTO schema_migrations (version, description) VALUES (7, 'Create api_key_rotations table');
        RAISE NOTICE 'Migration 7 applied: Create api_key_rotations table';
    END IF;
END $$;

-- ============================================================================
-- Migration 8: Add composite indexes for performance
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 8) THEN
        CREATE INDEX IF NOT EXISTS idx_activity_created_action ON activity_log(created_at DESC, action);
        CREATE INDEX IF NOT EXISTS idx_thoughts_created_category ON thoughts(created_at DESC, category);
        CREATE INDEX IF NOT EXISTS idx_goals_status_priority ON goals(status, priority DESC);
        
        INSERT INTO schema_migrations (version, description) VALUES (8, 'Add composite indexes for performance');
        RAISE NOTICE 'Migration 8 applied: Add composite indexes for performance';
    END IF;
END $$;

-- ============================================================================
-- Migration 9: Knowledge graph tables (if not existing)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 9) THEN
        -- Knowledge entities
        CREATE TABLE IF NOT EXISTS knowledge_entities (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            properties JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kg_entity_name ON knowledge_entities(name);
        CREATE INDEX IF NOT EXISTS idx_kg_entity_type ON knowledge_entities(type);
        
        -- Knowledge relations
        CREATE TABLE IF NOT EXISTS knowledge_relations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            from_entity UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE NOT NULL,
            to_entity UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE NOT NULL,
            relation_type TEXT NOT NULL,
            properties JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kg_relation_from ON knowledge_relations(from_entity);
        CREATE INDEX IF NOT EXISTS idx_kg_relation_to ON knowledge_relations(to_entity);
        CREATE INDEX IF NOT EXISTS idx_kg_relation_type ON knowledge_relations(relation_type);
        
        INSERT INTO schema_migrations (version, description) VALUES (9, 'Create knowledge graph tables');
        RAISE NOTICE 'Migration 9 applied: Create knowledge graph tables';
    END IF;
END $$;

-- ============================================================================
-- Migration 10: Key-value memory table (for aria-apiclient memory operations)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 10) THEN
        CREATE TABLE IF NOT EXISTS key_value_memory (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            key VARCHAR(255) UNIQUE NOT NULL,
            value JSONB NOT NULL,
            category VARCHAR(100) DEFAULT 'general',
            ttl_seconds INTEGER,
            expires_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kv_memory_key ON key_value_memory(key);
        CREATE INDEX IF NOT EXISTS idx_kv_memory_category ON key_value_memory(category);
        CREATE INDEX IF NOT EXISTS idx_kv_memory_expires ON key_value_memory(expires_at) WHERE expires_at IS NOT NULL;
        
        INSERT INTO schema_migrations (version, description) VALUES (10, 'Create key_value_memory table');
        RAISE NOTICE 'Migration 10 applied: Create key_value_memory table';
    END IF;
END $$;

-- ============================================================================
-- View: Applied migrations summary
-- ============================================================================
CREATE OR REPLACE VIEW v_migration_status AS
SELECT 
    version,
    description,
    applied_at,
    applied_at::date as applied_date
FROM schema_migrations
ORDER BY version;

-- ============================================================================
-- Migration 11: Add missing tables for ORM parity
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 11) THEN
        -- Rename knowledge_entities.entity_type -> type (if old schema)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_entities' AND column_name='entity_type') THEN
            ALTER TABLE knowledge_entities RENAME COLUMN entity_type TO type;
        END IF;
        -- Rename knowledge_relations columns (if old schema)
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_relations' AND column_name='from_entity_id') THEN
            ALTER TABLE knowledge_relations RENAME COLUMN from_entity_id TO from_entity;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='knowledge_relations' AND column_name='to_entity_id') THEN
            ALTER TABLE knowledge_relations RENAME COLUMN to_entity_id TO to_entity;
        END IF;

        -- Hourly Goals
        CREATE TABLE IF NOT EXISTS hourly_goals (
            id SERIAL PRIMARY KEY,
            hour_slot INTEGER NOT NULL,
            goal_type VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_hourly_status ON hourly_goals(status);
        CREATE INDEX IF NOT EXISTS idx_hourly_hour_slot ON hourly_goals(hour_slot);
        CREATE INDEX IF NOT EXISTS idx_hourly_created ON hourly_goals(created_at DESC);

        -- Performance Log
        CREATE TABLE IF NOT EXISTS performance_log (
            id SERIAL PRIMARY KEY,
            review_period VARCHAR(20) NOT NULL,
            successes TEXT,
            failures TEXT,
            improvements TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_perflog_created ON performance_log(created_at DESC);

        -- Pending Complex Tasks
        CREATE TABLE IF NOT EXISTS pending_complex_tasks (
            id SERIAL PRIMARY KEY,
            task_id VARCHAR(50) UNIQUE NOT NULL,
            task_type VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            agent_type VARCHAR(50) NOT NULL,
            priority VARCHAR(20) DEFAULT 'medium',
            status VARCHAR(20) DEFAULT 'pending',
            result TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE
        );
        CREATE INDEX IF NOT EXISTS idx_pct_status ON pending_complex_tasks(status);
        CREATE INDEX IF NOT EXISTS idx_pct_task_id ON pending_complex_tasks(task_id);
        CREATE INDEX IF NOT EXISTS idx_pct_created ON pending_complex_tasks(created_at DESC);

        -- Schedule Tick
        CREATE TABLE IF NOT EXISTS schedule_tick (
            id INTEGER PRIMARY KEY,
            last_tick TIMESTAMP WITH TIME ZONE,
            tick_count INTEGER DEFAULT 0,
            heartbeat_interval INTEGER DEFAULT 3600,
            enabled BOOLEAN DEFAULT true,
            jobs_total INTEGER DEFAULT 0,
            jobs_successful INTEGER DEFAULT 0,
            jobs_failed INTEGER DEFAULT 0,
            last_job_name VARCHAR(255),
            last_job_status VARCHAR(50),
            next_job_at TIMESTAMP WITH TIME ZONE,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Scheduled Jobs
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id VARCHAR(50) PRIMARY KEY,
            agent_id VARCHAR(50) DEFAULT 'main',
            name VARCHAR(100) NOT NULL,
            enabled BOOLEAN DEFAULT true,
            schedule_kind VARCHAR(20) DEFAULT 'cron',
            schedule_expr VARCHAR(50) NOT NULL,
            session_target VARCHAR(50),
            wake_mode VARCHAR(50),
            payload_kind VARCHAR(50),
            payload_text TEXT,
            next_run_at TIMESTAMP WITH TIME ZONE,
            last_run_at TIMESTAMP WITH TIME ZONE,
            last_status VARCHAR(20),
            last_duration_ms INTEGER,
            run_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            created_at_ms INTEGER,
            updated_at_ms INTEGER,
            synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_name ON scheduled_jobs(name);
        CREATE INDEX IF NOT EXISTS idx_jobs_enabled ON scheduled_jobs(enabled);
        CREATE INDEX IF NOT EXISTS idx_jobs_next_run ON scheduled_jobs(next_run_at);

        -- Skill Status
        CREATE TABLE IF NOT EXISTS skill_status (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            skill_name VARCHAR(100) NOT NULL UNIQUE,
            canonical_name VARCHAR(100) NOT NULL,
            layer VARCHAR(20),
            status VARCHAR(20) NOT NULL DEFAULT 'unavailable',
            last_health_check TIMESTAMP WITH TIME ZONE,
            last_execution TIMESTAMP WITH TIME ZONE,
            use_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            metadata JSONB,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_skill_status_name ON skill_status(skill_name);
        CREATE INDEX IF NOT EXISTS idx_skill_status_status ON skill_status(status);
        CREATE INDEX IF NOT EXISTS idx_skill_status_layer ON skill_status(layer);

        -- Agent Performance
        CREATE TABLE IF NOT EXISTS agent_performance (
            id SERIAL PRIMARY KEY,
            agent_id VARCHAR(100) NOT NULL,
            task_type VARCHAR(100) NOT NULL,
            success BOOLEAN NOT NULL,
            duration_ms INTEGER,
            token_cost NUMERIC(10, 6),
            pheromone_score NUMERIC(5, 3) DEFAULT 0.500,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_agent_perf_agent ON agent_performance(agent_id);
        CREATE INDEX IF NOT EXISTS idx_agent_perf_task ON agent_performance(task_type);
        CREATE INDEX IF NOT EXISTS idx_agent_perf_created ON agent_performance(created_at DESC);

        -- Working Memory
        CREATE TABLE IF NOT EXISTS working_memory (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            category VARCHAR(50) NOT NULL,
            key VARCHAR(200) NOT NULL,
            value JSONB NOT NULL,
            importance FLOAT DEFAULT 0.5,
            ttl_hours INTEGER,
            source VARCHAR(100),
            checkpoint_id VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            accessed_at TIMESTAMP WITH TIME ZONE,
            access_count INTEGER DEFAULT 0,
            CONSTRAINT uq_wm_category_key UNIQUE (category, key)
        );
        CREATE INDEX IF NOT EXISTS idx_wm_category ON working_memory(category);
        CREATE INDEX IF NOT EXISTS idx_wm_key ON working_memory(key);
        CREATE INDEX IF NOT EXISTS idx_wm_importance ON working_memory(importance DESC);
        CREATE INDEX IF NOT EXISTS idx_wm_checkpoint ON working_memory(checkpoint_id);

        INSERT INTO schema_migrations (version, description) VALUES (11, 'Add missing tables for ORM parity');
        RAISE NOTICE 'Migration 11 applied: Add missing tables for ORM parity';
    END IF;
END $$;

-- ============================================================================
-- Migration 12: Enable pgvector extension + semantic_memories table (S5-01)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 12) THEN
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS semantic_memories (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            content TEXT NOT NULL,
            summary TEXT,
            category VARCHAR(50) DEFAULT 'general',
            embedding vector(768) NOT NULL,
            metadata JSONB DEFAULT '{}',
            importance FLOAT DEFAULT 0.5,
            source VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            accessed_at TIMESTAMP WITH TIME ZONE,
            access_count INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memories(category);
        CREATE INDEX IF NOT EXISTS idx_semantic_importance ON semantic_memories(importance);
        CREATE INDEX IF NOT EXISTS idx_semantic_created ON semantic_memories(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_semantic_source ON semantic_memories(source);
        -- IVFFlat index for cosine similarity search (created after data exists)
        -- CREATE INDEX IF NOT EXISTS idx_semantic_embedding ON semantic_memories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

        INSERT INTO schema_migrations (version, description) VALUES (12, 'S5-01: pgvector + semantic_memories table');
        RAISE NOTICE 'Migration 12 applied: pgvector + semantic_memories';
    END IF;
END $$;

-- ============================================================================
-- Migration 13: Lessons learned table (S5-02)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 13) THEN
        CREATE TABLE IF NOT EXISTS lessons_learned (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            error_pattern VARCHAR(200) NOT NULL,
            error_type VARCHAR(100) NOT NULL,
            skill_name VARCHAR(100),
            context JSONB DEFAULT '{}',
            resolution TEXT NOT NULL,
            resolution_code TEXT,
            occurrences INTEGER DEFAULT 1,
            last_occurred TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            effectiveness FLOAT DEFAULT 1.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT uq_lesson_pattern UNIQUE (error_pattern)
        );

        CREATE INDEX IF NOT EXISTS idx_lesson_pattern ON lessons_learned(error_pattern);
        CREATE INDEX IF NOT EXISTS idx_lesson_type ON lessons_learned(error_type);
        CREATE INDEX IF NOT EXISTS idx_lesson_skill ON lessons_learned(skill_name);

        INSERT INTO schema_migrations (version, description) VALUES (13, 'S5-02: lessons_learned table');
        RAISE NOTICE 'Migration 13 applied: lessons_learned table';
    END IF;
END $$;

-- ============================================================================
-- Migration 14: Improvement proposals table (S5-06)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 14) THEN
        CREATE TABLE IF NOT EXISTS improvement_proposals (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(50),
            risk_level VARCHAR(20) DEFAULT 'low',
            file_path VARCHAR(500),
            current_code TEXT,
            proposed_code TEXT,
            rationale TEXT,
            status VARCHAR(20) DEFAULT 'proposed',
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_proposal_status ON improvement_proposals(status);
        CREATE INDEX IF NOT EXISTS idx_proposal_risk ON improvement_proposals(risk_level);
        CREATE INDEX IF NOT EXISTS idx_proposal_category ON improvement_proposals(category);

        INSERT INTO schema_migrations (version, description) VALUES (14, 'S5-06: improvement_proposals table');
        RAISE NOTICE 'Migration 14 applied: improvement_proposals table';
    END IF;
END $$;

-- ============================================================================
-- Migration 15: Skill invocations table (S5-07)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = 15) THEN
        CREATE TABLE IF NOT EXISTS skill_invocations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            skill_name VARCHAR(100) NOT NULL,
            tool_name VARCHAR(100) NOT NULL,
            duration_ms INTEGER,
            success BOOLEAN DEFAULT true,
            error_type VARCHAR(100),
            tokens_used INTEGER,
            model_used VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_invocation_skill ON skill_invocations(skill_name);
        CREATE INDEX IF NOT EXISTS idx_invocation_created ON skill_invocations(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_invocation_success ON skill_invocations(success);

        INSERT INTO schema_migrations (version, description) VALUES (15, 'S5-07: skill_invocations table');
        RAISE NOTICE 'Migration 15 applied: skill_invocations table';
    END IF;
END $$;

-- Print migration summary
DO $$
DECLARE
    max_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(version), 0) INTO max_version FROM schema_migrations;
    RAISE NOTICE '=== Migrations Complete: % migrations applied ===', max_version;
END $$;
