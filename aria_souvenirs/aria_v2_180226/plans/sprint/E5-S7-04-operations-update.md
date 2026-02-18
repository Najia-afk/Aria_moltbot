# S7-04: Update Existing Operations Page for Engine
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P0 | **Points:** 2 | **Phase:** 7

## Problem
The existing `operations.html` template still references OpenClaw cron jobs and uses stale API endpoints. It must be updated to link to the new engine operations pages (cron, agents, health) and remove any OpenClaw-specific references.

## Root Cause
The operations page was built around OpenClaw cron management and filesystem-based job listings. With the engine providing its own cron management API, the existing page must redirect or link to the new dedicated pages while removing dead OpenClaw references.

## Fix

### 1. Update `src/web/templates/operations.html`

```html
{% extends "base.html" %}
{% block title %}Aria — Operations{% endblock %}

{% block extra_css %}
<style>
/* ── Operations Hub ──────────────────────────────────────────── */
.ops-hub {
    padding: 24px;
    max-width: 1200px;
    margin: 0 auto;
}

.ops-hub h1 {
    font-size: 1.4rem;
    margin: 0 0 8px;
    color: var(--text-primary, #e0e0e0);
}

.ops-hub .subtitle {
    color: var(--text-muted, #888);
    font-size: 0.85rem;
    margin-bottom: 24px;
}

/* ── Status Banner ───────────────────────────────────────────── */
.engine-status-banner {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #2a2a3e);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
}

.status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #888;
    flex-shrink: 0;
}

.status-dot.healthy { background: #00d26a; }
.status-dot.degraded { background: #ffc107; }
.status-dot.down { background: #ff4444; }

.status-label {
    font-size: 0.85rem;
    color: var(--text-primary, #e0e0e0);
}

.status-detail {
    font-size: 0.75rem;
    color: var(--text-muted, #888);
    margin-left: auto;
}

/* ── Cards Grid ──────────────────────────────────────────────── */
.ops-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
}

.ops-card {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #2a2a3e);
    border-radius: 10px;
    padding: 24px;
    text-decoration: none;
    color: inherit;
    transition: all 0.2s;
    display: flex;
    flex-direction: column;
}

.ops-card:hover {
    border-color: var(--accent-primary, #6c5ce7);
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(108,92,231,0.15);
}

.ops-card-icon {
    font-size: 1.8rem;
    margin-bottom: 12px;
}

.ops-card-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary, #e0e0e0);
    margin-bottom: 6px;
}

.ops-card-desc {
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    line-height: 1.5;
    flex: 1;
}

.ops-card-stat {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color, #2a2a3e);
    font-size: 0.75rem;
    color: var(--text-muted, #888);
}

.ops-card-stat strong {
    color: var(--text-primary, #e0e0e0);
}

/* ── Quick Status Section ────────────────────────────────────── */
.ops-section {
    margin-bottom: 32px;
}

.ops-section h2 {
    font-size: 1rem;
    color: var(--text-primary, #e0e0e0);
    margin: 0 0 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
}

.quick-stats {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 12px;
}

.quick-stat {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #2a2a3e);
    border-radius: 8px;
    padding: 14px;
    text-align: center;
}

.quick-stat-value {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--accent-primary, #6c5ce7);
}

.quick-stat-label {
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
}

@media (max-width: 768px) {
    .ops-cards { grid-template-columns: 1fr; }
    .quick-stats { grid-template-columns: repeat(2, 1fr); }
}
</style>
{% endblock %}

{% block content %}
<div class="ops-hub">
    <h1>Operations Hub</h1>
    <p class="subtitle">Manage and monitor Aria's engine, agents, and scheduled tasks.</p>

    <!-- Engine Status Banner -->
    <div class="engine-status-banner" id="engineStatus">
        <div class="status-dot" id="statusDot"></div>
        <span class="status-label" id="statusLabel">Checking engine status…</span>
        <span class="status-detail" id="statusDetail"></span>
    </div>

    <!-- Operations Cards -->
    <div class="ops-cards">
        <a href="/chat/" class="ops-card">
            <div class="ops-card-icon">💬</div>
            <div class="ops-card-title">Chat</div>
            <div class="ops-card-desc">Interactive chat with Aria agents. Supports streaming, thinking tokens, and tool calls.</div>
            <div class="ops-card-stat">Sessions: <strong id="statSessions">—</strong></div>
        </a>

        <a href="/operations/cron/" class="ops-card">
            <div class="ops-card-icon">⏰</div>
            <div class="ops-card-title">Cron Management</div>
            <div class="ops-card-desc">View, create, update, and manage scheduled tasks. Monitor job history and execution status.</div>
            <div class="ops-card-stat">Active jobs: <strong id="statCron">—</strong></div>
        </a>

        <a href="/operations/agents/" class="ops-card">
            <div class="ops-card-icon">🤖</div>
            <div class="ops-card-title">Agent Management</div>
            <div class="ops-card-desc">Monitor and configure agents. View status, pheromone scores, models, and system prompts.</div>
            <div class="ops-card-stat">Agents: <strong id="statAgents">—</strong></div>
        </a>

        <a href="/operations/health/" class="ops-card">
            <div class="ops-card-icon">🏥</div>
            <div class="ops-card-title">System Health</div>
            <div class="ops-card-desc">Engine status, database health, scheduler status, memory usage, and recent errors.</div>
            <div class="ops-card-stat">Uptime: <strong id="statUptime">—</strong></div>
        </a>

        <a href="/models" class="ops-card">
            <div class="ops-card-icon">🧠</div>
            <div class="ops-card-title">Models</div>
            <div class="ops-card-desc">View loaded models, providers, and capabilities. Switch models per agent or session.</div>
            <div class="ops-card-stat">Models: <strong id="statModels">—</strong></div>
        </a>

        <a href="/skills" class="ops-card">
            <div class="ops-card-icon">🧩</div>
            <div class="ops-card-title">Skills</div>
            <div class="ops-card-desc">Skill catalog, health checks, and execution history. Enable or disable skills per agent.</div>
            <div class="ops-card-stat">Skills: <strong id="statSkills">—</strong></div>
        </a>
    </div>

    <!-- Quick Stats -->
    <div class="ops-section">
        <h2>Quick Stats</h2>
        <div class="quick-stats">
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsTotalMessages">—</div>
                <div class="quick-stat-label">Messages Today</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsCronRuns">—</div>
                <div class="quick-stat-label">Cron Runs Today</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsErrors">—</div>
                <div class="quick-stat-label">Errors (24h)</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsTokens">—</div>
                <div class="quick-stat-label">Tokens Used</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsAvgLatency">—</div>
                <div class="quick-stat-label">Avg Latency</div>
            </div>
            <div class="quick-stat">
                <div class="quick-stat-value" id="qsDbSize">—</div>
                <div class="quick-stat-label">DB Size</div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function() {
    'use strict';

    const API = '/api/engine';

    document.addEventListener('DOMContentLoaded', () => {
        checkEngineHealth();
        loadQuickStats();
    });

    async function checkEngineHealth() {
        const dot = document.getElementById('statusDot');
        const label = document.getElementById('statusLabel');
        const detail = document.getElementById('statusDetail');

        try {
            const resp = await fetch(`${API}/health`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();

            if (data.status === 'healthy') {
                dot.className = 'status-dot healthy';
                label.textContent = 'Engine is healthy';
            } else if (data.status === 'degraded') {
                dot.className = 'status-dot degraded';
                label.textContent = 'Engine is degraded';
            } else {
                throw new Error('unhealthy');
            }

            detail.textContent = `Uptime: ${data.uptime || '—'} · DB: ${data.database || '—'}`;

            // Populate card stats if available
            if (data.sessions != null) document.getElementById('statSessions').textContent = data.sessions;
            if (data.cron_jobs != null) document.getElementById('statCron').textContent = data.cron_jobs;
            if (data.agents != null) document.getElementById('statAgents').textContent = data.agents;
            if (data.uptime) document.getElementById('statUptime').textContent = data.uptime;
        } catch(e) {
            dot.className = 'status-dot down';
            label.textContent = 'Engine is unreachable';
            detail.textContent = e.message;
        }
    }

    async function loadQuickStats() {
        try {
            const resp = await fetch(`${API}/stats/quick`);
            if (!resp.ok) return;
            const data = await resp.json();

            const mapping = {
                qsTotalMessages: data.messages_today,
                qsCronRuns: data.cron_runs_today,
                qsErrors: data.errors_24h,
                qsTokens: formatNumber(data.tokens_used),
                qsAvgLatency: data.avg_latency_ms ? `${data.avg_latency_ms}ms` : null,
                qsDbSize: data.db_size_mb ? `${data.db_size_mb}MB` : null,
            };

            for (const [id, value] of Object.entries(mapping)) {
                if (value != null) document.getElementById(id).textContent = value;
            }

            // Also update card stats
            if (data.model_count != null) document.getElementById('statModels').textContent = data.model_count;
            if (data.skill_count != null) document.getElementById('statSkills').textContent = data.skill_count;
        } catch(e) { /* ignore */ }
    }

    function formatNumber(n) {
        if (n == null) return null;
        if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
        if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
        return String(n);
    }
})();
</script>
{% endblock %}
```

