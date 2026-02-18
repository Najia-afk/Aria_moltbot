# S7-03: System Prompt Editor per Agent
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P2 | **Points:** 3 | **Phase:** 7

## Problem
Agent system prompts need a web-based editor. Currently, system prompts are assembled from Soul files + agent config, but there's no UI to view or edit the per-agent system prompt stored in `aria_engine.agent_state.system_prompt`.

## Root Cause
System prompts were static files mounted into OpenClaw containers. The new engine stores them in the database (`aria_engine.agent_state.system_prompt`), but no editor UI exists. Users need to see the full assembled prompt (Soul + Focus + custom text) and edit the custom portion.

## Fix

### 1. Flask Route — already added in S6-06
```python
@app.route('/operations/agents/<agent_id>/prompt')
def operations_agent_prompt(agent_id):
    return render_template('engine_prompt_editor.html', agent_id=agent_id)
```

### 2. Template — `src/web/templates/engine_prompt_editor.html`

```html
{% extends "base.html" %}
{% block title %}Aria — Prompt Editor: {{ agent_id }}{% endblock %}

{% block extra_css %}
<!-- CodeMirror for text editing -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css">
<style>
/* ── Prompt Editor Layout ────────────────────────────────────── */
.prompt-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 64px);
    overflow: hidden;
}

.prompt-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
    background: var(--bg-secondary, #1a1a2e);
    gap: 12px;
    flex-wrap: wrap;
}

.prompt-toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.prompt-toolbar h2 {
    margin: 0;
    font-size: 1.1rem;
    color: var(--text-primary, #e0e0e0);
}

.prompt-toolbar .agent-badge {
    background: rgba(108, 92, 231, 0.2);
    color: var(--accent-primary, #6c5ce7);
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
}

.prompt-toolbar-actions {
    display: flex;
    gap: 8px;
}

.btn {
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
    display: flex;
    align-items: center;
    gap: 6px;
}

.btn-primary { background: var(--accent-primary, #6c5ce7); color: white; }
.btn-primary:hover { background: #5a4bd6; }
.btn-secondary { background: var(--bg-tertiary, #2a2a3e); color: var(--text-primary, #e0e0e0); border: 1px solid var(--border-color, #3a3a5e); }
.btn-secondary:hover { background: var(--bg-secondary, #1a1a2e); }

.save-status {
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    display: flex;
    align-items: center;
    gap: 4px;
}

.save-status.saved { color: #00d26a; }
.save-status.unsaved { color: #ffc107; }
.save-status.error { color: #ff4444; }

/* ── Editor Area ─────────────────────────────────────────────── */
.prompt-content {
    display: flex;
    flex: 1;
    overflow: hidden;
}

.editor-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.editor-tabs {
    display: flex;
    background: var(--bg-tertiary, #2a2a3e);
    border-bottom: 1px solid var(--border-color, #3a3a5e);
    padding: 0 12px;
}

.editor-tab {
    padding: 10px 16px;
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    background: none;
    border-top: none;
    border-left: none;
    border-right: none;
    font-family: inherit;
}

.editor-tab:hover { color: var(--text-primary, #e0e0e0); }
.editor-tab.active { color: var(--accent-primary, #6c5ce7); border-bottom-color: var(--accent-primary, #6c5ce7); }

.editor-wrapper {
    flex: 1;
    overflow: hidden;
}

.CodeMirror {
    height: 100% !important;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    line-height: 1.6;
}

/* ── Preview Panel ───────────────────────────────────────────── */
.preview-panel {
    width: 400px;
    border-left: 1px solid var(--border-color, #2a2a3e);
    background: var(--bg-secondary, #1a1a2e);
    overflow-y: auto;
    padding: 20px;
    display: none;
}

.preview-panel.visible { display: block; }

.preview-panel h3 {
    margin: 0 0 12px;
    font-size: 0.9rem;
    color: var(--text-primary, #e0e0e0);
}

.preview-content {
    font-size: 0.8rem;
    line-height: 1.6;
    color: var(--text-primary, #e0e0e0);
    white-space: pre-wrap;
    font-family: 'JetBrains Mono', monospace;
}

.preview-section {
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
}

.preview-section-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--text-muted, #888);
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}

/* ── Template Variables ──────────────────────────────────────── */
.template-vars {
    margin-top: 16px;
}

.template-var {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 0;
    font-size: 0.8rem;
    border-bottom: 1px solid rgba(255,255,255,0.03);
}

.template-var-name {
    font-family: 'JetBrains Mono', monospace;
    color: var(--accent-primary, #6c5ce7);
    font-size: 0.75rem;
}

.template-var-value {
    color: var(--text-muted, #888);
    font-size: 0.75rem;
}

/* ── Stats Bar ───────────────────────────────────────────────── */
.prompt-stats {
    display: flex;
    gap: 16px;
    padding: 8px 20px;
    background: var(--bg-tertiary, #2a2a3e);
    border-top: 1px solid var(--border-color, #3a3a5e);
    font-size: 0.75rem;
    color: var(--text-muted, #888);
}

@media (max-width: 768px) {
    .preview-panel { display: none !important; }
    .prompt-content { flex-direction: column; }
}
</style>
{% endblock %}

{% block content %}
<div class="prompt-page">
    <!-- Toolbar -->
    <div class="prompt-toolbar">
        <div class="prompt-toolbar-left">
            <a href="/operations/agents/" style="color:var(--text-muted);text-decoration:none;font-size:1.1rem;">←</a>
            <h2>System Prompt Editor</h2>
            <span class="agent-badge">{{ agent_id }}</span>
        </div>
        <div class="prompt-toolbar-actions">
            <span class="save-status" id="saveStatus">Ready</span>
            <button class="btn btn-secondary" onclick="togglePreview()">👁 Preview</button>
            <button class="btn btn-secondary" onclick="resetPrompt()">↻ Reset</button>
            <button class="btn btn-primary" onclick="savePrompt()" id="saveBtn">💾 Save</button>
        </div>
    </div>

    <!-- Editor + Preview -->
    <div class="prompt-content">
        <div class="editor-panel">
            <div class="editor-tabs">
                <button class="editor-tab active" onclick="switchTab('custom', this)">Custom Prompt</button>
                <button class="editor-tab" onclick="switchTab('soul', this)">Soul (read-only)</button>
                <button class="editor-tab" onclick="switchTab('assembled', this)">Assembled (preview)</button>
            </div>
            <div class="editor-wrapper" id="editorWrapper">
                <textarea id="promptEditor"></textarea>
            </div>
        </div>

        <div class="preview-panel" id="previewPanel">
            <h3>Assembled Prompt Preview</h3>
            <div class="preview-section">
                <div class="preview-section-label">Soul</div>
                <div class="preview-content" id="previewSoul">Loading…</div>
            </div>
            <div class="preview-section">
                <div class="preview-section-label">Custom System Prompt</div>
                <div class="preview-content" id="previewCustom"></div>
            </div>
            <div class="template-vars">
                <div class="preview-section-label">Template Variables</div>
                <div id="templateVarsList"></div>
            </div>
        </div>
    </div>

    <!-- Stats Bar -->
    <div class="prompt-stats">
        <span>Characters: <strong id="charCount">0</strong></span>
        <span>Words: <strong id="wordCount">0</strong></span>
        <span>Estimated tokens: <strong id="tokenCount">0</strong></span>
        <span>Agent: <strong>{{ agent_id }}</strong></span>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/markdown/markdown.min.js"></script>
<script>
(function() {
    'use strict';

    const agentId = '{{ agent_id }}';
    const API = '/api/engine';
    let editor = null;
    let originalPrompt = '';
    let soulContent = '';
    let currentTab = 'custom';
    let hasChanges = false;

    document.addEventListener('DOMContentLoaded', () => {
        initEditor();
        loadPrompt();
        loadSoul();
        loadTemplateVars();
    });

    function initEditor() {
        editor = CodeMirror.fromTextArea(document.getElementById('promptEditor'), {
            mode: 'markdown',
            theme: 'material-darker',
            lineNumbers: true,
            lineWrapping: true,
            autofocus: true,
            tabSize: 2,
            indentWithTabs: false,
            placeholder: 'Enter system prompt for this agent…',
        });

        editor.on('change', () => {
            hasChanges = editor.getValue() !== originalPrompt;
            updateSaveStatus();
            updateStats();
            updatePreview();
        });

        // Keyboard shortcut: Ctrl+S to save
        editor.setOption('extraKeys', {
            'Ctrl-S': () => savePrompt(),
            'Cmd-S': () => savePrompt(),
        });
    }

    async function loadPrompt() {
        try {
            const resp = await fetch(`${API}/agents/${agentId}`);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            originalPrompt = data.system_prompt || '';
            editor.setValue(originalPrompt);
            hasChanges = false;
            updateSaveStatus();
            updateStats();
        } catch(e) {
            console.error('Failed to load prompt:', e);
            setSaveStatus('error', 'Failed to load prompt');
        }
    }

    async function loadSoul() {
        try {
            const resp = await fetch(`${API}/agents/${agentId}/assembled-prompt`);
            if (resp.ok) {
                const data = await resp.json();
                soulContent = data.soul_content || '';
                document.getElementById('previewSoul').textContent = soulContent || '(no soul content)';
            }
        } catch(e) {
            document.getElementById('previewSoul').textContent = '(failed to load)';
        }
    }

    async function loadTemplateVars() {
        try {
            const resp = await fetch(`${API}/agents/${agentId}/template-vars`);
            if (resp.ok) {
                const data = await resp.json();
                const vars = data.variables || {};
                const container = document.getElementById('templateVarsList');
                container.innerHTML = Object.entries(vars).map(([k, v]) => `
                    <div class="template-var">
                        <span class="template-var-name">{{ '{{' }}${k}{{ '}}' }}</span>
                        <span class="template-var-value">${esc(String(v).substring(0, 50))}</span>
                    </div>
                `).join('') || '<div style="color:var(--text-muted);font-size:0.8rem;">No template variables.</div>';
            }
        } catch(e) { /* ignore */ }
    }

    async function savePrompt() {
        try {
            setSaveStatus('saving', 'Saving…');
            const prompt = editor.getValue();
            const resp = await fetch(`${API}/agents/${agentId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ system_prompt: prompt }),
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            originalPrompt = prompt;
            hasChanges = false;
            setSaveStatus('saved', 'Saved ✓');
            setTimeout(() => setSaveStatus('ready', 'Ready'), 2000);
        } catch(e) {
            setSaveStatus('error', 'Save failed: ' + e.message);
        }
    }

    function resetPrompt() {
        if (hasChanges && !confirm('Discard unsaved changes?')) return;
        editor.setValue(originalPrompt);
        hasChanges = false;
        updateSaveStatus();
    }

    function switchTab(tab, btn) {
        currentTab = tab;
        document.querySelectorAll('.editor-tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');

        if (tab === 'custom') {
            editor.setOption('readOnly', false);
            editor.setValue(editor.getValue()); // Refresh
        } else if (tab === 'soul') {
            editor.setOption('readOnly', true);
            editor.setValue(soulContent || '(no soul content loaded)');
        } else if (tab === 'assembled') {
            editor.setOption('readOnly', true);
            const assembled = (soulContent ? soulContent + '\n\n---\n\n' : '') + editor.getValue();
            editor.setValue(assembled);
        }
    }

    function togglePreview() {
        document.getElementById('previewPanel').classList.toggle('visible');
        setTimeout(() => editor.refresh(), 100);
    }

    function updatePreview() {
        const customPrompt = currentTab === 'custom' ? editor.getValue() : originalPrompt;
        document.getElementById('previewCustom').textContent = customPrompt;
    }

    function updateStats() {
        const text = editor.getValue();
        document.getElementById('charCount').textContent = text.length;
        document.getElementById('wordCount').textContent = text.split(/\s+/).filter(w => w).length;
        document.getElementById('tokenCount').textContent = Math.ceil(text.length / 4); // Rough estimate
    }

    function updateSaveStatus() {
        if (hasChanges) {
            setSaveStatus('unsaved', '● Unsaved changes');
        } else {
            setSaveStatus('ready', 'Ready');
        }
    }

    function setSaveStatus(state, text) {
        const el = document.getElementById('saveStatus');
        el.className = `save-status ${state}`;
        el.textContent = text;
    }

    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

    // Warn on page leave with unsaved changes
    window.addEventListener('beforeunload', (e) => {
        if (hasChanges) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    window.savePrompt = savePrompt;
    window.resetPrompt = resetPrompt;
    window.switchTab = switchTab;
    window.togglePreview = togglePreview;
})();
</script>
{% endblock %}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Saves via PATCH /api/engine/agents/{id} |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model access |
| 4 | Docker-first testing | ✅ | Flask template + CodeMirror CDN |
| 5 | aria_memories only writable path | ❌ | Writes to DB only |
| 6 | No soul modification | ✅ | Soul is read-only in the editor |

