-- Aria Engine Schema — Standalone runtime tables
-- Creates the aria_engine schema and all engine tables
-- Required by: aria_engine container (agent_pool, scheduler, chat_engine, etc.)

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE SCHEMA IF NOT EXISTS aria_engine;

-- ============================================================================
-- Chat Sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.chat_sessions (
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
    total_cost NUMERIC(10,6) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_ae_cs_agent ON aria_engine.chat_sessions(agent_id);
CREATE INDEX IF NOT EXISTS idx_ae_cs_status ON aria_engine.chat_sessions(status);
CREATE INDEX IF NOT EXISTS idx_ae_cs_created ON aria_engine.chat_sessions(created_at);

-- ============================================================================
-- Chat Messages
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES aria_engine.chat_sessions(id) ON DELETE CASCADE,
    agent_id VARCHAR(100),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    thinking TEXT,
    tool_calls JSONB,
    tool_results JSONB,
    model VARCHAR(200),
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost NUMERIC(10,6),
    latency_ms INTEGER,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ae_cm_session ON aria_engine.chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_ae_cm_agent ON aria_engine.chat_messages(agent_id);
CREATE INDEX IF NOT EXISTS idx_ae_cm_role ON aria_engine.chat_messages(role);
CREATE INDEX IF NOT EXISTS idx_ae_cm_created ON aria_engine.chat_messages(created_at);

-- Compatibility hardening for existing deployments:
-- some runtime paths expect aria_engine.chat_messages.agent_id to exist.
ALTER TABLE aria_engine.chat_messages
    ADD COLUMN IF NOT EXISTS agent_id VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_ae_cm_agent
    ON aria_engine.chat_messages(agent_id);

-- ============================================================================
-- Cron Jobs
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.cron_jobs (
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
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_status VARCHAR(20),
    last_duration_ms INTEGER,
    last_error TEXT,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ae_cj_enabled ON aria_engine.cron_jobs(enabled);
CREATE INDEX IF NOT EXISTS idx_ae_cj_next_run ON aria_engine.cron_jobs(next_run_at);

-- ============================================================================
-- Agent State
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.agent_state (
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
    pheromone_score NUMERIC(5,3) DEFAULT 0.500,
    last_active_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Config (key-value store)
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.config (
    key VARCHAR(200) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by VARCHAR(100) DEFAULT 'system'
);

-- ============================================================================
-- Agent Tools
-- ============================================================================
CREATE TABLE IF NOT EXISTS aria_engine.agent_tools (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id VARCHAR(100) NOT NULL,
    skill_name VARCHAR(100) NOT NULL,
    function_name VARCHAR(100) NOT NULL,
    description TEXT,
    parameters JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ae_at_agent ON aria_engine.agent_tools(agent_id);

-- ============================================================================
-- Seed default agent (main)
-- ============================================================================
INSERT INTO aria_engine.agent_state (agent_id, display_name, model, system_prompt, status)
VALUES ('main', 'Aria Main', 'litellm/kimi', 'You are Aria, an autonomous AI agent.', 'idle')
ON CONFLICT (agent_id) DO NOTHING;
