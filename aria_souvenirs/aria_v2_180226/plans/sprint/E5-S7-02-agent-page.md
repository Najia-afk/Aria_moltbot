# S7-02: Agent Management Web Page
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P1 | **Points:** 5 | **Phase:** 7

## Problem
There's no web UI for managing Aria's agents (main, researcher, creative, security, social, sprint). Users need to view agent status, configure models/temperature, start/stop agents, and see live activity — all from the dashboard.

## Root Cause
Agent management was done via OpenClaw config files and CLI. With OpenClaw removed, agents are managed by `AgentPool` (S4-01) with state in `aria_engine.agent_state`, but no web UI exists to interact with this data.

## Fix

### 1. Flask Route — already added in S6-06
```python
@app.route('/operations/agents/')
def operations_agents():
    return render_template('engine_agents_mgmt.html')
```

### 2. Template — `src/web/templates/engine_agents_mgmt.html`

```html
{% extends "base.html" %}
{% block title %}Aria — Agent Management{% endblock %}

{% block extra_css %}
<style>
/* ── Agent Page Layout ───────────────────────────────────────── */
.agent-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
}

.agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
}

.agent-header h1 { margin: 0; font-size: 1.4rem; color: var(--text-primary, #e0e0e0); }

.view-toggle {
    display: flex;
    background: var(--bg-tertiary, #2a2a3e);
    border-radius: 8px;
    padding: 2px;
    border: 1px solid var(--border-color, #3a3a5e);
}

.view-toggle button {
    background: none;
    border: none;
    padding: 6px 14px;
    color: var(--text-muted, #888);
    cursor: pointer;
    border-radius: 6px;
    font-size: 0.8rem;
    transition: all 0.2s;
    font-family: inherit;
}

.view-toggle button.active {
    background: var(--accent-primary, #6c5ce7);
    color: white;
}

/* ── Agent Cards ─────────────────────────────────────────────── */
.agent-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
}

.agent-card {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #2a2a3e);
    border-radius: 12px;
    padding: 20px;
    transition: border-color 0.2s;
}

.agent-card:hover { border-color: rgba(108, 92, 231, 0.3); }

.agent-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.agent-name-group {
    display: flex;
    align-items: center;
    gap: 10px;
}

.agent-avatar {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.agent-name {
    font-weight: 600;
    font-size: 1rem;
    color: var(--text-primary, #e0e0e0);
}

.agent-id {
    font-size: 0.75rem;
    color: var(--text-muted, #888);
    font-family: 'JetBrains Mono', monospace;
}

.agent-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.agent-status-dot.idle { background: #888; }
.agent-status-dot.busy { background: #00d26a; animation: pulse 1.5s infinite; }
.agent-status-dot.error { background: #ff4444; }
.agent-status-dot.disabled { background: #444; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* ── Agent Stats ─────────────────────────────────────────────── */
.agent-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    margin-bottom: 16px;
}

.agent-stat {
    background: var(--bg-primary, #0d0d1a);
    border-radius: 8px;
    padding: 10px;
    text-align: center;
}

.agent-stat-value {
    font-size: 1.1rem;
    font-weight: 600;
    color: var(--text-primary, #e0e0e0);
}

.agent-stat-label {
    font-size: 0.65rem;
    color: var(--text-muted, #888);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 2px;
}

/* ── Agent Details ───────────────────────────────────────────── */
.agent-details {
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    margin-bottom: 16px;
}

.agent-detail-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}

.agent-detail-label { color: var(--text-muted, #888); }
.agent-detail-value { color: var(--text-primary, #e0e0e0); font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }

/* ── Agent Actions ───────────────────────────────────────────── */
.agent-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}

.agent-actions button {
    flex: 1;
    min-width: 70px;
}

/* ── Pheromone Bar ───────────────────────────────────────────── */
.pheromone-bar {
    height: 4px;
    background: var(--bg-tertiary, #2a2a3e);
    border-radius: 2px;
    margin-top: 12px;
    overflow: hidden;
}

.pheromone-fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.5s ease;
}

.pheromone-label {
    display: flex;
    justify-content: space-between;
    margin-top: 4px;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
}

/* ── Detail Panel ────────────────────────────────────────────── */
.agent-detail-panel {
    position: fixed;
    top: 64px;
    right: -400px;
    width: 400px;
    bottom: 0;
    background: var(--bg-secondary, #1a1a2e);
    border-left: 1px solid var(--border-color, #2a2a3e);
    z-index: 100;
    transition: right 0.3s;
    overflow-y: auto;
    padding: 24px;
    box-shadow: -4px 0 20px rgba(0,0,0,0.3);
}

.agent-detail-panel.open { right: 0; }

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}

.panel-header h2 { margin: 0; font-size: 1.1rem; }

.panel-close {
    background: none;
    border: none;
    color: var(--text-muted, #888);
    cursor: pointer;
    font-size: 1.2rem;
    padding: 4px;
}

.panel-form .form-group {
    margin-bottom: 14px;
}

.panel-form label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    margin-bottom: 4px;
}

.panel-form input,
.panel-form select,
.panel-form textarea {
    width: 100%;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 6px;
    padding: 8px 10px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.85rem;
    font-family: inherit;
    box-sizing: border-box;
}

.panel-form textarea {
    min-height: 120px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    resize: vertical;
}

@media (max-width: 768px) {
    .agent-page { padding: 12px; }
    .agent-grid { grid-template-columns: 1fr; }
    .agent-detail-panel { width: 100%; right: -100%; }
}
</style>
{% endblock %}

{% block content %}
<div class="agent-page">
    <div class="agent-header">
        <h1>🤖 Agent Pool</h1>
        <div style="display:flex;gap:8px;align-items:center;">
            <button class="btn-secondary" onclick="loadAgents()" style="padding:8px 14px;font-size:0.85rem;background:var(--bg-tertiary);border:1px solid var(--border-color);border-radius:8px;color:var(--text-primary);cursor:pointer;">↻ Refresh</button>
            <div class="view-toggle">
                <button class="active" onclick="setView('card', this)">Cards</button>
                <button onclick="setView('list', this)">List</button>
            </div>
        </div>
    </div>

    <div class="agent-grid" id="agentGrid">
        <div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);">Loading agents…</div>
    </div>
</div>

<!-- Detail Panel (slide-in from right) -->
<div class="agent-detail-panel" id="agentDetailPanel">
    <div class="panel-header">
        <h2 id="panelAgentName">Agent</h2>
        <button class="panel-close" onclick="closePanel()">✕</button>
    </div>
    <div class="panel-form">
        <input type="hidden" id="panelAgentId">
        <div class="form-group">
            <label>Model</label>
            <select id="panelModel"></select>
        </div>
        <div class="form-group">
            <label>Temperature</label>
            <input type="range" id="panelTemp" min="0" max="2" step="0.1" oninput="document.getElementById('panelTempVal').textContent=this.value">
            <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:var(--text-muted);margin-top:2px;">
                <span>0 (Precise)</span>
                <span id="panelTempVal">0.7</span>
                <span>2 (Creative)</span>
            </div>
        </div>
        <div class="form-group">
            <label>System Prompt (preview)</label>
            <textarea id="panelPrompt" readonly placeholder="System prompt will appear here…"></textarea>
        </div>
        <div style="display:flex;gap:8px;margin-top:16px;">
            <button class="btn-primary" onclick="saveAgentConfig()" style="flex:1;justify-content:center;">Save Changes</button>
            <a id="panelPromptLink" href="#" class="btn-secondary" style="text-align:center;text-decoration:none;padding:10px 18px;border-radius:8px;font-size:0.85rem;">Edit Prompt</a>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function() {
    'use strict';

    const API = '/api/engine';
    let agents = [];
    let pollInterval = null;

    const AGENT_ICONS = {
        main: '🌟', researcher: '🔬', creative: '🎨',
        security: '🛡️', social: '📱', sprint: '🏃',
    };

    document.addEventListener('DOMContentLoaded', () => {
        loadAgents();
        pollInterval = setInterval(loadAgents, 15000); // Poll every 15s
    });

    async function loadAgents() {
        try {
            const resp = await fetch(`${API}/agents`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            agents = data.agents || data || [];
            renderAgents(agents);
        } catch(e) {
            document.getElementById('agentGrid').innerHTML = `
                <div style="grid-column:1/-1;text-align:center;padding:40px;color:#ff4444;">
                    Failed to load agents: ${e.message}
                </div>`;
        }
    }

    function renderAgents(agentList) {
        const grid = document.getElementById('agentGrid');
        if (!agentList.length) {
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);">No agents configured.</div>';
            return;
        }

        grid.innerHTML = agentList.map(a => {
            const icon = AGENT_ICONS[a.agent_id] || '🤖';
            const status = a.status || 'idle';
            const score = parseFloat(a.pheromone_score || 0.5);
            const scoreColor = score >= 0.7 ? '#00d26a' : score >= 0.4 ? '#ffc107' : '#ff4444';
            const lastActive = a.last_active_at ? timeAgo(new Date(a.last_active_at)) : 'Never';
            const model = (a.model || '').split('/').pop() || 'default';

            return `
                <div class="agent-card" data-id="${a.agent_id}">
                    <div class="agent-card-header">
                        <div class="agent-name-group">
                            <div class="agent-avatar">${icon}</div>
                            <div>
                                <div class="agent-name">${esc(a.display_name || a.agent_id)}</div>
                                <div class="agent-id">${esc(a.agent_id)}</div>
                            </div>
                        </div>
                        <div class="agent-status-dot ${status}" title="${status}"></div>
                    </div>

                    <div class="agent-stats">
                        <div class="agent-stat">
                            <div class="agent-stat-value">${a.consecutive_failures || 0}</div>
                            <div class="agent-stat-label">Failures</div>
                        </div>
                        <div class="agent-stat">
                            <div class="agent-stat-value">${score.toFixed(3)}</div>
                            <div class="agent-stat-label">Pheromone</div>
                        </div>
                        <div class="agent-stat">
                            <div class="agent-stat-value">${lastActive}</div>
                            <div class="agent-stat-label">Last Active</div>
                        </div>
                    </div>

                    <div class="agent-details">
                        <div class="agent-detail-row">
                            <span class="agent-detail-label">Model</span>
                            <span class="agent-detail-value">${esc(model)}</span>
                        </div>
                        <div class="agent-detail-row">
                            <span class="agent-detail-label">Temperature</span>
                            <span class="agent-detail-value">${a.temperature || 0.7}</span>
                        </div>
                        <div class="agent-detail-row">
                            <span class="agent-detail-label">Status</span>
                            <span class="agent-detail-value">${esc(status)}</span>
                        </div>
                        <div class="agent-detail-row">
                            <span class="agent-detail-label">Current Task</span>
                            <span class="agent-detail-value" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;">${esc(a.current_task || '—')}</span>
                        </div>
                    </div>

                    <div class="pheromone-bar">
                        <div class="pheromone-fill" style="width:${score * 100}%;background:${scoreColor};"></div>
                    </div>
                    <div class="pheromone-label">
                        <span>Pheromone Score</span>
                        <span style="color:${scoreColor};">${score.toFixed(3)}</span>
                    </div>

                    <div class="agent-actions" style="margin-top:12px;">
                        <button class="btn-secondary btn-sm" onclick="agentAction('${a.agent_id}', 'restart')">↻ Restart</button>
                        <button class="btn-secondary btn-sm" onclick="openPanel('${a.agent_id}')">⚙ Config</button>
                        ${status === 'disabled'
                            ? `<button class="btn-secondary btn-sm" onclick="agentAction('${a.agent_id}', 'enable')" style="color:#00d26a;">▶ Enable</button>`
                            : `<button class="btn-secondary btn-sm" onclick="agentAction('${a.agent_id}', 'disable')" style="color:#ff4444;">⏹ Disable</button>`
                        }
                    </div>
                </div>
            `;
        }).join('');
    }

    // ── Agent Actions ───────────────────────────────────────────
    async function agentAction(agentId, action) {
        try {
            await fetch(`${API}/agents/${agentId}/${action}`, { method: 'POST' });
            setTimeout(loadAgents, 1000);
        } catch(e) {
            alert(`Failed to ${action} agent: ${e.message}`);
        }
    }

    // ── Detail Panel ────────────────────────────────────────────
    async function openPanel(agentId) {
        const agent = agents.find(a => a.agent_id === agentId);
        if (!agent) return;

        document.getElementById('panelAgentId').value = agentId;
        document.getElementById('panelAgentName').textContent = agent.display_name || agentId;
        document.getElementById('panelTemp').value = agent.temperature || 0.7;
        document.getElementById('panelTempVal').textContent = agent.temperature || 0.7;
        document.getElementById('panelPrompt').value = agent.system_prompt || '(not loaded)';
        document.getElementById('panelPromptLink').href = `/operations/agents/${agentId}/prompt`;

        // Load models into selector
        try {
            const resp = await fetch('/api/models/available');
            const data = await resp.json();
            const models = data.models || data || [];
            const select = document.getElementById('panelModel');
            select.innerHTML = models.map(m => {
                const id = m.model_id || m.id || m;
                const name = m.display_name || m.name || id;
                return `<option value="${id}" ${id === agent.model ? 'selected' : ''}>${name}</option>`;
            }).join('');
        } catch(e) { /* ignore */ }

        document.getElementById('agentDetailPanel').classList.add('open');
    }

    function closePanel() {
        document.getElementById('agentDetailPanel').classList.remove('open');
    }

    async function saveAgentConfig() {
        const agentId = document.getElementById('panelAgentId').value;
        const config = {
            model: document.getElementById('panelModel').value,
            temperature: parseFloat(document.getElementById('panelTemp').value),
        };

        try {
            await fetch(`${API}/agents/${agentId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });
            closePanel();
            loadAgents();
        } catch(e) {
            alert('Failed to save: ' + e.message);
        }
    }

    // ── View Toggle ─────────────────────────────────────────────
    function setView(view, btn) {
        document.querySelectorAll('.view-toggle button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const grid = document.getElementById('agentGrid');
        if (view === 'list') {
            grid.style.gridTemplateColumns = '1fr';
        } else {
            grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(340px, 1fr))';
        }
    }

    // ── Helpers ─────────────────────────────────────────────────
    function timeAgo(date) {
        const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
        return `${Math.floor(seconds / 86400)}d`;
    }

    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    window.loadAgents = loadAgents;
    window.agentAction = agentAction;
    window.openPanel = openPanel;
    window.closePanel = closePanel;
    window.saveAgentConfig = saveAgentConfig;
    window.setView = setView;
})();
</script>
{% endblock %}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | UI calls /api/engine/agents endpoints |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ✅ | Model list for agent config from /api/models/available |
| 4 | Docker-first testing | ✅ | Flask template |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 (Agent pool — `/api/engine/agents` endpoint must exist)
- S4-06 (Agent dashboard updates — pheromone scores)
- S6-06 (Flask route for `/operations/agents/`)

## Verification
```bash
# 1. Page renders:
curl -s http://aria-web:5000/operations/agents/ | grep -c "Agent Pool"
# EXPECTED: 1

# 2. Agent grid:
curl -s http://aria-web:5000/operations/agents/ | grep -c "agentGrid"
# EXPECTED: at least 1

# 3. Detail panel:
curl -s http://aria-web:5000/operations/agents/ | grep -c "agentDetailPanel"
# EXPECTED: at least 1
```

## Prompt for Agent
```
Build the agent management web page for Aria operations dashboard.

FILES TO READ FIRST:
- src/web/templates/base.html (base template)
- src/web/app.py (find /operations/agents/ route)
- aria_engine/agent_pool.py (agent state schema)
- aria_agents/scoring.py (pheromone scoring)

STEPS:
1. Create src/web/templates/engine_agents_mgmt.html extending base.html
2. Build card-based grid showing each agent with status, model, pheromone score
3. Add detail panel (slide-in) for editing model, temperature
4. Add start/stop/restart buttons per agent
5. Add live status polling every 15s
6. Style with existing CSS variables
7. Make responsive

CONSTRAINTS:
- Card view and list view toggle
- Pheromone score as visual bar
- Live polling (not WebSocket — simpler for ops pages)
```
