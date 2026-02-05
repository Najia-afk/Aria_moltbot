-- Aria Income Operations Database Schema

-- Opportunities tracking
CREATE TABLE IF NOT EXISTS opportunities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(50) NOT NULL, -- 'crypto', 'secops', 'business'
    subcategory VARCHAR(100), -- 'yield_farming', 'bug_bounty', 'saas', etc.
    description TEXT,
    entry_barrier VARCHAR(50), -- 'low', 'medium', 'high'
    capital_required DECIMAL(20, 8), -- in USD
    expected_apy DECIMAL(8, 4), -- annual yield %
    risk_level VARCHAR(20), -- 'low', 'medium', 'high', 'extreme'
    automation_potential INTEGER CHECK (automation_potential BETWEEN 0 AND 100),
    time_commitment VARCHAR(50), -- 'passive', 'weekly', 'daily', 'full_time'
    platforms TEXT[], -- where to execute
    tools_required TEXT[],
    status VARCHAR(50) DEFAULT 'researching', -- researching, testing, active, paused, abandoned
    priority INTEGER DEFAULT 5,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Bubble monetization tracking
CREATE TABLE IF NOT EXISTS bubble_monetization (
    id SERIAL PRIMARY KEY,
    angle VARCHAR(100) NOT NULL, -- 'saas', 'api', 'licensing', 'data'
    target_segment VARCHAR(255),
    pricing_model VARCHAR(100),
    price_point VARCHAR(100),
    value_proposition TEXT,
    implementation_complexity VARCHAR(20),
    time_to_revenue VARCHAR(50),
    status VARCHAR(50) DEFAULT 'idea',
    priority INTEGER DEFAULT 5,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Crypto yield tracking
CREATE TABLE IF NOT EXISTS yield_positions (
    id SERIAL PRIMARY KEY,
    protocol VARCHAR(100) NOT NULL,
    chain VARCHAR(50) NOT NULL,
    strategy VARCHAR(100), -- 'staking', 'lp', 'lending', 'farming'
    asset VARCHAR(50) NOT NULL,
    amount DECIMAL(20, 8),
    entry_price DECIMAL(20, 8),
    current_value DECIMAL(20, 8),
    apy DECIMAL(8, 4),
    rewards_earned DECIMAL(20, 8) DEFAULT 0,
    start_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    risks TEXT[],
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Bug bounty / SecOps income
CREATE TABLE IF NOT EXISTS secops_work (
    id SERIAL PRIMARY KEY,
    platform VARCHAR(100), -- 'immunefi', 'synack', 'hackerone'
    work_type VARCHAR(100), -- 'bug_bounty', 'audit', 'ctf', 'consulting'
    project_name VARCHAR(255),
    severity VARCHAR(20), -- 'critical', 'high', 'medium', 'low'
    bounty_amount DECIMAL(20, 8),
    currency VARCHAR(10),
    status VARCHAR(50), -- 'researching', 'submitted', 'validated', 'paid', 'rejected'
    effort_hours DECIMAL(8, 2),
    hourly_rate DECIMAL(10, 2) GENERATED ALWAYS AS (
        CASE WHEN effort_hours > 0 THEN bounty_amount / effort_hours ELSE NULL END
    ) STORED,
    notes TEXT,
    submitted_at TIMESTAMP,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily logs
CREATE TABLE IF NOT EXISTS daily_logs (
    id SERIAL PRIMARY KEY,
    log_date DATE DEFAULT CURRENT_DATE,
    category VARCHAR(50),
    action_taken TEXT,
    results TEXT,
    earnings DECIMAL(20, 8) DEFAULT 0,
    expenses DECIMAL(20, 8) DEFAULT 0,
    learnings TEXT,
    next_steps TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_opportunities_category ON opportunities(category);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_yield_positions_status ON yield_positions(status);
CREATE INDEX IF NOT EXISTS idx_secops_status ON secops_work(status);
CREATE INDEX IF NOT EXISTS idx_daily_logs_date ON daily_logs(log_date);
