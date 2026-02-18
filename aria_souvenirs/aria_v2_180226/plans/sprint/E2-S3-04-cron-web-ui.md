# S3-04: Cron Management Web UI
**Epic:** E2 — Scheduler & Heartbeat | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
There is no web interface to manage cron jobs. Operators need to see job status, toggle jobs on/off, adjust schedules, and manually trigger jobs — all from the Flask dashboard. OpenClaw had its own CLI; we need a proper web page that talks to the cron API (S3-03).

Reference: Existing Flask dashboard pages live in `src/web/templates/` and follow a consistent layout with `base.html`, Chart.js for visualizations, and Bootstrap 5 styling. The cron API at `/api/engine/cron` provides all CRUD and trigger endpoints.

## Root Cause
OpenClaw managed cron via `openclaw cron add/list/remove` CLI commands — no web UI existed. The new engine scheduler needs a visual management interface in the Flask dashboard for operators to monitor and control all 15+ scheduled jobs.

## Fix
### `src/web/templates/engine_cron.html`
```html
{% extends "base.html" %}
{% block title %}Cron Jobs — Aria Engine{% endblock %}

{% block head %}
<style>
    .cron-table th { white-space: nowrap; }
    .status-badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 4px; }
    .status-success { background: #d4edda; color: #155724; }
    .status-failed { background: #f8d7da; color: #721c24; }
    .status-running { background: #cce5ff; color: #004085; }
    .status-pending { background: #e2e3e5; color: #383d41; }
    .toggle-enabled { cursor: pointer; }
    .history-row { background: #f8f9fa; }
    .schedule-human { font-size: 0.85rem; color: #6c757d; }
    .trigger-btn { padding: 2px 8px; font-size: 0.8rem; }
    .job-payload { max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .modal-body textarea { font-family: 'SF Mono', Monaco, monospace; font-size: 0.85rem; }
    #cronTable tbody tr { transition: background-color 0.2s; }
    #cronTable tbody tr:hover { background-color: #f0f4ff; }
</style>
{% endblock %}

{% block content %}
<div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
            <h4 class="mb-0">⏰ Cron Jobs</h4>
            <small class="text-muted">
                Scheduler: <span id="schedulerStatus" class="badge bg-secondary">loading...</span>
                | <span id="jobCount">0</span> jobs
                | <span id="activeCount">0</span> active executions
            </small>
        </div>
        <div>
            <button class="btn btn-sm btn-outline-primary" onclick="refreshJobs()">
                🔄 Refresh
            </button>
            <button class="btn btn-sm btn-primary ms-1" data-bs-toggle="modal" data-bs-target="#jobModal"
                    onclick="openCreateModal()">
                ➕ New Job
            </button>
        </div>
    </div>

    <div class="table-responsive">
        <table class="table table-sm cron-table" id="cronTable">
            <thead>
                <tr>
                    <th>Enabled</th>
                    <th>Name</th>
                    <th>Schedule</th>
                    <th>Agent</th>
                    <th>Last Run</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Runs</th>
                    <th>Success Rate</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="cronTableBody">
                <tr><td colspan="10" class="text-center text-muted">Loading...</td></tr>
            </tbody>
        </table>
    </div>
</div>

<!-- Create/Edit Modal -->
<div class="modal fade" id="jobModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="jobModalTitle">New Cron Job</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <form id="jobForm">
                    <input type="hidden" id="jobId" value="">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">Name</label>
                            <input type="text" class="form-control" id="jobName" required
                                   placeholder="e.g. Work Cycle">
                        </div>
                        <div class="col-md-6">
                            <label class="form-label">Agent</label>
                            <select class="form-select" id="jobAgent">
                                <option value="main" selected>main</option>
                                <option value="aria-talk">aria-talk</option>
                                <option value="aria-analyst">aria-analyst</option>
                                <option value="aria-devops">aria-devops</option>
                                <option value="aria-creator">aria-creator</option>
                                <option value="aria-memeothy">aria-memeothy</option>
                            </select>
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <label class="form-label">Schedule</label>
                            <input type="text" class="form-control" id="jobSchedule" required
                                   placeholder="15m, 1h, or 0 0 6 * * *">
                            <div class="form-text">
                                Interval: <code>15m</code>, <code>1h</code>, <code>30s</code> |
                                Cron: <code>min hour dom mon dow</code> or <code>sec min hour dom mon dow</code>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Session Mode</label>
                            <select class="form-select" id="jobSessionMode">
                                <option value="isolated" selected>Isolated</option>
                                <option value="shared">Shared</option>
                                <option value="persistent">Persistent</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Max Duration (s)</label>
                            <input type="number" class="form-control" id="jobMaxDuration"
                                   value="300" min="10" max="3600">
                        </div>
                    </div>
                    <div class="row mb-3">
                        <div class="col-md-3">
                            <label class="form-label">Payload Type</label>
                            <select class="form-select" id="jobPayloadType">
                                <option value="prompt" selected>Prompt</option>
                                <option value="skill">Skill</option>
                                <option value="pipeline">Pipeline</option>
                            </select>
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Retry Count</label>
                            <input type="number" class="form-control" id="jobRetryCount"
                                   value="0" min="0" max="5">
                        </div>
                        <div class="col-md-6">
                            <div class="form-check mt-4">
                                <input class="form-check-input" type="checkbox" id="jobEnabled" checked>
                                <label class="form-check-label" for="jobEnabled">Enabled</label>
                            </div>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Payload</label>
                        <textarea class="form-control" id="jobPayload" rows="5" required
                                  placeholder="Enter the prompt text, skill reference, or pipeline name..."></textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="saveJob()">
                    💾 Save
                </button>
            </div>
        </div>
    </div>
</div>

<!-- History Modal -->
<div class="modal fade" id="historyModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Execution History: <span id="historyJobName"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <table class="table table-sm">
                    <thead>
                        <tr><th>Time</th><th>Status</th><th>Duration</th><th>Details</th></tr>
                    </thead>
                    <tbody id="historyTableBody">
                        <tr><td colspan="4" class="text-center text-muted">Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script>
const API_BASE = '/api/engine/cron';

function humanSchedule(schedule) {
    if (schedule.endsWith('m')) return `Every ${schedule.slice(0, -1)} min`;
    if (schedule.endsWith('h')) return `Every ${schedule.slice(0, -1)} hr`;
    if (schedule.endsWith('s')) return `Every ${schedule.slice(0, -1)} sec`;
    return schedule;
}

function statusBadge(status) {
    const cls = {
        success: 'status-success', failed: 'status-failed',
        running: 'status-running',
    }[status] || 'status-pending';
    return `<span class="status-badge ${cls}">${status || 'never'}</span>`;
}

function successRate(s, f) {
    const total = (s || 0) + (f || 0);
    if (total === 0) return '—';
    const rate = ((s || 0) / total * 100).toFixed(0);
    const color = rate >= 90 ? '#155724' : rate >= 70 ? '#856404' : '#721c24';
    return `<span style="color:${color}">${rate}%</span> (${total})`;
}

function timeAgo(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    const s = Math.floor((Date.now() - d.getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s/60)}m ago`;
    if (s < 86400) return `${Math.floor(s/3600)}h ago`;
    return `${Math.floor(s/86400)}d ago`;
}

