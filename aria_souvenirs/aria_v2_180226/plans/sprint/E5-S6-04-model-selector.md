# S6-04: Model Selector Dropdown in Chat
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P1 | **Points:** 2 | **Phase:** 6

## Problem
Users need to select which LLM model to use for their chat session. The model selector needs to be populated from `models.yaml` via the API, show model metadata (provider, context length), and allow mid-session model switching.

## Root Cause
OpenClaw had its own model selection UI. With OpenClaw removed, the chat UI (S6-01) includes a basic `<select>` placeholder for model selection, but it needs proper population from the API, model metadata display, and session-level model switching logic.

## Fix

### 1. Enhanced Model Selector Component — JavaScript module

```html
<!-- Add to engine_chat.html in extra_js block -->
<script>
(function() {
    'use strict';

    /**
     * ModelSelector — Populated from models.yaml via /api/models/available.
     *
     * Features:
     * - Grouped by provider (Ollama, LiteLLM, Cloud)
     * - Shows context window size and capabilities
     * - Persists selection to current session
     * - Shows current model info in chat header
     */

    let modelsData = [];
    let selectedModel = '';

    document.addEventListener('DOMContentLoaded', () => {
        loadModelsEnhanced();
    });

    async function loadModelsEnhanced() {
        const select = document.getElementById('modelSelector');
        const infoEl = document.getElementById('modelInfo');

        try {
            const resp = await fetch('/api/models/available');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            modelsData = data.models || data || [];

            // Clear and rebuild
            select.innerHTML = '';

            // Group by provider
            const groups = {};
            modelsData.forEach(m => {
                const provider = m.provider || m.litellm_provider || 'other';
                if (!groups[provider]) groups[provider] = [];
                groups[provider].push(m);
            });

            // Build optgroups
            const providerOrder = ['ollama', 'litellm', 'openrouter', 'moonshot', 'other'];
            const providerLabels = {
                ollama: '🖥️ Ollama (Local)',
                litellm: '🔀 LiteLLM',
                openrouter: '🌐 OpenRouter',
                moonshot: '🌙 Moonshot',
                other: '📦 Other',
            };

            // Add "Auto (Agent Default)" option
            const autoOpt = document.createElement('option');
            autoOpt.value = '';
            autoOpt.textContent = '🤖 Auto (Agent Default)';
            select.appendChild(autoOpt);

            providerOrder.forEach(provider => {
                const models = groups[provider];
                if (!models || !models.length) return;

                const group = document.createElement('optgroup');
                group.label = providerLabels[provider] || provider;

                models.forEach(m => {
                    const opt = document.createElement('option');
                    const id = m.model_id || m.id || m;
                    opt.value = id;

                    // Build display name with context info
                    const name = m.display_name || m.name || id;
                    const ctx = m.context_length || m.max_tokens;
                    const ctxStr = ctx ? ` (${formatNum(ctx)} ctx)` : '';
                    const caps = [];
                    if (m.tool_calling) caps.push('🔧');
                    if (m.thinking) caps.push('💭');
                    if (m.vision) caps.push('👁️');

                    opt.textContent = `${name}${ctxStr} ${caps.join('')}`;
                    opt.title = [
                        `Model: ${id}`,
                        ctx ? `Context: ${formatNum(ctx)} tokens` : '',
                        m.tool_calling ? 'Supports tool calling' : '',
                        m.thinking ? 'Supports thinking/reasoning' : '',
                        m.vision ? 'Supports vision' : '',
                    ].filter(Boolean).join('\n');

                    group.appendChild(opt);
                });

                select.appendChild(group);
            });

            // Also handle ungrouped models
            Object.keys(groups).forEach(provider => {
                if (!providerOrder.includes(provider)) {
                    const models = groups[provider];
                    const group = document.createElement('optgroup');
                    group.label = `📦 ${provider}`;
                    models.forEach(m => {
                        const opt = document.createElement('option');
                        opt.value = m.model_id || m.id || m;
                        opt.textContent = m.display_name || m.name || opt.value;
                        group.appendChild(opt);
                    });
                    select.appendChild(group);
                }
            });

            // Restore selection
            if (selectedModel && select.querySelector(`option[value="${selectedModel}"]`)) {
                select.value = selectedModel;
            }

            // Update info display
            updateModelInfo();

            // Listen for changes
            select.onchange = () => {
                selectedModel = select.value;
                currentModel = selectedModel; // Update global from S6-01
                updateModelInfo();
                updateSessionModel();
            };

        } catch(e) {
            console.warn('Failed to load models:', e);
            select.innerHTML = '<option value="">Models unavailable</option>';
        }
    }

    function updateModelInfo() {
        const infoEl = document.getElementById('modelInfo');
        if (!infoEl) return;

        if (!selectedModel) {
            infoEl.textContent = 'Model: Agent default';
            return;
        }

        const model = modelsData.find(m =>
            (m.model_id || m.id) === selectedModel
        );

        if (model) {
            const ctx = model.context_length || model.max_tokens;
            const provider = model.provider || '?';
            infoEl.textContent = `${provider} · ${ctx ? formatNum(ctx) + ' ctx' : ''}`;
        } else {
            infoEl.textContent = selectedModel;
        }
    }

    async function updateSessionModel() {
        // If we have an active session, update its model
        if (!sessionId || !selectedModel) return;

        try {
            await fetch(`/api/engine/sessions/${sessionId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: selectedModel }),
            });
        } catch(e) {
            console.warn('Failed to update session model:', e);
        }
    }

    function formatNum(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(0) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
        return n.toString();
    }

    // Export
    window.loadModelsEnhanced = loadModelsEnhanced;
})();
</script>
```

### 2. Enhanced CSS for model selector

```css
/* ── Model Selector Enhancements ─────────────────────────────── */
#modelSelector {
    min-width: 180px;
    max-width: 280px;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 6px;
    padding: 6px 10px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.8rem;
    font-family: inherit;
    cursor: pointer;
    appearance: none;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 16 16' fill='%23888'%3E%3Cpath d='M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 10px center;
    padding-right: 28px;
}

