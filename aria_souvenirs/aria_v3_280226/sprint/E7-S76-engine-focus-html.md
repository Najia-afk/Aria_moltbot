# S-76: engine_focus.html — Focus Profile Management UI

**Epic:** E7 — Focus System v2 | **Priority:** P2 | **Points:** 3 | **Phase:** 4

---

## Problem

`aria_engine.focus_profiles` table (created S-70, seeded S-71) is live in DB.
The CRUD API router `engine_focus.py` (created S-71) is registered at
`/api/engine/focus`. However, there is **no management page** — the only way
to view or edit focus profiles is via raw API calls. Operators cannot:

- See which profiles are enabled / disabled
- View token_budget_hint visually as a heat bar
- See delegation level (L1/L2/L3) at a glance
- Edit `system_prompt_addon` without raw JSON
- Add keywords to `expertise_keywords` array

---

## New File

**Path:** `src/web/templates/engine_focus.html`

---

## Full File Content

```html
{% extends "base.html" %}
{% block title %}Focus Profiles — Aria Engine{% endblock %}

{% block head %}
<style>
    .focus-card {
        background: #fff;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 14px;
        transition: box-shadow 0.15s;
    }
    .focus-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
    .focus-card.disabled-card { opacity: 0.55; }
    .badge-l1 { background: #8b5cf6; }
    .badge-l2 { background: #0d6efd; }
    .badge-l3 { background: #6c757d; }
    .level-badge {
        display: inline-block;
        font-size: 0.7rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 20px;
        color: #fff;
        letter-spacing: 0.5px;
    }
    .budget-bar-wrap { background: #e9ecef; border-radius: 4px; height: 6px; margin-top: 4px; }
    .budget-bar { height: 6px; border-radius: 4px; background: linear-gradient(to right, #28a745, #ffc107, #dc3545); }
    .keyword-chip {
        display: inline-block;
        background: #e9f2ff;
        color: #0d6efd;
        border-radius: 20px;
        padding: 1px 9px;
        font-size: 0.75rem;
        margin: 2px;
    }
    .addon-preview {
        font-family: monospace;
        font-size: 0.8rem;
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 6px;
        padding: 8px 12px;
        max-height: 80px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: pre-wrap;
        cursor: pointer;
        color: #495057;
    }
    .tone-tag {
        font-size: 0.75rem;
        background: #fff3cd;
        color: #856404;
        border-radius: 4px;
        padding: 1px 7px;
        margin-right: 4px;
    }
</style>
{% endblock %}

{% block content %}
<div class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
            <h4 class="mb-0">🎭 Focus Profiles</h4>
            <small class="text-muted">
                <span id="totalCount">0</span> profiles |
                <span id="enabledCount">0</span> enabled
            </small>
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-secondary" onclick="loadProfiles()">🔄 Refresh</button>
            <button class="btn btn-sm btn-success" onclick="openNew()">+ New Profile</button>
        </div>
    </div>

    <div id="profileGrid" class="row g-3">
        <div class="col-12 text-muted p-3">Loading...</div>
    </div>
</div>

<!-- Edit Modal -->
<div class="modal fade" id="editModal" tabindex="-1">
  <div class="modal-dialog modal-lg modal-dialog-scrollable">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="editModalTitle">Focus Profile</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <form id="editForm">
          <input type="hidden" id="fld_focus_id">

          <div class="row g-3">
            <div class="col-md-6">
              <label class="form-label fw-semibold">Focus ID <span class="text-danger">*</span></label>
              <input type="text" class="form-control form-control-sm" id="fld_focus_id_vis" placeholder="e.g. devsecops">
            </div>
            <div class="col-md-6">
              <label class="form-label fw-semibold">Display Name</label>
              <input type="text" class="form-control form-control-sm" id="fld_display_name" placeholder="DevSecOps Specialist">
            </div>

            <div class="col-md-3">
              <label class="form-label fw-semibold">Delegation Level</label>
              <select class="form-select form-select-sm" id="fld_delegation_level">
                <option value="1">L1 — Orchestrator</option>
                <option value="2" selected>L2 — Specialist</option>
                <option value="3">L3 — Ephemeral</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label fw-semibold">Token Budget</label>
              <input type="number" class="form-control form-control-sm" id="fld_token_budget_hint" min="100" max="8000" step="100" value="2000">
            </div>
            <div class="col-md-3">
              <label class="form-label fw-semibold">Tone</label>
              <input type="text" class="form-control form-control-sm" id="fld_tone" placeholder="assertive">
            </div>
            <div class="col-md-3">
              <label class="form-label fw-semibold">Style</label>
              <input type="text" class="form-control form-control-sm" id="fld_style" placeholder="technical">
            </div>

            <div class="col-md-4">
              <label class="form-label fw-semibold">Temperature Delta</label>
              <input type="number" class="form-control form-control-sm" id="fld_temperature_delta" min="-0.5" max="0.5" step="0.05" value="0">
              <div class="form-text">Added to agent's base temperature (clamped 0–1)</div>
            </div>
            <div class="col-md-4">
              <label class="form-label fw-semibold">Model Override</label>
              <input type="text" class="form-control form-control-sm" id="fld_model_override" placeholder="(leave blank = use agent default)">
            </div>
            <div class="col-md-4">
              <label class="form-label fw-semibold">Enabled</label>
              <div class="form-check mt-2">
                <input class="form-check-input" type="checkbox" id="fld_enabled" checked>
                <label class="form-check-label" for="fld_enabled">Active</label>
              </div>
            </div>

            <div class="col-12">
              <label class="form-label fw-semibold">Expertise Keywords <span class="text-muted">(comma-separated)</span></label>
              <input type="text" class="form-control form-control-sm" id="fld_keywords" placeholder="deploy, docker, security, ci, cd">
              <div class="form-text">Used for DB-driven routing (S-72). Each word becomes a regex alternation.</div>
            </div>

            <div class="col-12">
              <label class="form-label fw-semibold">Auto Skills <span class="text-muted">(comma-separated skill IDs)</span></label>
              <input type="text" class="form-control form-control-sm" id="fld_auto_skills" placeholder="shell_exec, knowledge_query">
            </div>

            <div class="col-12">
              <label class="form-label fw-semibold">System Prompt Addon</label>
              <textarea class="form-control form-control-sm font-monospace"
                        id="fld_system_prompt_addon" rows="6"
                        placeholder="Additional instructions appended to agent system prompt when this focus is active..."></textarea>
              <div class="form-text">Appended additive to agent's system_prompt — never replaces it.</div>
            </div>
          </div>
        </form>
      </div>
      <div class="modal-footer">
        <button class="btn btn-sm btn-outline-danger" id="btnDelete" onclick="deleteProfile()">🗑 Delete</button>
        <button class="btn btn-sm btn-secondary" data-bs-dismiss="modal">Cancel</button>
        <button class="btn btn-sm btn-primary" onclick="saveProfile()">💾 Save</button>
      </div>
    </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script>
const API = '/api/engine/focus';
let profiles = [];
let editingId = null;

const LEVEL_LABELS = { 1: 'L1', 2: 'L2', 3: 'L3' };
const LEVEL_CLASSES = { 1: 'badge-l1', 2: 'badge-l2', 3: 'badge-l3' };

/* ─── Budget bar ─── */
function budgetBar(hint) {
    const MAX = 4000;
    const pct = Math.min(100, Math.round((hint / MAX) * 100));
    const color = hint <= 1000 ? '#28a745' : hint <= 2000 ? '#ffc107' : '#dc3545';
    return `
        <div class="d-flex justify-content-between mt-1" style="font-size:0.75rem">
            <span class="text-muted">0</span>
            <span class="fw-semibold">${hint.toLocaleString()} tokens</span>
            <span class="text-muted">4k</span>
        </div>
        <div class="budget-bar-wrap">
            <div class="budget-bar" style="width:${pct}%; background:${color}"></div>
        </div>`;
}

/* ─── Render grid ─── */
function renderProfiles(data) {
    profiles = data;
    document.getElementById('totalCount').textContent = data.length;
    document.getElementById('enabledCount').textContent = data.filter(p => p.enabled).length;

    const grid = document.getElementById('profileGrid');
    if (!data.length) {
        grid.innerHTML = '<div class="col-12 text-muted">No focus profiles found. Create one or run the seed endpoint.</div>';
        return;
    }

    grid.innerHTML = data.map(p => {
        const lvl = p.delegation_level || 2;
        const keywords = (p.expertise_keywords || []).slice(0, 8);
        const extraKw = (p.expertise_keywords || []).length - 8;
        const chips = keywords.map(k => `<span class="keyword-chip">${k}</span>`).join('') +
                      (extraKw > 0 ? `<span class="keyword-chip text-muted">+${extraKw}</span>` : '');
        const addon = (p.system_prompt_addon || '').trim().slice(0, 180) + (p.system_prompt_addon?.length > 180 ? '…' : '');

        return `
        <div class="col-md-6 col-xl-4">
          <div class="focus-card ${p.enabled ? '' : 'disabled-card'}">
            <div class="d-flex justify-content-between align-items-start mb-1">
              <div>
                <span class="level-badge ${LEVEL_CLASSES[lvl]}">${LEVEL_LABELS[lvl]}</span>
                <strong class="ms-2">${p.display_name || p.focus_id}</strong>
                <code class="ms-1 text-muted" style="font-size:0.75rem">${p.focus_id}</code>
              </div>
              <div>
                ${p.enabled
                    ? '<span class="badge bg-success" style="font-size:0.7rem">active</span>'
                    : '<span class="badge bg-secondary" style="font-size:0.7rem">disabled</span>'}
              </div>
            </div>

            <div class="mb-2">
              ${p.tone ? `<span class="tone-tag">tone: ${p.tone}</span>` : ''}
              ${p.style ? `<span class="tone-tag" style="background:#f0fff4;color:#155724">style: ${p.style}</span>` : ''}
              ${p.model_override ? `<span class="tone-tag" style="background:#f8f0ff;color:#6610f2">model: ${p.model_override.split('-').slice(-1)[0]}</span>` : ''}
            </div>

            <div class="mb-2">${budgetBar(p.token_budget_hint || 0)}</div>

            <div class="mb-2 mt-2">${chips || '<span class="text-muted" style="font-size:0.8rem">No keywords</span>'}</div>

            ${addon ? `<div class="addon-preview" onclick="editProfile('${p.focus_id}')">${addon}</div>` : ''}

            <div class="d-flex justify-content-end mt-2 gap-2">
              <button class="btn btn-sm btn-outline-primary py-0" onclick="editProfile('${p.focus_id}')">✏️ Edit</button>
            </div>
          </div>
        </div>`;
    }).join('');
}

/* ─── Load ─── */
async function loadProfiles() {
    try {
        const resp = await fetch(API);
        const data = await resp.json();
        renderProfiles(data.profiles || data);
    } catch (e) {
        document.getElementById('profileGrid').innerHTML = '<div class="col-12 text-danger">Failed to load focus profiles: ' + e.message + '</div>';
    }
}

/* ─── Open edit modal ─── */
function editProfile(focusId) {
    const p = profiles.find(x => x.focus_id === focusId);
    if (!p) return;
    editingId = focusId;

    document.getElementById('editModalTitle').textContent = `Edit: ${p.display_name || p.focus_id}`;
    document.getElementById('fld_focus_id').value = p.focus_id;
    document.getElementById('fld_focus_id_vis').value = p.focus_id;
    document.getElementById('fld_focus_id_vis').disabled = true;  // cannot rename
    document.getElementById('fld_display_name').value = p.display_name || '';
    document.getElementById('fld_delegation_level').value = p.delegation_level || 2;
    document.getElementById('fld_token_budget_hint').value = p.token_budget_hint || 2000;
    document.getElementById('fld_tone').value = p.tone || '';
    document.getElementById('fld_style').value = p.style || '';
    document.getElementById('fld_temperature_delta').value = p.temperature_delta || 0;
    document.getElementById('fld_model_override').value = p.model_override || '';
    document.getElementById('fld_enabled').checked = p.enabled !== false;
    document.getElementById('fld_keywords').value = (p.expertise_keywords || []).join(', ');
    document.getElementById('fld_auto_skills').value = (p.auto_skills || []).join(', ');
    document.getElementById('fld_system_prompt_addon').value = p.system_prompt_addon || '';
    document.getElementById('btnDelete').style.display = '';

    new bootstrap.Modal(document.getElementById('editModal')).show();
}

/* ─── New profile ─── */
function openNew() {
    editingId = null;
    document.getElementById('editModalTitle').textContent = 'New Focus Profile';
    document.getElementById('editForm').reset();
    document.getElementById('fld_focus_id_vis').disabled = false;
    document.getElementById('fld_enabled').checked = true;
    document.getElementById('fld_delegation_level').value = 2;
    document.getElementById('fld_token_budget_hint').value = 2000;
    document.getElementById('btnDelete').style.display = 'none';
    new bootstrap.Modal(document.getElementById('editModal')).show();
}

/* ─── Save ─── */
async function saveProfile() {
    const isEdit = !!editingId;
    const focusId = editingId || document.getElementById('fld_focus_id_vis').value.trim();
    if (!focusId) { alert('Focus ID is required.'); return; }

    const payload = {
        display_name:         document.getElementById('fld_display_name').value.trim() || null,
        delegation_level:     parseInt(document.getElementById('fld_delegation_level').value),
        token_budget_hint:    parseInt(document.getElementById('fld_token_budget_hint').value),
        tone:                 document.getElementById('fld_tone').value.trim() || null,
        style:                document.getElementById('fld_style').value.trim() || null,
        temperature_delta:    parseFloat(document.getElementById('fld_temperature_delta').value),
        model_override:       document.getElementById('fld_model_override').value.trim() || null,
        enabled:              document.getElementById('fld_enabled').checked,
        expertise_keywords:   document.getElementById('fld_keywords').value.split(',').map(s=>s.trim()).filter(Boolean),
        auto_skills:          document.getElementById('fld_auto_skills').value.split(',').map(s=>s.trim()).filter(Boolean),
        system_prompt_addon:  document.getElementById('fld_system_prompt_addon').value.trim() || null,
    };

    try {
        let resp;
        if (isEdit) {
            resp = await fetch(`${API}/${focusId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
        } else {
            resp = await fetch(API, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ focus_id: focusId, ...payload }),
            });
        }
        if (!resp.ok) throw new Error(await resp.text());

        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
        await loadProfiles();
    } catch (e) {
        alert('Save failed: ' + e.message);
    }
}

