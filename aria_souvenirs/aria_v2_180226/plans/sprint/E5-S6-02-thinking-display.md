# S6-02: Thinking Token Display Panel
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P1 | **Points:** 3 | **Phase:** 6

## Problem
When Aria uses models that support extended thinking (Qwen3, Claude), the reasoning tokens are available via the WebSocket stream but there's no dedicated UI component to display them. Users need visibility into *how* Aria reasons, not just what she outputs.

## Root Cause
The thinking token format (`reasoning_content` from LiteLLM) is a new capability introduced with Qwen3 and Claude. OpenClaw had no UI for this. The chat UI (S6-01) includes basic thinking panel structure, but this ticket provides the complete standalone component with enhanced features: per-message toggle state, token counting, and distinct styling.

## Fix

### 1. Thinking Display Component — add to `engine_chat.html` JavaScript

This code extends the chat UI (S6-01) with a fully-featured thinking panel system. The following JavaScript module should be included in the chat template's `extra_js` block, after the main chat script.

```html
<!-- Add to engine_chat.html after main chat script -->
<script>
(function() {
    'use strict';

    /**
     * ThinkingDisplay — Manages thinking/reasoning token display per message.
     *
     * Features:
     * - Collapsible panel per assistant message
     * - Real-time token counting (thinking vs response)
     * - Distinct visual styling (italic, monospace, gray background)
     * - Toggle state preserved per message
     * - Streaming support: panel updates in real-time as thinking tokens arrive
     */
    class ThinkingDisplay {
        constructor() {
            // Track toggle state per message element id
            this.toggleStates = new Map();
            // Track token counts per message
            this.tokenCounts = new Map();
        }

        /**
         * Create a thinking panel element for a message.
         * @param {string} messageId — unique ID for the message
         * @param {string} thinkingText — initial thinking text (can be empty for streaming)
         * @param {boolean} startExpanded — whether to start expanded
         * @returns {HTMLElement} — the thinking panel element
         */
        createPanel(messageId, thinkingText = '', startExpanded = false) {
            const panel = document.createElement('div');
            panel.className = 'thinking-panel';
            panel.id = `thinking-${messageId}`;
            panel.dataset.messageId = messageId;

            const thinkingTokens = this._countTokens(thinkingText);
            this.tokenCounts.set(messageId, { thinking: thinkingTokens, response: 0 });

            const isExpanded = this.toggleStates.get(messageId) || startExpanded;

            panel.innerHTML = `
                <button class="thinking-toggle ${isExpanded ? 'expanded' : ''}"
                        onclick="window._thinkingDisplay.toggle('${messageId}')">
                    <span class="chevron">▶</span>
                    <span class="thinking-label">${thinkingText ? 'Show Thinking' : 'Thinking…'}</span>
                    <span class="thinking-token-count">${thinkingTokens > 0 ? thinkingTokens + ' tokens' : ''}</span>
                </button>
                <div class="thinking-content" ${isExpanded ? 'style="display:block;"' : ''}>${this._escapeHtml(thinkingText)}</div>
            `;

            return panel;
        }

        /**
         * Append thinking text during streaming.
         * @param {string} messageId — message identifier
         * @param {string} text — new thinking text chunk
         */
        appendThinking(messageId, text) {
            const panel = document.getElementById(`thinking-${messageId}`);
            if (!panel) return;

            const contentEl = panel.querySelector('.thinking-content');
            contentEl.textContent += text;

            // Update token count
            const counts = this.tokenCounts.get(messageId) || { thinking: 0, response: 0 };
            counts.thinking = this._countTokens(contentEl.textContent);
            this.tokenCounts.set(messageId, counts);

            const countEl = panel.querySelector('.thinking-token-count');
            countEl.textContent = `${counts.thinking} tokens`;
        }

        /**
         * Finalize the thinking panel after streaming completes.
         * @param {string} messageId — message identifier
         * @param {number} responseTokens — number of response tokens
         */
        finalize(messageId, responseTokens = 0) {
            const panel = document.getElementById(`thinking-${messageId}`);
            if (!panel) return;

            const counts = this.tokenCounts.get(messageId) || { thinking: 0, response: 0 };
            counts.response = responseTokens;
            this.tokenCounts.set(messageId, counts);

            // Update label
            const label = panel.querySelector('.thinking-label');
            label.textContent = 'Show Thinking';

            // Update token display with ratio
            const countEl = panel.querySelector('.thinking-token-count');
            if (counts.thinking > 0) {
                const ratio = counts.response > 0
                    ? `${counts.thinking} thinking / ${counts.response} response`
                    : `${counts.thinking} tokens`;
                countEl.textContent = ratio;
            }
        }

        /**
         * Toggle thinking panel visibility.
         * @param {string} messageId — message identifier
         */
        toggle(messageId) {
            const panel = document.getElementById(`thinking-${messageId}`);
            if (!panel) return;

            const toggleBtn = panel.querySelector('.thinking-toggle');
            const contentEl = panel.querySelector('.thinking-content');
            const isExpanded = toggleBtn.classList.toggle('expanded');

            contentEl.style.display = isExpanded ? 'block' : 'none';
            this.toggleStates.set(messageId, isExpanded);
        }

        /**
         * Get token counts for a message.
         * @param {string} messageId — message identifier
         * @returns {{ thinking: number, response: number }} — token counts
         */
        getCounts(messageId) {
            return this.tokenCounts.get(messageId) || { thinking: 0, response: 0 };
        }

        /**
         * Rough token count estimation (whitespace split).
         * Server provides accurate counts; this is for real-time display.
         */
        _countTokens(text) {
            if (!text) return 0;
            return text.split(/\s+/).filter(w => w.length > 0).length;
        }

        _escapeHtml(str) {
            if (!str) return '';
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }
    }

    // Register globally for onclick handlers
    window._thinkingDisplay = new ThinkingDisplay();
})();
</script>
```

