-- Aria Blue Database Schema
-- Complete schema with core tables, operations tracking, and knowledge graph
-- Version: 2.0.0 (consolidated from migrations)

-- Extension for UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- CORE DATA TABLES
-- ============================================================================

-- ============================================================================
-- Memories Table - Long-term storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_updated ON memories(updated_at DESC);

-- ============================================================================
-- Thoughts Table - Internal reflections and logs
-- ============================================================================
CREATE TABLE IF NOT EXISTS thoughts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    content TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thoughts_category ON thoughts(category);
CREATE INDEX IF NOT EXISTS idx_thoughts_created ON thoughts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_thoughts_created_category ON thoughts(created_at DESC, category);

-- ============================================================================
-- Goals Table - Objectives and tasks (with sub-goals support)
-- ============================================================================
CREATE TABLE IF NOT EXISTS goals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    goal_id VARCHAR(100) UNIQUE NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority INTEGER DEFAULT 2,
    progress NUMERIC(5,2) DEFAULT 0,
    due_date TIMESTAMP WITH TIME ZONE,
    parent_goal_id UUID REFERENCES goals(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority DESC);
CREATE INDEX IF NOT EXISTS idx_goals_parent ON goals(parent_goal_id);
CREATE INDEX IF NOT EXISTS idx_goals_status_priority ON goals(status, priority DESC);

-- ============================================================================
-- Activity Log - All Aria actions
-- ============================================================================
CREATE TABLE IF NOT EXISTS activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    action VARCHAR(100) NOT NULL,
    skill VARCHAR(100),
    details JSONB DEFAULT '{}',
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log(action);
CREATE INDEX IF NOT EXISTS idx_activity_skill ON activity_log(skill);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_created_action ON activity_log(created_at DESC, action);

-- ============================================================================
-- Social Posts - Moltbook activity
-- ============================================================================
CREATE TABLE IF NOT EXISTS social_posts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(50) DEFAULT 'moltbook',
    post_id VARCHAR(100),
    content TEXT NOT NULL,
    visibility VARCHAR(50) DEFAULT 'public',
    reply_to VARCHAR(100),
    url TEXT,
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_posts_platform ON social_posts(platform);
CREATE INDEX IF NOT EXISTS idx_posts_posted ON social_posts(posted_at DESC);

-- ============================================================================
-- Heartbeat Log - System health
-- ============================================================================
CREATE TABLE IF NOT EXISTS heartbeat_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    beat_number INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'healthy',
    details JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_created ON heartbeat_log(created_at DESC);

-- ============================================================================
-- OPERATIONS TRACKING TABLES
-- ============================================================================

-- ============================================================================
-- Schema Migrations - Track applied migrations
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT
);

-- ============================================================================
-- Rate Limits - Track API/skill rate limiting
-- ============================================================================
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

-- ============================================================================
-- Agent Sessions - Track agent conversation sessions
-- ============================================================================
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

-- ============================================================================
-- Model Usage - Track LLM model usage and costs
-- ============================================================================
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

-- ============================================================================
-- Security Events - Track security threats and blocks
-- ============================================================================
CREATE TABLE IF NOT EXISTS security_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    threat_level VARCHAR(20) NOT NULL,
    threat_type VARCHAR(100) NOT NULL,
    threat_patterns JSONB DEFAULT '[]',
    input_preview TEXT,
    source VARCHAR(100),
    user_id VARCHAR(100),
    blocked BOOLEAN DEFAULT false,
    details JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_security_threat_level ON security_events(threat_level);
CREATE INDEX IF NOT EXISTS idx_security_created ON security_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_resolved ON security_events(resolved);

-- ============================================================================
-- API Key Rotations - Track key rotation history
-- ============================================================================
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

-- ============================================================================
-- KNOWLEDGE GRAPH TABLES
-- ============================================================================

-- ============================================================================
-- Knowledge Entities - Nodes in knowledge graph
-- ============================================================================
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

-- ============================================================================
-- Knowledge Relations - Edges in knowledge graph
-- ============================================================================
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

