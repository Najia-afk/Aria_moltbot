# S4-03: Agent Tabs in Web UI
**Epic:** E3 — Agent Pool | **Priority:** P1 | **Points:** 5 | **Phase:** 3

## Problem
There is no web interface to view and manage agents. Operators need to see all agents' status at a glance — which are active, which are busy, what model they're using, their heartbeat status, and current sessions. The existing `skill_health_dashboard.py` tracks skills but not agent runtime state.

Reference: The `AgentPool` (S4-01) provides `list_agents()` and per-agent summaries. The `aria_engine.agent_state` table has status, pheromone_score, last_active_at, current_task. Flask dashboard pages use Bootstrap 5 and live in `src/web/templates/`.

## Root Cause
OpenClaw managed agents as separate processes in separate directories with no unified view. The new engine has all agents in-process with state tracked in `agent_state`. No dashboard page was built because the `AgentPool` was just created in S4-01.

## Fix
### `src/web/templates/engine_agents.html`
```html
{% extends "base.html" %}
{% block title %}Agents — Aria Engine{% endblock %}

{% block head %}
<style>
    .agent-tab { cursor: pointer; padding: 8px 16px; border-radius: 8px 8px 0 0; }
    .agent-tab.active { background: #fff; border: 1px solid #dee2e6; border-bottom: none; }
    .agent-tab .status-dot {
        display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; margin-right: 6px;
    }
    .status-idle { background: #28a745; }
    .status-busy { background: #ffc107; animation: pulse 1s infinite; }
    .status-error { background: #dc3545; }
    .status-disabled { background: #6c757d; }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .agent-detail { background: #fff; border: 1px solid #dee2e6; border-radius: 0 8px 8px 8px; padding: 20px; }
    .metric-card { background: #f8f9fa; border-radius: 8px; padding: 12px; text-align: center; }
    .metric-card .value { font-size: 1.5rem; font-weight: bold; }
    .metric-card .label { font-size: 0.8rem; color: #6c757d; }
    .session-list { max-height: 300px; overflow-y: auto; }
    .heartbeat-indicator { font-size: 0.85rem; }
    .activity-feed { max-height: 200px; overflow-y: auto; font-size: 0.85rem; }
</style>
{% endblock %}

{% block content %}
<div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
            <h4 class="mb-0">🤖 Agent Pool</h4>
            <small class="text-muted">
                <span id="agentCount">0</span> agents |
                Pool status: <span id="poolStatus" class="badge bg-secondary">loading</span>
            </small>
        </div>
        <div>
            <button class="btn btn-sm btn-outline-primary" onclick="refreshAgents()">🔄 Refresh</button>
        </div>
    </div>

    <!-- Agent Tabs -->
    <div class="d-flex flex-wrap gap-1 mb-0" id="agentTabs">
        <div class="text-muted p-2">Loading agents...</div>
    </div>

    <!-- Agent Detail Panel -->
    <div class="agent-detail" id="agentDetail">
        <p class="text-muted text-center">Select an agent tab above</p>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
const API_BASE = '/api/engine/agents';
let agents = [];
let selectedAgent = null;

function statusColor(status) {
    return { idle: 'status-idle', busy: 'status-busy', error: 'status-error', disabled: 'status-disabled' }[status] || 'status-disabled';
}

function timeAgo(iso) {
    if (!iso) return 'never';
    const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (s < 0) return 'just now';
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s/60)}m ago`;
    if (s < 86400) return `${Math.floor(s/3600)}h ago`;
    return `${Math.floor(s/86400)}d ago`;
}

async function refreshAgents() {
    try {
        const resp = await fetch(API_BASE);
        const data = await resp.json();
        agents = data.agents || [];

        document.getElementById('agentCount').textContent = data.total_agents;
        const statusCounts = data.status_counts || {};
        const running = (statusCounts.idle || 0) + (statusCounts.busy || 0);
        document.getElementById('poolStatus').textContent =
            `${running}/${data.total_agents} active`;
        document.getElementById('poolStatus').className =
            `badge ${running > 0 ? 'bg-success' : 'bg-warning'}`;

        renderTabs();
        if (selectedAgent) {
            renderDetail(selectedAgent);
        } else if (agents.length > 0) {
            selectAgent(agents[0].agent_id);
        }
    } catch (err) {
        console.error('Failed to load agents:', err);
    }
}

