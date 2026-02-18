# S6-05: Tool Call Visualization in Chat
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P2 | **Points:** 3 | **Phase:** 6

## Problem
When Aria invokes skills/tools during a chat conversation, the user has no visibility into what's happening. Tool calls need to be visualized as expandable cards showing the tool name, parameters, execution status, and result.

## Root Cause
OpenClaw displayed tool calls in its own format. The new chat UI (S6-01) has basic tool call card structure, but this ticket provides the complete tool visualization component with animated status transitions, JSON formatting, execution timing, and proper integration with the WebSocket stream.

## Fix

### 1. Tool Visualization Component — JavaScript module

```html
<!-- Add to engine_chat.html in extra_js block -->
<script>
(function() {
    'use strict';

    /**
     * ToolVisualizer — Renders tool/skill invocations as expandable cards in chat.
     *
     * WebSocket events handled:
     * - tool_call_start: { id, name, arguments } — tool invocation begins
     * - tool_call_end:   { id, result, error, duration_ms } — tool execution completes
     *
     * Features:
     * - Expandable cards with tool name, formatted parameters, result
     * - Status indicator: pending → executing → complete/error
     * - Animated spinner during execution
     * - Execution duration display
     * - Nested JSON formatting with syntax highlighting
     */
    class ToolVisualizer {
        constructor() {
            this.activeTools = new Map(); // id → { el, startTime }
        }

        /**
         * Create a tool call card when execution starts.
         * @param {HTMLElement} messageBody — the .message-body element to insert into
         * @param {Object} toolCall — { id, name, arguments }
         * @returns {HTMLElement} — the card element
         */
        createToolCard(messageBody, toolCall) {
            const card = document.createElement('div');
            card.className = 'tool-call-card';
            card.id = `tool-${toolCall.id}`;

            const argsFormatted = this._formatJSON(toolCall.arguments);

            card.innerHTML = `
                <div class="tool-call-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <span class="tool-icon">🔧</span>
                    <span class="tool-name">${this._escapeHtml(toolCall.name)}</span>
                    <span class="tool-call-status executing">
                        <span class="tool-spinner"></span>
                        executing
                    </span>
                </div>
                <div class="tool-call-body">
                    <div class="tool-section">
                        <div class="tool-section-label">Parameters</div>
                        <div class="tool-call-params">${argsFormatted}</div>
                    </div>
                    <div class="tool-result-section" style="display:none;">
                        <div class="tool-section-label">Result</div>
                        <div class="tool-call-result"></div>
                    </div>
                    <div class="tool-timing"></div>
                </div>
            `;

            // Insert before the message-content div
            const contentEl = messageBody.querySelector('.message-content');
            if (contentEl) {
                messageBody.insertBefore(card, contentEl);
            } else {
                messageBody.appendChild(card);
            }

            this.activeTools.set(toolCall.id, {
                el: card,
                startTime: Date.now(),
                name: toolCall.name,
            });

            return card;
        }

        /**
         * Update a tool call card when execution completes.
         * @param {Object} result — { id, result, error, duration_ms, status }
         */
        completeToolCall(result) {
            const toolData = this.activeTools.get(result.id);
            if (!toolData) return;

            const card = toolData.el;
            const isError = result.error || result.status === 'error';

            // Update status
            const statusEl = card.querySelector('.tool-call-status');
            statusEl.className = `tool-call-status ${isError ? 'error' : 'complete'}`;
            statusEl.innerHTML = isError ? '✗ error' : '✓ complete';

            // Show result
            const resultSection = card.querySelector('.tool-result-section');
            const resultEl = card.querySelector('.tool-call-result');

            if (isError) {
                resultEl.className = 'tool-call-result error';
                resultEl.textContent = result.error || 'Unknown error';
            } else {
                const formatted = this._formatJSON(result.result);
                resultEl.innerHTML = formatted;
            }
            resultSection.style.display = '';

            // Show timing
            const timingEl = card.querySelector('.tool-timing');
            const duration = result.duration_ms || (Date.now() - toolData.startTime);
            timingEl.textContent = `⏱ ${duration}ms`;

            // Auto-expand on error
            if (isError) {
                card.classList.add('expanded');
            }

            this.activeTools.delete(result.id);
        }

        /**
         * Format JSON for display with syntax highlighting.
         */
        _formatJSON(data) {
            if (!data) return '<span class="json-null">null</span>';

            try {
                const obj = typeof data === 'string' ? JSON.parse(data) : data;
                return this._syntaxHighlight(JSON.stringify(obj, null, 2));
            } catch(e) {
                return this._escapeHtml(typeof data === 'string' ? data : JSON.stringify(data));
            }
        }

        /**
         * Apply syntax highlighting to JSON string.
         */
        _syntaxHighlight(json) {
            if (!json) return '';
            json = this._escapeHtml(json);
            return json.replace(
                /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
                function(match) {
                    let cls = 'json-number';
                    if (/^"/.test(match)) {
                        if (/:$/.test(match)) {
                            cls = 'json-key';
                        } else {
                            cls = 'json-string';
                        }
                    } else if (/true|false/.test(match)) {
                        cls = 'json-boolean';
                    } else if (/null/.test(match)) {
                        cls = 'json-null';
                    }
                    return `<span class="${cls}">${match}</span>`;
                }
            );
        }

        _escapeHtml(str) {
            if (!str) return '';
            const div = document.createElement('div');
            div.textContent = typeof str === 'string' ? str : JSON.stringify(str);
            return div.innerHTML;
        }
    }

    // Register globally
    window._toolVisualizer = new ToolVisualizer();
})();
</script>
```

### 2. Tool Card CSS — add to `engine_chat.html` styles