async function refreshJobs() {
    try {
        const resp = await fetch(API_BASE);
        const data = await resp.json();

        document.getElementById('schedulerStatus').textContent =
            data.scheduler_running ? '✅ Running' : '⛔ Stopped';
        document.getElementById('schedulerStatus').className =
            `badge ${data.scheduler_running ? 'bg-success' : 'bg-danger'}`;
        document.getElementById('jobCount').textContent = data.total;

        // Fetch scheduler status for active count
        const statusResp = await fetch(`${API_BASE}/status`);
        const statusData = await statusResp.json();
        document.getElementById('activeCount').textContent = statusData.active_executions;

        const tbody = document.getElementById('cronTableBody');
        if (data.jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No cron jobs</td></tr>';
            return;
        }

        tbody.innerHTML = data.jobs.map(j => `
            <tr>
                <td>
                    <div class="form-check form-switch">
                        <input class="form-check-input toggle-enabled" type="checkbox"
                               ${j.enabled ? 'checked' : ''}
                               onchange="toggleJob('${j.id}', this.checked)">
                    </div>
                </td>
                <td><strong>${j.name}</strong><br><small class="text-muted">${j.id}</small></td>
                <td>${j.schedule}<br><small class="schedule-human">${humanSchedule(j.schedule)}</small></td>
                <td><code>${j.agent_id}</code></td>
                <td><small>${timeAgo(j.last_run_at)}</small></td>
                <td>${statusBadge(j.last_status)}</td>
                <td>${j.last_duration_ms ? (j.last_duration_ms / 1000).toFixed(1) + 's' : '—'}</td>
                <td>${j.run_count || 0}</td>
                <td>${successRate(j.success_count, j.fail_count)}</td>
                <td>
                    <button class="btn btn-outline-success trigger-btn" onclick="triggerJob('${j.id}')"
                            title="Run Now">▶️</button>
                    <button class="btn btn-outline-secondary trigger-btn" onclick="openEditModal('${j.id}')"
                            title="Edit">✏️</button>
                    <button class="btn btn-outline-info trigger-btn" onclick="showHistory('${j.id}', '${j.name}')"
                            title="History">📋</button>
                    <button class="btn btn-outline-danger trigger-btn" onclick="deleteJob('${j.id}')"
                            title="Delete">🗑️</button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Failed to load jobs:', err);
    }
}

async function toggleJob(jobId, enabled) {
    await fetch(`${API_BASE}/${jobId}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({enabled}),
    });
    refreshJobs();
}