/* ─── Delete ─── */
async function deleteProfile() {
    if (!editingId) return;
    if (!confirm(`Delete focus profile "${editingId}"? This cannot be undone.`)) return;
    try {
        const resp = await fetch(`${API}/${editingId}`, { method: 'DELETE' });
        if (!resp.ok) throw new Error(await resp.text());
        bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
        await loadProfiles();
    } catch (e) {
        alert('Delete failed: ' + e.message);
    }
}

/* ─── Init ─── */
document.addEventListener('DOMContentLoaded', loadProfiles);
</script>
{% endblock %}
```

---

## Route Registration

**File:** `src/api/main.py` — find the HTML template routes section (search for
`engine_agents` route registered as a GET returning `TemplateResponse`) and add:

```python
@app.get("/engine/focus", response_class=HTMLResponse)
async def engine_focus_page(request: Request):
    return templates.TemplateResponse("engine_focus.html", {"request": request})
```

## Navigation Link

**File:** `src/web/templates/base.html` — find the sidebar nav list and add:

```html
<li class="nav-item">
    <a class="nav-link" href="/engine/focus">🎭 Focus Profiles</a>
</li>
```

---

## Constraints

| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | All fields from S-70 schema visible | ✅ | All 13 user-editable fields present in modal |
| 2 | Additive prompt note visible | ✅ | Form text explains addon is appended, never replaces |
| 3 | Token budget visual | ✅ | Heat bar with green→yellow→red gradient |
| 4 | L1/L2/L3 color-coded | ✅ | Purple/Blue/Gray badges |
| 5 | No inline credentials | ✅ | API calls only to `/api/engine/focus` |
| 6 | No soul files touched | ✅ | None |

---

## Dependencies

- **S-71** — `engine_focus.py` CRUD API must be registered at `/api/engine/focus`

---

## Verification

```bash
# 1. Template renders without Jinja errors
docker exec aria-api curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/engine/focus
# EXPECTED: 200