function renderTabs() {
    const container = document.getElementById('agentTabs');
    container.innerHTML = agents.map(a => `
        <div class="agent-tab ${selectedAgent === a.agent_id ? 'active' : ''}"
             onclick="selectAgent('${a.agent_id}')">
            <span class="status-dot ${statusColor(a.status)}"></span>
            <strong>${a.display_name || a.agent_id}</strong>
            <small class="text-muted ms-1">${a.model ? a.model.split('/').pop() : ''}</small>
        </div>
    `).join('');
}

function selectAgent(agentId) {
    selectedAgent = agentId;
    renderTabs();
    renderDetail(agentId);
}

function renderDetail(agentId) {
    const agent = agents.find(a => a.agent_id === agentId);
    if (!agent) {
        document.getElementById('agentDetail').innerHTML =
            '<p class="text-muted">Agent not found</p>';
        return;
    }

    const pheromoneColor = agent.pheromone_score >= 0.7 ? '#28a745' :
                           agent.pheromone_score >= 0.4 ? '#ffc107' : '#dc3545';
    const pheromoneWidth = Math.round(agent.pheromone_score * 100);

    document.getElementById('agentDetail').innerHTML = `
        <div class="row mb-4">
            <div class="col-md-8">
                <h5>
                    <span class="status-dot ${statusColor(agent.status)}"></span>
                    ${agent.display_name || agent.agent_id}
                    <small class="text-muted">(${agent.agent_id})</small>
                </h5>
                <p class="mb-1">
                    <strong>Model:</strong> <code>${agent.model || 'not set'}</code> |
                    <strong>Focus:</strong> ${agent.focus_type || 'general'} |
                    <strong>Status:</strong>
                    <span class="badge bg-${agent.status === 'idle' ? 'success' : agent.status === 'busy' ? 'warning' : 'danger'}">
                        ${agent.status}
                    </span>
                </p>
                ${agent.current_task ? `<p class="mb-1 text-muted"><strong>Current task:</strong> ${agent.current_task}</p>` : ''}
            </div>
            <div class="col-md-4 text-end">
                <div class="heartbeat-indicator">
                    💓 Last active: <strong>${timeAgo(agent.last_active_at)}</strong>
                </div>
                <div class="mt-1">
                    Failures: <span class="badge ${agent.consecutive_failures > 0 ? 'bg-danger' : 'bg-success'}">
                        ${agent.consecutive_failures}
                    </span>
                </div>
            </div>
        </div>

        <!-- Metrics Row -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="value">${(agent.pheromone_score || 0.5).toFixed(3)}</div>
                    <div class="label">Pheromone Score</div>
                    <div class="progress mt-2" style="height: 4px;">
                        <div class="progress-bar" style="width: ${pheromoneWidth}%; background: ${pheromoneColor}"></div>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="value">${agent.context_length || 0}</div>
                    <div class="label">Context Messages</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="value">${agent.current_session_id ? '✅' : '—'}</div>
                    <div class="label">Active Session</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="metric-card">
                    <div class="value">${agent.status}</div>
                    <div class="label">Runtime Status</div>
                </div>
            </div>
        </div>

        <!-- Sessions for this agent -->
        <h6>📂 Sessions</h6>
        <div class="session-list mb-3" id="agentSessions-${agentId}">
            <p class="text-muted">Loading sessions...</p>
        </div>
    `;

    // Load sessions for this agent
    loadAgentSessions(agentId);
}

async function loadAgentSessions(agentId) {
    try {
        const resp = await fetch(`/api/engine/sessions?agent_id=${agentId}&limit=10`);
        const data = await resp.json();
        const container = document.getElementById(`agentSessions-${agentId}`);

        if (!data.sessions || data.sessions.length === 0) {
            container.innerHTML = '<p class="text-muted">No sessions</p>';
            return;
        }

        container.innerHTML = `
            <table class="table table-sm">
                <thead><tr><th>Title</th><th>Type</th><th>Messages</th><th>Status</th><th>Updated</th></tr></thead>
                <tbody>
                    ${data.sessions.map(s => `
                        <tr>
                            <td>${s.title || '<em>untitled</em>'}</td>
                            <td><code>${s.session_type}</code></td>
                            <td>${s.message_count || 0}</td>
                            <td><span class="badge bg-${s.status === 'active' ? 'success' : 'secondary'}">${s.status}</span></td>
                            <td><small>${timeAgo(s.updated_at)}</small></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } catch (err) {
        console.error('Failed to load sessions:', err);
    }
}