### 2. Additional CSS — add to `engine_chat.html` styles

```css
/* ── Enhanced Thinking Panel Styles ──────────────────────────── */
.thinking-panel {
    background: rgba(102, 126, 234, 0.04);
    border: 1px solid rgba(102, 126, 234, 0.12);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
    transition: border-color 0.2s;
}

.thinking-panel:hover {
    border-color: rgba(102, 126, 234, 0.25);
}

.thinking-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-muted, #888);
    background: none;
    border: none;
    width: 100%;
    text-align: left;
    transition: color 0.2s, background 0.2s;
    font-family: inherit;
}

.thinking-toggle:hover {
    color: var(--text-primary, #e0e0e0);
    background: rgba(102, 126, 234, 0.06);
}

.thinking-toggle .chevron {
    transition: transform 0.2s;
    font-size: 0.7rem;
    flex-shrink: 0;
}

.thinking-toggle.expanded .chevron {
    transform: rotate(90deg);
}

.thinking-label {
    flex-shrink: 0;
}

.thinking-token-count {
    margin-left: auto;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    opacity: 0.7;
    font-family: 'JetBrains Mono', monospace;
}

.thinking-content {
    display: none;
    padding: 8px 12px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    color: #9ca3af;
    font-style: italic;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-height: 400px;
    overflow-y: auto;
    background: rgba(0, 0, 0, 0.15);
    border-top: 1px solid rgba(102, 126, 234, 0.08);
}

.thinking-content::-webkit-scrollbar {
    width: 4px;
}

.thinking-content::-webkit-scrollbar-thumb {
    background: rgba(102, 126, 234, 0.2);
    border-radius: 2px;
}

/* During streaming, show animated label */
.message.streaming .thinking-label {
    animation: thinkingPulse 1.5s ease-in-out infinite;
}

@keyframes thinkingPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

### 3. Integration with chat message handler (modify handleWSMessage in S6-01)

```javascript
// In handleWSMessage(), update the 'thinking' case:
case 'thinking':
    if (streamingMessageId) {
        window._thinkingDisplay.appendThinking(streamingMessageId, msg.content || '');
    }
    break;