# 2. Page loads all profiles
docker exec aria-api curl -s http://localhost:8000/engine/focus | grep -c "focus-card"
# EXPECTED: 8  (one card per seeded profile)

# 3. Edit modal fields all present in HTML source
docker exec aria-api curl -s http://localhost:8000/engine/focus | \
    grep -E 'fld_token_budget_hint|fld_delegation_level|fld_system_prompt_addon|fld_keywords'
# EXPECTED: 4 lines returned (one per field ID)
```

---

## Prompt for Agent

You are executing ticket S-76 for the Aria project.

**Constraint:** The template must extend `base.html` using the same pattern as `engine_agents.html`. No inline CDN imports unless the base template already includes Bootstrap. Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `src/web/templates/base.html` — confirm Bootstrap version and any shared layout
- `src/web/templates/engine_agents.html` — reference pattern
- `src/api/main.py` — find HTML GET route registration pattern

**Steps:**
1. Create `src/web/templates/engine_focus.html` with the full content shown above.
2. Add `GET /engine/focus` route in `src/api/main.py`.
3. Add `🎭 Focus Profiles` nav link to `base.html` sidebar.
4. Run all 3 verification commands.
5. Report: "S-76 DONE — Focus profile management UI live at /engine/focus, 8 cards rendered, modal fully wired."