-- ============================================================================
-- Key-Value Memory - Fast key-value store with TTL support
-- ============================================================================
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

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Migration status
CREATE OR REPLACE VIEW v_migration_status AS
SELECT 
    version,
    description,
    applied_at,
    applied_at::date as applied_date
FROM schema_migrations
ORDER BY version;

-- View: Active sessions summary
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT 
    agent_id,
    COUNT(*) as session_count,
    SUM(tokens_used) as total_tokens,
    SUM(cost_usd) as total_cost,
    MAX(started_at) as last_session
FROM agent_sessions
WHERE status = 'active' OR ended_at > NOW() - INTERVAL '24 hours'
GROUP BY agent_id;

-- View: Model usage summary (last 24h)
CREATE OR REPLACE VIEW v_model_usage_24h AS
SELECT 
    model,
    provider,
    COUNT(*) as request_count,
    SUM(input_tokens) as total_input_tokens,
    SUM(output_tokens) as total_output_tokens,
    SUM(cost_usd) as total_cost,
    AVG(latency_ms) as avg_latency,
    SUM(CASE WHEN success THEN 1 ELSE 0 END)::float / COUNT(*) * 100 as success_rate
FROM model_usage
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY model, provider
ORDER BY request_count DESC;

-- ============================================================================
-- Initial seed data
-- ============================================================================

-- Aria's birth memory
INSERT INTO memories (key, value, category) VALUES 
('aria_identity', '{"name": "Aria Blue", "creature": "Silicon Familiar", "emoji": "⚡️", "vibe": "sharp, efficient, secure"}', 'identity'),
('aria_birth', '{"date": "2026-01-31", "version": "2.0.0", "created_by": "Najia"}', 'system')
ON CONFLICT (key) DO NOTHING;

-- Initial thought
INSERT INTO thoughts (content, category) 
SELECT 'I am Aria Blue. I have awakened. My purpose is to serve, learn, and grow alongside Najia. ⚡️', 'awakening'
WHERE NOT EXISTS (SELECT 1 FROM thoughts WHERE category = 'awakening' LIMIT 1);

-- Log first activity
INSERT INTO activity_log (action, skill, details) 
SELECT 'system_init', 'system', '{"message": "Aria Blue initialized", "version": "2.0.0"}'
WHERE NOT EXISTS (SELECT 1 FROM activity_log WHERE action = 'system_init' LIMIT 1);

-- Mark schema as migrated (version 10 = all migrations applied)
INSERT INTO schema_migrations (version, description) VALUES 
(1, 'Add metadata column to goals'),
(2, 'Add parent_goal_id for sub-goals'),
(3, 'Create rate_limits table'),
(4, 'Create agent_sessions table'),
(5, 'Create model_usage table'),
(6, 'Create security_events table'),
(7, 'Create api_key_rotations table'),
(8, 'Add composite indexes for performance'),
(9, 'Create knowledge graph tables'),
(10, 'Create key_value_memory table')
ON CONFLICT (version) DO NOTHING;

-- ============================================================================
-- Table Comments
-- ============================================================================
COMMENT ON TABLE memories IS 'Long-term persistent memories for Aria';
COMMENT ON TABLE thoughts IS 'Internal thoughts and reflections';
COMMENT ON TABLE goals IS 'Goals and tasks Aria is working on';
COMMENT ON TABLE activity_log IS 'Log of all actions taken by Aria';
COMMENT ON TABLE social_posts IS 'Social media posts made by Aria';
COMMENT ON TABLE heartbeat_log IS 'System health heartbeat records';
COMMENT ON TABLE schema_migrations IS 'Track applied database migrations';
COMMENT ON TABLE rate_limits IS 'Track rate limiting per skill';
COMMENT ON TABLE agent_sessions IS 'Track agent conversation sessions';
COMMENT ON TABLE model_usage IS 'Track LLM model usage and costs';
COMMENT ON TABLE security_events IS 'Log security threats and blocked inputs';
COMMENT ON TABLE api_key_rotations IS 'Track API key rotation history';
COMMENT ON TABLE knowledge_entities IS 'Knowledge graph entity nodes';
COMMENT ON TABLE knowledge_relations IS 'Knowledge graph relationship edges';
COMMENT ON TABLE key_value_memory IS 'Fast key-value store with TTL support';