## Dependencies
- S7-02 (Agent page — links to prompt editor)
- S4-01 (Agent pool — PATCH endpoint for system_prompt)
- S2-05 (System prompt assembly — assembled-prompt endpoint)

## Verification
```bash
# 1. Page renders:
curl -s http://aria-web:5000/operations/agents/main/prompt | grep -c "Prompt Editor"
# EXPECTED: 1

# 2. CodeMirror loaded:
curl -s http://aria-web:5000/operations/agents/main/prompt | grep -c "codemirror"
# EXPECTED: at least 2

# 3. Save button exists:
curl -s http://aria-web:5000/operations/agents/main/prompt | grep -c "savePrompt"
# EXPECTED: at least 1
```

## Prompt for Agent
```
Build the system prompt editor for Aria's per-agent prompt management.

FILES TO READ FIRST:
- src/web/templates/base.html (base template)
- aria_mind/soul/SOUL.md (soul file — read-only context)
- aria_engine/agent_pool.py (agent state with system_prompt field)
- src/api/routers/engine.py (PATCH agent endpoint)

STEPS:
1. Create src/web/templates/engine_prompt_editor.html extending base.html
2. Integrate CodeMirror 5.x with markdown mode and material-darker theme
3. Implement three tabs: Custom (editable), Soul (read-only), Assembled (preview)
4. Add save/reset/preview buttons with keyboard shortcut (Ctrl+S)
5. Show character, word, and estimated token counts
6. Implement unsaved changes warning on page leave
7. Add template variables preview panel
8. Make responsive

CONSTRAINTS:
- Soul content is READ-ONLY (Constraint 6)
- Saves to aria_engine.agent_state.system_prompt via PATCH API
- CodeMirror loaded from CDN (no bundling)
- Warn before discarding unsaved changes
```
