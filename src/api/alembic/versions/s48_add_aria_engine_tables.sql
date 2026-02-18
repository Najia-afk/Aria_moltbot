-- Aria Engine v2.0 — Migration s48: Add engine tables
-- Replaces OpenClaw runtime state with native PostgreSQL tables

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Engine chat sessions
CREATE TABLE IF NOT EXISTS engine_chat_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL DEFAULT 'main',
    session_type VARCHAR(50) NOT NULL DEFAULT 'interactive',
    title VARCHAR(500),
    system_prompt TEXT,
    model VARCHAR(200),
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    context_window INTEGER DEFAULT 50,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost NUMERIC(10, 6) DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ecs_agent ON engine_chat_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_ecs_status ON engine_chat_sessions(status);
CREATE INDEX IF NOT EXISTS idx_ecs_created ON engine_chat_sessions(created_at);

-- Engine chat messages
CREATE TABLE IF NOT EXISTS engine_chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES engine_chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    thinking TEXT,
    tool_calls JSONB,
    tool_results JSONB,
    model VARCHAR(200),
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost NUMERIC(10, 6),
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ecm_session ON engine_chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_ecm_role ON engine_chat_messages(role);
CREATE INDEX IF NOT EXISTS idx_ecm_created ON engine_chat_messages(created_at);

-- Engine cron jobs
CREATE TABLE IF NOT EXISTS engine_cron_jobs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    schedule VARCHAR(100) NOT NULL,
    agent_id VARCHAR(100) DEFAULT 'main',
    enabled BOOLEAN DEFAULT true,
    payload_type VARCHAR(50) DEFAULT 'prompt',
    payload TEXT NOT NULL,
    session_mode VARCHAR(50) DEFAULT 'isolated',
    max_duration_seconds INTEGER DEFAULT 300,
    retry_count INTEGER DEFAULT 0,
    last_run_at TIMESTAMPTZ,
    last_status VARCHAR(20),
    last_duration_ms INTEGER,
    last_error TEXT,
    next_run_at TIMESTAMPTZ,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ecj_enabled ON engine_cron_jobs(enabled);
CREATE INDEX IF NOT EXISTS idx_ecj_next_run ON engine_cron_jobs(next_run_at);

-- Engine agent state
CREATE TABLE IF NOT EXISTS engine_agent_state (
    agent_id VARCHAR(100) PRIMARY KEY,
    display_name VARCHAR(200),
    model VARCHAR(200) NOT NULL,
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,
    system_prompt TEXT,
    focus_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'idle',
    current_session_id UUID,
    current_task TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    pheromone_score NUMERIC(5, 3) DEFAULT 0.500,
    last_active_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Engine config (key-value store)
CREATE TABLE IF NOT EXISTS engine_config (
    key VARCHAR(200) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'system'
);

-- Engine agent tools
CREATE TABLE IF NOT EXISTS engine_agent_tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    description TEXT,
    parameters JSONB DEFAULT '{}'::jsonb,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_eat_agent ON engine_agent_tools(agent_id);

-- Mark migration in schema_migrations
INSERT INTO schema_migrations (version, description, applied_at)
VALUES ('s48', 'add_aria_engine_tables', NOW())
ON CONFLICT DO NOTHING;