// In startStreamingMessage(), add thinking panel:
function startStreamingMessage() {
    isStreaming = true;
    streamContent = '';
    streamingMessageId = 'msg-' + Date.now();

    const container = document.getElementById('chatMessages');
    const msgEl = createMessageElement('assistant', '', { id: streamingMessageId });
    msgEl.classList.add('streaming');

    // Insert thinking panel (hidden until thinking tokens arrive)
    const thinkingPanel = window._thinkingDisplay.createPanel(streamingMessageId, '', false);
    thinkingPanel.style.display = 'none'; // Hidden until first thinking token
    const body = msgEl.querySelector('.message-body');
    body.insertBefore(thinkingPanel, body.querySelector('.message-content'));

    container.appendChild(msgEl);
    streamingMessageEl = msgEl;
    scrollToBottom();
}

// Show thinking panel on first thinking token:
function appendStreamThinking(text) {
    if (!streamingMessageEl || !streamingMessageId) return;
    const panel = document.getElementById(`thinking-${streamingMessageId}`);
    if (panel && panel.style.display === 'none') {
        panel.style.display = ''; // Show on first token
    }
    window._thinkingDisplay.appendThinking(streamingMessageId, text);
    if (autoScroll) scrollToBottom();
}

// In finalizeStreamingMessage(), finalize thinking:
function finalizeStreamingMessage(msg) {
    if (streamingMessageId) {
        const responseTokens = msg?.tokens_output || 0;
        window._thinkingDisplay.finalize(streamingMessageId, responseTokens);
    }
    // ... rest of finalize logic
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | UI component, calls no backend directly |
| 2 | .env for secrets (zero in code) | ❌ | No secrets in UI component |
| 3 | models.yaml single source of truth | ❌ | No model access |
| 4 | Docker-first testing | ✅ | Tested as part of Flask template rendering |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S6-01 (Chat UI — this extends the base chat template)
- S2-03 (WebSocket streaming — must emit `thinking` event type)
- S1-03 (Thinking token handling in LLM gateway)

## Verification
```bash
# 1. ThinkingDisplay class exists in template:
curl -s http://aria-web:5000/chat/ | grep -c "ThinkingDisplay"
# EXPECTED: 1

# 2. Thinking panel CSS present:
curl -s http://aria-web:5000/chat/ | grep -c "thinking-panel"
# EXPECTED: at least 3 (CSS + HTML)

# 3. Toggle function registered:
curl -s http://aria-web:5000/chat/ | grep -c "_thinkingDisplay.toggle"
# EXPECTED: at least 1

# 4. Token count display present:
curl -s http://aria-web:5000/chat/ | grep -c "thinking-token-count"
# EXPECTED: at least 2
```

## Prompt for Agent
```
Implement the thinking token display component for the Aria chat UI.

FILES TO READ FIRST:
- src/web/templates/engine_chat.html (full file — chat UI from S6-01)
- aria_engine/llm_gateway.py (lines 180-230 — streaming thinking tokens)
- src/api/routers/chat.py (WebSocket message format — thinking event)

STEPS:
1. Read engine_chat.html to understand the existing thinking panel structure
2. Create ThinkingDisplay class as a standalone JS component
3. Integrate with the streaming message handler
4. Add enhanced CSS for thinking panels
5. Ensure thinking panel is hidden until first thinking token arrives
6. Add token counting (thinking vs response)
7. Test with collapsible toggle per message
8. Verify styling: italic, monospace, gray background

CONSTRAINTS:
- Must work with streaming (tokens arrive one at a time)
- Toggle state must be preserved per message (don't collapse on new tokens)
- Token count is approximate (whitespace-split) until server provides exact count
- Panel must auto-show when first thinking token arrives
```
