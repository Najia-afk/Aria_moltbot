# S7-01: Cron Management Web Page
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P0 | **Points:** 5 | **Phase:** 7

## Problem
Aria's cron jobs were managed via OpenClaw CLI (`openclaw cron add/list/remove`). With OpenClaw removed, there's no web UI for managing scheduled jobs. We need a full cron management page that lets users view, create, edit, toggle, trigger, and inspect execution history for all cron jobs.

## Root Cause
The cron management was entirely inside OpenClaw's Node.js process. The new APScheduler-based scheduler (S3-01) stores jobs in `aria_engine.cron_jobs` PostgreSQL table, and the cron CRUD API (S3-03) exposes endpoints — but no web UI exists to manage them.

## Fix

### 1. Flask Route — already in `src/web/app.py` (from S6-06)
```python
@app.route('/operations/cron/')
def operations_cron():
    return render_template('engine_operations.html')
```

### 2. Template — `src/web/templates/engine_operations.html`

```html
{% extends "base.html" %}
{% block title %}Aria — Cron Management{% endblock %}

{% block extra_css %}
<style>
/* ── Cron Page Layout ────────────────────────────────────────── */
.cron-page {
    max-width: 1200px;
    margin: 0 auto;
    padding: 24px;
}

.cron-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    flex-wrap: wrap;
    gap: 12px;
}

.cron-header h1 {
    margin: 0;
    font-size: 1.4rem;
    color: var(--text-primary, #e0e0e0);
}

.cron-actions {
    display: flex;
    gap: 8px;
}

.btn-primary {
    background: var(--accent-primary, #6c5ce7);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
    font-family: inherit;
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-primary:hover { background: #5a4bd6; }

.btn-secondary {
    background: var(--bg-tertiary, #2a2a3e);
    color: var(--text-primary, #e0e0e0);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 8px;
    padding: 10px 18px;
    font-size: 0.85rem;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
}

.btn-secondary:hover { background: var(--bg-secondary, #1a1a2e); }

.btn-sm {
    padding: 6px 12px;
    font-size: 0.8rem;
    border-radius: 6px;
}

.btn-danger {
    background: rgba(255, 68, 68, 0.1);
    color: #ff4444;
    border: 1px solid rgba(255, 68, 68, 0.2);
}

.btn-danger:hover { background: rgba(255, 68, 68, 0.2); }

/* ── Cron Table ──────────────────────────────────────────────── */
.cron-table-wrapper {
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid var(--border-color, #2a2a3e);
    background: var(--bg-secondary, #1a1a2e);
}

.cron-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.cron-table th {
    text-align: left;
    padding: 12px 16px;
    background: var(--bg-tertiary, #2a2a3e);
    color: var(--text-muted, #888);
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-color, #3a3a5e);
    white-space: nowrap;
}

.cron-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
    color: var(--text-primary, #e0e0e0);
    vertical-align: middle;
}

.cron-table tr:hover {
    background: rgba(108, 92, 231, 0.04);
}

.cron-table tr:last-child td {
    border-bottom: none;
}

/* ── Toggle Switch ───────────────────────────────────────────── */
.toggle-switch {
    position: relative;
    width: 40px;
    height: 22px;
    display: inline-block;
}

.toggle-switch input {
    display: none;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background: var(--bg-tertiary, #2a2a3e);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 22px;
    transition: all 0.3s;
}

.toggle-slider::before {
    content: '';
    position: absolute;
    width: 16px;
    height: 16px;
    left: 2px;
    bottom: 2px;
    background: var(--text-muted, #888);
    border-radius: 50%;
    transition: all 0.3s;
}

.toggle-switch input:checked + .toggle-slider {
    background: rgba(0, 210, 106, 0.2);
    border-color: #00d26a;
}

.toggle-switch input:checked + .toggle-slider::before {
    transform: translateX(18px);
    background: #00d26a;
}

/* ── Status Badges ───────────────────────────────────────────── */
.status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 500;
}

.status-badge.success { background: rgba(0, 210, 106, 0.15); color: #00d26a; }
.status-badge.error { background: rgba(255, 68, 68, 0.15); color: #ff4444; }
.status-badge.running { background: rgba(102, 126, 234, 0.15); color: #667eea; }
.status-badge.pending { background: rgba(255, 193, 7, 0.15); color: #ffc107; }

/* ── Schedule Display ────────────────────────────────────────── */
.schedule-display {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--accent-primary, #6c5ce7);
}

.schedule-human {
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    margin-top: 2px;
}

/* ── History Expansion ───────────────────────────────────────── */
.history-row td {
    padding: 0;
    background: var(--bg-primary, #0d0d1a);
}

.history-content {
    padding: 12px 16px;
    font-size: 0.8rem;
}

.history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.8rem;
}

.history-table th {
    text-align: left;
    padding: 6px 10px;
    color: var(--text-muted, #888);
    font-size: 0.7rem;
    text-transform: uppercase;
}

.history-table td {
    padding: 6px 10px;
    color: var(--text-primary, #e0e0e0);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}

/* ── Modal ───────────────────────────────────────────────────── */
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.6);
    z-index: 1000;
    display: none;
    align-items: center;
    justify-content: center;
}

.modal-overlay.active { display: flex; }

.modal {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    max-height: 90vh;
    overflow-y: auto;
    padding: 24px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}

.modal h2 {
    margin: 0 0 20px;
    font-size: 1.1rem;
    color: var(--text-primary, #e0e0e0);
}

.form-group {
    margin-bottom: 16px;
}

.form-group label {
    display: block;
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    margin-bottom: 4px;
    font-weight: 500;
}

.form-group input,
.form-group select,
.form-group textarea {
    width: 100%;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 6px;
    padding: 10px 12px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.85rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
    box-sizing: border-box;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
    border-color: var(--accent-primary, #6c5ce7);
}

.form-group textarea {
    min-height: 100px;
    resize: vertical;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
}

.form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.form-hint {
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    margin-top: 4px;
}

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 20px;
}

/* ── Cron Presets ─────────────────────────────────────────────── */
.cron-presets {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 4px;
}

.cron-preset {
    background: var(--bg-tertiary, #2a2a3e);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    cursor: pointer;
    transition: all 0.15s;
}

.cron-preset:hover {
    background: var(--accent-primary, #6c5ce7);
    color: white;
    border-color: var(--accent-primary, #6c5ce7);
}

.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted, #888);
}

.empty-state .icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.5; }
.empty-state h3 { margin: 0 0 8px; color: var(--text-primary, #e0e0e0); }
.empty-state p { margin: 0; font-size: 0.9rem; }

@media (max-width: 768px) {
    .cron-page { padding: 12px; }
    .form-row { grid-template-columns: 1fr; }
    .cron-table { font-size: 0.8rem; }
}
</style>
{% endblock %}

{% block content %}
<div class="cron-page">
    <div class="cron-header">
        <h1>⏰ Cron Jobs</h1>
        <div class="cron-actions">
            <button class="btn-secondary" onclick="loadCronJobs()">↻ Refresh</button>
            <button class="btn-primary" onclick="openModal()">+ New Job</button>
        </div>
    </div>

    <div class="cron-table-wrapper">
        <table class="cron-table" id="cronTable">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Schedule</th>
                    <th>Agent</th>
                    <th>Enabled</th>
                    <th>Last Run</th>
                    <th>Next Run</th>
                    <th>Stats</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="cronTableBody">
                <tr>
                    <td colspan="8">
                        <div class="empty-state" id="cronLoading">Loading cron jobs…</div>
                    </td>
                </tr>
            </tbody>
        </table>
    </div>
</div>

<!-- Add/Edit Modal -->
<div class="modal-overlay" id="cronModal">
    <div class="modal">
        <h2 id="modalTitle">Add Cron Job</h2>
        <input type="hidden" id="editJobId" value="">

        <div class="form-group">
            <label>Job Name</label>
            <input type="text" id="jobName" placeholder="e.g. daily-reflection">
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Cron Expression</label>
                <input type="text" id="jobSchedule" placeholder="0 * * * *">
                <div class="cron-presets">
                    <span class="cron-preset" onclick="setCron('* * * * *')">Every min</span>
                    <span class="cron-preset" onclick="setCron('*/5 * * * *')">Every 5m</span>
                    <span class="cron-preset" onclick="setCron('0 * * * *')">Hourly</span>
                    <span class="cron-preset" onclick="setCron('0 */4 * * *')">Every 4h</span>
                    <span class="cron-preset" onclick="setCron('0 0 * * *')">Daily</span>
                    <span class="cron-preset" onclick="setCron('0 0 * * 1')">Weekly</span>
                </div>
            </div>
            <div class="form-group">
                <label>Agent</label>
                <select id="jobAgent">
                    <option value="main">main</option>
                    <option value="researcher">researcher</option>
                    <option value="creative">creative</option>
                    <option value="security">security</option>
                    <option value="social">social</option>
                    <option value="sprint">sprint</option>
                </select>
            </div>
        </div>

        <div class="form-row">
            <div class="form-group">
                <label>Payload Type</label>
                <select id="jobPayloadType">
                    <option value="prompt">Prompt</option>
                    <option value="skill">Skill</option>
                    <option value="pipeline">Pipeline</option>
                </select>
            </div>
            <div class="form-group">
                <label>Session Mode</label>
                <select id="jobSessionMode">
                    <option value="isolated">Isolated (new session each run)</option>
                    <option value="shared">Shared (reuse session)</option>
                    <option value="persistent">Persistent (never close)</option>
                </select>
            </div>
        </div>

        <div class="form-group">
            <label>Payload</label>
            <textarea id="jobPayload" placeholder="Enter prompt text or skill/pipeline name…"></textarea>
            <div class="form-hint">For prompts: enter the text. For skills: enter skill name (e.g. memory_compression). For pipelines: enter pipeline ID.</div>
        </div>

        <div class="modal-actions">
            <button class="btn-secondary" onclick="closeModal()">Cancel</button>
            <button class="btn-primary" onclick="saveJob()">Save Job</button>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
(function() {
    'use strict';

    const API = '/api/engine/cron';
    let cronJobs = [];

    document.addEventListener('DOMContentLoaded', loadCronJobs);

    // ── Load ────────────────────────────────────────────────────
    async function loadCronJobs() {
        const tbody = document.getElementById('cronTableBody');
        try {
            const resp = await fetch(`${API}/jobs`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            cronJobs = data.jobs || data || [];
            renderTable(cronJobs);
        } catch(e) {
            tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="icon">⚠️</div><h3>Failed to load</h3><p>${e.message}</p></div></td></tr>`;
        }
    }

    // ── Render ───────────────────────────────────────────────────
    function renderTable(jobs) {
        const tbody = document.getElementById('cronTableBody');

        if (!jobs.length) {
            tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state"><div class="icon">⏰</div><h3>No cron jobs</h3><p>Create your first scheduled job.</p></div></td></tr>`;
            return;
        }

        tbody.innerHTML = jobs.map(job => {
            const lastRun = job.last_run_at ? new Date(job.last_run_at).toLocaleString() : '—';
            const nextRun = job.next_run_at ? new Date(job.next_run_at).toLocaleString() : '—';
            const lastStatus = job.last_status
                ? `<span class="status-badge ${job.last_status}">${job.last_status}</span>`
                : '—';
            const stats = `${job.success_count || 0}✓ / ${job.fail_count || 0}✗`;

            return `
                <tr data-id="${job.id}">
                    <td>
                        <div style="font-weight:500;">${esc(job.name)}</div>
                        <div style="font-size:0.7rem;color:var(--text-muted);">${esc(job.id)}</div>
                    </td>
                    <td>
                        <div class="schedule-display">${esc(job.schedule)}</div>
                        <div class="schedule-human">${cronToHuman(job.schedule)}</div>
                    </td>
                    <td><span class="status-badge" style="background:rgba(108,92,231,0.15);color:#667eea;">${esc(job.agent_id || 'main')}</span></td>
                    <td>
                        <label class="toggle-switch">
                            <input type="checkbox" ${job.enabled ? 'checked' : ''} onchange="toggleJob('${job.id}', this.checked)">
                            <span class="toggle-slider"></span>
                        </label>
                    </td>
                    <td>
                        <div>${lastRun}</div>
                        <div>${lastStatus}</div>
                    </td>
                    <td>${nextRun}</td>
                    <td><span style="font-size:0.8rem;">${stats}</span></td>
                    <td>
                        <div style="display:flex;gap:4px;">
                            <button class="btn-secondary btn-sm" onclick="triggerJob('${job.id}')" title="Run now">▶</button>
                            <button class="btn-secondary btn-sm" onclick="editJob('${job.id}')" title="Edit">✏️</button>
                            <button class="btn-secondary btn-sm" onclick="toggleHistory('${job.id}')" title="History">📋</button>
                            <button class="btn-danger btn-sm" onclick="deleteJob('${job.id}')" title="Delete">🗑</button>
                        </div>
                    </td>
                </tr>
                <tr class="history-row" id="history-${job.id}" style="display:none;">
                    <td colspan="8">
                        <div class="history-content" id="history-content-${job.id}">Loading history…</div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // ── CRUD Operations ─────────────────────────────────────────
    async function toggleJob(id, enabled) {
        try {
            await fetch(`${API}/jobs/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled }),
            });
        } catch(e) {
            alert('Failed to toggle job: ' + e.message);
            loadCronJobs();
        }
    }

    async function triggerJob(id) {
        try {
            const resp = await fetch(`${API}/jobs/${id}/trigger`, { method: 'POST' });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            alert('Job triggered successfully');
            setTimeout(loadCronJobs, 2000);
        } catch(e) {
            alert('Failed to trigger job: ' + e.message);
        }
    }

    async function deleteJob(id) {
        if (!confirm('Delete this cron job? This cannot be undone.')) return;
        try {
            await fetch(`${API}/jobs/${id}`, { method: 'DELETE' });
            loadCronJobs();
        } catch(e) {
            alert('Failed to delete job: ' + e.message);
        }
    }

    async function saveJob() {
        const editId = document.getElementById('editJobId').value;
        const job = {
            name: document.getElementById('jobName').value.trim(),
            schedule: document.getElementById('jobSchedule').value.trim(),
            agent_id: document.getElementById('jobAgent').value,
            payload_type: document.getElementById('jobPayloadType').value,
            payload: document.getElementById('jobPayload').value.trim(),
            session_mode: document.getElementById('jobSessionMode').value,
        };

        if (!job.name || !job.schedule || !job.payload) {
            alert('Name, schedule, and payload are required.');
            return;
        }

        try {
            const url = editId ? `${API}/jobs/${editId}` : `${API}/jobs`;
            const method = editId ? 'PUT' : 'POST';
            const resp = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(job),
            });
            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `HTTP ${resp.status}`);
            }
            closeModal();
            loadCronJobs();
        } catch(e) {
            alert('Failed to save job: ' + e.message);
        }
    }

    // ── Edit ────────────────────────────────────────────────────
    function editJob(id) {
        const job = cronJobs.find(j => j.id === id);
        if (!job) return;

        document.getElementById('editJobId').value = job.id;
        document.getElementById('modalTitle').textContent = 'Edit Cron Job';
        document.getElementById('jobName').value = job.name || '';
        document.getElementById('jobSchedule').value = job.schedule || '';
        document.getElementById('jobAgent').value = job.agent_id || 'main';
        document.getElementById('jobPayloadType').value = job.payload_type || 'prompt';
        document.getElementById('jobPayload').value = job.payload || '';
        document.getElementById('jobSessionMode').value = job.session_mode || 'isolated';

        openModal();
    }

    // ── History ─────────────────────────────────────────────────
    async function toggleHistory(id) {
        const row = document.getElementById(`history-${id}`);
        if (row.style.display === 'none') {
            row.style.display = '';
            const content = document.getElementById(`history-content-${id}`);
            try {
                const resp = await fetch(`${API}/jobs/${id}/history?limit=10`);
                const data = await resp.json();
                const runs = data.runs || data || [];
                if (!runs.length) {
                    content.innerHTML = '<em style="color:var(--text-muted);">No execution history yet.</em>';
                    return;
                }
                content.innerHTML = `
                    <table class="history-table">
                        <thead><tr><th>Time</th><th>Status</th><th>Duration</th><th>Error</th></tr></thead>
                        <tbody>
                            ${runs.map(r => `
                                <tr>
                                    <td>${new Date(r.executed_at || r.timestamp).toLocaleString()}</td>
                                    <td><span class="status-badge ${r.status}">${r.status}</span></td>
                                    <td>${r.duration_ms ? r.duration_ms + 'ms' : '—'}</td>
                                    <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;">${esc(r.error || '—')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            } catch(e) {
                content.innerHTML = `<em style="color:#ff4444;">Failed to load history: ${e.message}</em>`;
            }
        } else {
            row.style.display = 'none';
        }
    }

    // ── Modal ───────────────────────────────────────────────────
    function openModal() {
        if (!document.getElementById('editJobId').value) {
            document.getElementById('modalTitle').textContent = 'Add Cron Job';
            document.getElementById('jobName').value = '';
            document.getElementById('jobSchedule').value = '';
            document.getElementById('jobPayload').value = '';
            document.getElementById('editJobId').value = '';
        }
        document.getElementById('cronModal').classList.add('active');
    }

    function closeModal() {
        document.getElementById('cronModal').classList.remove('active');
        document.getElementById('editJobId').value = '';
    }

    // Close modal on overlay click
    document.getElementById('cronModal').addEventListener('click', function(e) {
        if (e.target === this) closeModal();
    });

    // ── Utils ───────────────────────────────────────────────────
    function setCron(expr) {
        document.getElementById('jobSchedule').value = expr;
    }

    function cronToHuman(expr) {
        if (!expr) return '';
        const presets = {
            '* * * * *': 'Every minute',
            '*/5 * * * *': 'Every 5 minutes',
            '*/15 * * * *': 'Every 15 minutes',
            '*/30 * * * *': 'Every 30 minutes',
            '0 * * * *': 'Every hour',
            '0 */2 * * *': 'Every 2 hours',
            '0 */4 * * *': 'Every 4 hours',
            '0 */6 * * *': 'Every 6 hours',
            '0 0 * * *': 'Daily at midnight',
            '0 6 * * *': 'Daily at 6am',
            '0 0 * * 0': 'Weekly (Sunday)',
            '0 0 * * 1': 'Weekly (Monday)',
            '0 0 1 * *': 'Monthly',
        };
        return presets[expr] || expr;
    }

    function esc(str) {
        if (!str) return '';
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    // ── Exports ─────────────────────────────────────────────────
    window.loadCronJobs = loadCronJobs;
    window.toggleJob = toggleJob;
    window.triggerJob = triggerJob;
    window.deleteJob = deleteJob;
    window.editJob = editJob;
    window.saveJob = saveJob;
    window.toggleHistory = toggleHistory;
    window.openModal = openModal;
    window.closeModal = closeModal;
    window.setCron = setCron;
})();
</script>
{% endblock %}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | UI calls /api/engine/cron endpoints |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in UI |
| 3 | models.yaml single source of truth | ❌ | No model access |
| 4 | Docker-first testing | ✅ | Flask serves template |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S3-03 (Cron CRUD API endpoints at `/api/engine/cron/jobs`)
- S6-06 (Flask route for `/operations/cron/` already added)