```css
/* ── Tool Call Cards ─────────────────────────────────────────── */
.tool-call-card {
    background: var(--bg-tertiary, #2a2a3e);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 8px;
    margin: 8px 0;
    overflow: hidden;
    transition: border-color 0.2s;
}

.tool-call-card:hover {
    border-color: rgba(108, 92, 231, 0.3);
}

.tool-call-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 12px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary, #e0e0e0);
    transition: background 0.15s;
}

.tool-call-header:hover {
    background: rgba(255, 255, 255, 0.03);
}

.tool-icon {
    font-size: 0.9rem;
    flex-shrink: 0;
}

.tool-name {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
}

.tool-call-status {
    margin-left: auto;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: 500;
    flex-shrink: 0;
}

.tool-call-status.pending {
    background: rgba(255, 193, 7, 0.15);
    color: #ffc107;
}

.tool-call-status.executing {
    background: rgba(0, 210, 106, 0.15);
    color: #00d26a;
}

.tool-call-status.complete {
    background: rgba(102, 126, 234, 0.15);
    color: #667eea;
}

.tool-call-status.error {
    background: rgba(255, 68, 68, 0.15);
    color: #ff4444;
}

/* ── Spinner ─────────────────────────────────────────────────── */
.tool-spinner {
    width: 10px;
    height: 10px;
    border: 2px solid rgba(0, 210, 106, 0.3);
    border-top-color: #00d26a;
    border-radius: 50%;
    animation: toolSpin 0.8s linear infinite;
}

@keyframes toolSpin {
    to { transform: rotate(360deg); }
}

/* ── Tool Body ───────────────────────────────────────────────── */
.tool-call-body {
    display: none;
    padding: 0 12px 12px;
    border-top: 1px solid var(--border-color, #3a3a5e);
}

.tool-call-card.expanded .tool-call-body {
    display: block;
}

.tool-section {
    margin-top: 8px;
}

.tool-section-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--text-muted, #888);
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}

.tool-call-params,
.tool-call-result {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    background: var(--bg-primary, #0d0d1a);
    padding: 10px;
    border-radius: 6px;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    line-height: 1.5;
    max-height: 300px;
    overflow-y: auto;
}

.tool-call-result.error {
    color: #ff4444;
    background: rgba(255, 68, 68, 0.05);
    border: 1px solid rgba(255, 68, 68, 0.15);
}

.tool-timing {
    margin-top: 8px;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    text-align: right;
}

/* ── JSON Syntax Highlighting ────────────────────────────────── */
.json-key { color: #667eea; }
.json-string { color: #00d26a; }
.json-number { color: #ffd93d; }
.json-boolean { color: #ff6b6b; }
.json-null { color: #888; font-style: italic; }
```

### 3. Integration with WebSocket handler (modify handleWSMessage in S6-01)

```javascript
// In handleWSMessage(), update tool-related cases:

case 'tool_call':
case 'tool_call_start':
    if (streamingMessageEl) {
        const body = streamingMessageEl.querySelector('.message-body');
        window._toolVisualizer.createToolCard(body, {
            id: msg.id || msg.tool_call_id || ('tool-' + Date.now()),
            name: msg.name || msg.function?.name || 'unknown_tool',
            arguments: msg.arguments || msg.function?.arguments || msg.params || {},
        });
    }
    break;

case 'tool_result':
case 'tool_call_end':
    window._toolVisualizer.completeToolCall({
        id: msg.id || msg.tool_call_id,
        result: msg.result || msg.output,
        error: msg.error,
        status: msg.status,
        duration_ms: msg.duration_ms,
    });
    break;
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | UI component, tool results from API |
| 2 | .env for secrets (zero in code) | ❌ | No secrets |
| 3 | models.yaml single source of truth | ❌ | No model access |
| 4 | Docker-first testing | ✅ | Part of Flask template |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S6-01 (Chat UI — tool cards rendered inside messages)
- S1-04 (Tool calling bridge — tool_call WebSocket events)
- S2-03 (WebSocket streaming — must emit tool_call_start/end events)

## Verification
```bash
# 1. ToolVisualizer class present:
curl -s http://aria-web:5000/chat/ | grep -c "ToolVisualizer"
# EXPECTED: 1

# 2. Tool card CSS present:
curl -s http://aria-web:5000/chat/ | grep -c "tool-call-card"
# EXPECTED: at least 3

# 3. JSON syntax highlighting CSS present:
curl -s http://aria-web:5000/chat/ | grep -c "json-key"
# EXPECTED: at least 2

# 4. Spinner animation present:
curl -s http://aria-web:5000/chat/ | grep -c "toolSpin"
# EXPECTED: at least 1
```

## Prompt for Agent
```
Implement the tool call visualization component for the Aria chat UI.

FILES TO READ FIRST:
- src/web/templates/engine_chat.html (full file — chat UI from S6-01)
- aria_engine/tool_registry.py (tool definition format)
- src/api/routers/chat.py (WebSocket message format for tool events)
- aria_skills/base.py (BaseSkill — understand what tools look like)

STEPS:
1. Read engine_chat.html to understand the existing tool card structure
2. Create ToolVisualizer class as a standalone JS component
3. Implement createToolCard() — renders tool invocation card
4. Implement completeToolCall() — updates card with result/error
5. Add JSON syntax highlighting for parameters and results
6. Add animated spinner during execution
7. Add execution timing display
8. Integrate with WebSocket handler (tool_call_start/end events)
9. Add auto-expand on error

CONSTRAINTS:
- Cards must be expandable (collapsed by default, except on error)
- JSON must be pretty-printed with syntax highlighting
- Spinner must animate during execution
- Error results must be visually distinct (red styling)
```