// Auto-refresh
refreshAgents();
setInterval(refreshAgents, 15000);
</script>
{% endblock %}
```

### `src/api/routers/engine_agents.py` — Agent API Proxy
```python
"""
Agent Management API — list, inspect, and manage agents.

Endpoints:
    GET  /api/engine/agents          — list all agents with status
    GET  /api/engine/agents/{id}     — get single agent detail
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from aria_engine.agent_pool import AgentPool

logger = logging.getLogger("aria.api.engine_agents")

router = APIRouter(prefix="/api/engine/agents", tags=["engine-agents"])


class AgentSummary(BaseModel):
    agent_id: str
    display_name: str = ""
    model: str = ""
    status: str = "idle"
    focus_type: Optional[str] = None
    current_session_id: Optional[str] = None
    current_task: Optional[str] = None
    pheromone_score: float = 0.5
    consecutive_failures: int = 0
    last_active_at: Optional[str] = None
    context_length: int = 0


class AgentPoolStatus(BaseModel):
    total_agents: int
    max_concurrent: int
    status_counts: Dict[str, int]
    agents: List[AgentSummary]


def get_pool() -> AgentPool:
    from aria_engine import get_engine
    engine = get_engine()
    if engine is None or engine.agent_pool is None:
        raise HTTPException(503, "Agent pool not available")
    return engine.agent_pool


@router.get("", response_model=AgentPoolStatus)
async def list_agents(pool: AgentPool = Depends(get_pool)) -> AgentPoolStatus:
    status = pool.get_status()
    return AgentPoolStatus(**status)


@router.get("/{agent_id}", response_model=AgentSummary)
async def get_agent(
    agent_id: str,
    pool: AgentPool = Depends(get_pool),
) -> AgentSummary:
    agent = pool.get_agent(agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent {agent_id!r} not found")
    return AgentSummary(**agent.get_summary())
```

### Flask Route Registration
```python
# Add to src/web/app.py:

@app.route("/agents/")
def agents_page():
    """Agent management page."""
    return render_template("engine_agents.html")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Web UI → API → AgentPool |
| 2 | .env for secrets (zero in code) | ✅ | No secrets in templates |
| 3 | models.yaml single source of truth | ❌ | Models displayed from agent config |
| 4 | Docker-first testing | ✅ | Requires running Flask + API |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S4-01 (AgentPool — list_agents, get_status)
- S4-02 (Session isolation — per-agent session listing)
- Existing Flask base template

## Verification
```bash
# 1. Template exists:
python -c "
import os
print(os.path.exists('src/web/templates/engine_agents.html'))
"
# EXPECTED: True

# 2. API router:
python -c "from src.api.routers.engine_agents import router; print(f'Routes: {len(router.routes)}')"
# EXPECTED: Routes: 2

# 3. Visual test: open http://localhost:5000/agents/ — see agent tabs with status indicators
```

## Prompt for Agent
```
Create the agent tabs web UI page for the Aria Flask dashboard.

FILES TO READ FIRST:
- aria_engine/agent_pool.py (created in S4-01 — AgentPool.list_agents(), get_status())
- src/web/templates/base.html (layout template)
- src/web/templates/engine_cron.html (created in S3-04 — for style reference)
- src/web/app.py (Flask route registration)

STEPS:
1. Read all files above
2. Create src/web/templates/engine_agents.html with tab UI
3. Create src/api/routers/engine_agents.py with list/get endpoints
4. Implement tab bar with status color indicators
5. Implement detail panel: config, metrics, sessions, heartbeat
6. Implement session loading per agent
7. Register routes in Flask and FastAPI
8. Run verification commands

CONSTRAINTS:
- Constraint 1: Web UI only calls API endpoints
- Status indicators: green=idle, yellow=busy, red=error, gray=disabled
- Auto-refresh every 15 seconds
```