## Verification
```bash
# 1. Page renders:
curl -s http://aria-web:5000/operations/cron/ | grep -c "Cron Jobs"
# EXPECTED: 1

# 2. Table structure:
curl -s http://aria-web:5000/operations/cron/ | grep -c "cronTable"
# EXPECTED: at least 1

# 3. Modal exists:
curl -s http://aria-web:5000/operations/cron/ | grep -c "cronModal"
# EXPECTED: at least 2

# 4. API endpoint called:
curl -s http://aria-web:5000/operations/cron/ | grep -c "/api/engine/cron"
# EXPECTED: at least 1
```

## Prompt for Agent
```
Build the cron management web page for Aria operations dashboard.

FILES TO READ FIRST:
- src/web/templates/base.html (full file — base template)
- src/web/app.py (find /operations/cron/ route)
- src/api/routers/cron.py (cron CRUD API endpoints)
- aria_mind/cron_jobs.yaml (existing cron job definitions)

STEPS:
1. Create src/web/templates/engine_operations.html extending base.html
2. Build table showing all cron jobs with columns: name, schedule, agent, enabled, last run, next run, stats, actions
3. Implement Add/Edit modal with cron expression helper presets
4. Implement toggle (enable/disable), trigger (run now), delete
5. Implement expandable history per job
6. Style with existing CSS variables
7. Make responsive

CONSTRAINTS:
- All data via /api/engine/cron/jobs endpoints
- Toggle must use PATCH, not full PUT
- History must be lazy-loaded on expand
- Modal must support both add and edit
```