#modelSelector:focus {
    border-color: var(--accent-primary, #6c5ce7);
    outline: none;
}

#modelSelector optgroup {
    font-weight: 600;
    color: var(--text-muted, #888);
    font-size: 0.75rem;
    padding-top: 8px;
}

#modelSelector option {
    padding: 4px 8px;
    color: var(--text-primary, #e0e0e0);
    background: var(--bg-secondary, #1a1a2e);
}

#modelInfo {
    font-size: 0.7rem;
    color: var(--text-muted, #888);
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Fetches models from /api/models/available |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ✅ | API populates from models.yaml |
| 4 | Docker-first testing | ✅ | Part of Flask template |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S6-01 (Chat UI — model selector is part of chat header)
- Existing `/api/models/available` endpoint (already exists)

## Verification
```bash
# 1. Model selector exists:
curl -s http://aria-web:5000/chat/ | grep -c "modelSelector"
# EXPECTED: at least 2

# 2. API endpoint responds:
curl -s http://aria-api:8000/models/available | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('models',d)))"
# EXPECTED: positive number

# 3. Optgroup grouping present:
curl -s http://aria-web:5000/chat/ | grep -c "optgroup"
# EXPECTED: 0 (generated dynamically, not in static HTML)
```

## Prompt for Agent
```
Implement the model selector dropdown for the Aria chat UI.

FILES TO READ FIRST:
- src/web/templates/engine_chat.html (full file — chat UI, find #modelSelector)
- aria_models/models.yaml (first 50 lines — model structure)
- src/api/routers/models.py (model endpoints — /models/available)

STEPS:
1. Read engine_chat.html to find the model selector placeholder
2. Implement loadModelsEnhanced() to fetch and display models
3. Group models by provider in optgroup elements
4. Show capabilities (tool calling, thinking, vision) as emoji indicators
5. Show context window size per model
6. Implement updateSessionModel() to PATCH session on model change
7. Maintain "Auto (Agent Default)" as first option
8. Add enhanced CSS for the selector

CONSTRAINTS:
- Constraint 3: All model data comes from /api/models/available (sourced from models.yaml)
- Must handle API failures gracefully
- Must preserve selection across page interactions
```