### 2. Update Flask Route in `src/web/app.py`

The `/operations` route already exists. Ensure it renders the updated template:

```python
@app.route('/operations')
@app.route('/operations/')
def operations():
    return render_template('operations.html')
```

No changes needed — the route already exists; only the template content changes.

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Calls /api/engine/health and /stats/quick |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | N/A |
| 4 | Docker-first testing | ✅ | Standard Flask template |
| 5 | aria_memories only writable path | ❌ | Read-only page |
| 6 | No soul modification | ❌ | N/A |

## Dependencies
- S6-06 (Remove OpenClaw proxy — new engine routes)
- S7-01 (Cron page — linked from operations hub)
- S7-02 (Agent page — linked from operations hub)
- S7-05 (Health dashboard — linked from operations hub)

## Verification
```bash
# 1. Page renders without OpenClaw references:
curl -s http://aria-web:5000/operations/ | grep -c "openclaw\|clawdbot\|OpenClaw"
# EXPECTED: 0

# 2. Engine links present:
curl -s http://aria-web:5000/operations/ | grep -c "/operations/cron/\|/operations/agents/\|/operations/health/"
# EXPECTED: 3

# 3. Status banner present:
curl -s http://aria-web:5000/operations/ | grep -c "engineStatus"
# EXPECTED: 1
```

## Prompt for Agent
```
Update the existing operations.html template to serve as the Operations Hub — the central page linking to all engine management pages.

FILES TO READ FIRST:
- src/web/templates/operations.html (existing — to be replaced)
- src/web/templates/base.html (base template for CSS vars)
- src/web/app.py (Flask routes)

STEPS:
1. Replace the entire content of operations.html with the new hub layout
2. Remove ALL references to OpenClaw, clawdbot, or filesystem-based cron
3. Add card links to: /chat/, /operations/cron/, /operations/agents/, /operations/health/, /models, /skills
4. Add engine status banner that checks /api/engine/health
5. Add quick stats section showing messages today, cron runs, errors, tokens, latency, DB size
6. Ensure zero "openclaw" or "clawdbot" strings remain in the template

CONSTRAINTS:
- No OpenClaw references (Constraint: we're removing OpenClaw)
- Card links must use real routes added in S6-06
- Status check uses /api/engine/health endpoint
```