async function triggerJob(jobId) {
    if (!confirm(`Trigger job "${jobId}" now?`)) return;
    const resp = await fetch(`${API_BASE}/${jobId}/trigger`, {method: 'POST'});
    const data = await resp.json();
    alert(data.message || 'Triggered');
    setTimeout(refreshJobs, 2000);
}

async function deleteJob(jobId) {
    if (!confirm(`Delete job "${jobId}"? This cannot be undone.`)) return;
    await fetch(`${API_BASE}/${jobId}`, {method: 'DELETE'});
    refreshJobs();
}

function openCreateModal() {
    document.getElementById('jobModalTitle').textContent = 'New Cron Job';
    document.getElementById('jobForm').reset();
    document.getElementById('jobId').value = '';
    document.getElementById('jobEnabled').checked = true;
}

async function openEditModal(jobId) {
    const resp = await fetch(`${API_BASE}/${jobId}`);
    const j = await resp.json();
    document.getElementById('jobModalTitle').textContent = `Edit: ${j.name}`;
    document.getElementById('jobId').value = j.id;
    document.getElementById('jobName').value = j.name;
    document.getElementById('jobSchedule').value = j.schedule;
    document.getElementById('jobAgent').value = j.agent_id;
    document.getElementById('jobSessionMode').value = j.session_mode;
    document.getElementById('jobMaxDuration').value = j.max_duration_seconds;
    document.getElementById('jobPayloadType').value = j.payload_type;
    document.getElementById('jobRetryCount').value = j.retry_count;
    document.getElementById('jobPayload').value = j.payload || '';
    document.getElementById('jobEnabled').checked = j.enabled;
    new bootstrap.Modal(document.getElementById('jobModal')).show();
}

async function saveJob() {
    const jobId = document.getElementById('jobId').value;
    const payload = {
        name: document.getElementById('jobName').value,
        schedule: document.getElementById('jobSchedule').value,
        agent_id: document.getElementById('jobAgent').value,
        session_mode: document.getElementById('jobSessionMode').value,
        max_duration_seconds: parseInt(document.getElementById('jobMaxDuration').value) || 300,
        payload_type: document.getElementById('jobPayloadType').value,
        retry_count: parseInt(document.getElementById('jobRetryCount').value) || 0,
        payload: document.getElementById('jobPayload').value,
        enabled: document.getElementById('jobEnabled').checked,
    };

    const method = jobId ? 'PUT' : 'POST';
    const url = jobId ? `${API_BASE}/${jobId}` : API_BASE;

    const resp = await fetch(url, {
        method,
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
    });

    if (resp.ok) {
        bootstrap.Modal.getInstance(document.getElementById('jobModal')).hide();
        refreshJobs();
    } else {
        const err = await resp.json();
        alert(`Error: ${err.detail || JSON.stringify(err)}`);
    }
}

