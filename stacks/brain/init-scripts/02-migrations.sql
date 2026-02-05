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
            name VARCHAR(255) NOT NULL,
            entity_type VARCHAR(100) NOT NULL,
            properties JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kg_entities_name ON knowledge_entities(name);
        CREATE INDEX IF NOT EXISTS idx_kg_entities_type ON knowledge_entities(entity_type);
        
        -- Knowledge relations
        CREATE TABLE IF NOT EXISTS knowledge_relations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            from_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
            to_entity_id UUID REFERENCES knowledge_entities(id) ON DELETE CASCADE,
            relation_type VARCHAR(100) NOT NULL,
            properties JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        
        CREATE INDEX IF NOT EXISTS idx_kg_relations_from ON knowledge_relations(from_entity_id);
        CREATE INDEX IF NOT EXISTS idx_kg_relations_to ON knowledge_relations(to_entity_id);
        CREATE INDEX IF NOT EXISTS idx_kg_relations_type ON knowledge_relations(relation_type);
        
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

-- Print migration summary
DO $$
DECLARE
    max_version INTEGER;
BEGIN
    SELECT COALESCE(MAX(version), 0) INTO max_version FROM schema_migrations;
    RAISE NOTICE '=== Migrations Complete: % migrations applied ===', max_version;
END $$;