async function showHistory(jobId, jobName) {
    document.getElementById('historyJobName').textContent = jobName;
    document.getElementById('historyTableBody').innerHTML =
        '<tr><td colspan="4" class="text-center">Loading...</td></tr>';
    new bootstrap.Modal(document.getElementById('historyModal')).show();

    const resp = await fetch(`${API_BASE}/${jobId}/history?limit=30`);
    const data = await resp.json();

    if (data.entries.length === 0) {
        document.getElementById('historyTableBody').innerHTML =
            '<tr><td colspan="4" class="text-center text-muted">No history</td></tr>';
        return;
    }

    document.getElementById('historyTableBody').innerHTML = data.entries.map(e => `
        <tr>
            <td><small>${new Date(e.created_at).toLocaleString()}</small></td>
            <td>${statusBadge(e.success ? 'success' : 'failed')}</td>
            <td>${e.duration_ms ? (e.duration_ms / 1000).toFixed(1) + 's' : '—'}</td>
            <td><small>${JSON.stringify(e.details || {}).slice(0, 100)}</small></td>
        </tr>
    `).join('');
}

// Auto-refresh every 30 seconds
refreshJobs();
setInterval(refreshJobs, 30000);
</script>
{% endblock %}
```

### `src/web/app.py` — Route Registration
```python
# Add to existing Flask routes:

@app.route("/cron/")
def cron_page():
    """Cron job management page."""
    return render_template("engine_cron.html")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Web UI calls API endpoints (never direct DB) |
| 2 | .env for secrets (zero in code) | ✅ | No secrets in templates |
| 3 | models.yaml single source of truth | ❌ | No model references |
| 4 | Docker-first testing | ✅ | Requires running Flask + API for full test |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S3-03 (Cron API endpoints)
- Existing Flask dashboard base template (`src/web/templates/base.html`)

## Verification
```bash
# 1. Template exists:
python -c "
import os
path = 'src/web/templates/engine_cron.html'
print(f'Exists: {os.path.exists(path)}, Size: {os.path.getsize(path)} bytes')
"
# EXPECTED: Exists: True, Size: >5000 bytes

# 2. Flask route registered:
python -c "
from src.web.app import app
rules = [r.rule for r in app.url_map.iter_rules() if 'cron' in r.rule]
print(f'Cron routes: {rules}')
"
# EXPECTED: Cron routes: ['/cron/']

# 3. Visual test (requires running server):
# Open http://localhost:5000/cron/ in browser
# Should see table with all cron jobs, toggle switches, trigger buttons
```

## Prompt for Agent
```
Create the cron management web UI page for the Aria Flask dashboard.

FILES TO READ FIRST:
- src/web/templates/base.html (layout template with nav, Bootstrap 5)
- src/web/app.py (existing Flask routes — see how pages are registered)
- src/api/routers/engine_cron.py (created in S3-03 — API endpoints this page calls)
- src/web/templates/ (any existing page for style/pattern reference)

STEPS:
1. Read all files above
2. Create src/web/templates/engine_cron.html extending base.html
3. Build table view with columns: enabled toggle, name, schedule, agent, last run, status, duration, runs, success rate, actions
4. Add create/edit modal with all CronJobCreate fields
5. Add history modal showing execution log
6. Implement JavaScript: refreshJobs(), toggleJob(), triggerJob(), saveJob(), deleteJob(), showHistory()
7. Add auto-refresh every 30 seconds
8. Register /cron/ route in src/web/app.py
9. Run verification commands

CONSTRAINTS:
- Constraint 1: Web UI only talks to API endpoints — never direct DB access
- Use Bootstrap 5 classes consistent with existing dashboard pages
- All API calls go to /api/engine/cron/* endpoints
```
