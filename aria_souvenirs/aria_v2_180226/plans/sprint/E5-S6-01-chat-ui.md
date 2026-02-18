# S6-01: Web Chat UI with WebSocket Streaming
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P0 | **Points:** 8 | **Phase:** 6

## Problem
Aria has no native chat interface. All chat currently goes through the OpenClaw `/clawdbot/` proxy which is being removed. We need a full-featured web chat UI at `/chat/` that connects directly to the engine's WebSocket streaming endpoint at `/ws/chat/{session_id}`, renders markdown, highlights code, and provides a production-quality chat experience.

## Root Cause
The Flask dashboard (`src/web/app.py`) has 25+ pages but no chat page — all chat was proxied to OpenClaw's built-in UI via the `/clawdbot/` route. With OpenClaw removal (E6), there is no chat interface at all unless we build one natively.

## Fix

### 1. Flask Route — `src/web/app.py` (add route)
```python
# Add after existing routes in create_app()

@app.route('/chat/')
@app.route('/chat/<session_id>')
def chat(session_id=None):
    return render_template('engine_chat.html', session_id=session_id)
```

### 2. Chat Template — `src/web/templates/engine_chat.html`
```html
{% extends "base.html" %}
{% block title %}Aria Chat{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<style>
/* ── Chat Layout ─────────────────────────────────────────────── */
.chat-container {
    display: flex;
    height: calc(100vh - 64px);
    overflow: hidden;
}

.chat-main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}

.chat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
    background: var(--bg-secondary, #1a1a2e);
    gap: 12px;
    flex-shrink: 0;
}

.chat-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.chat-header h2 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary, #e0e0e0);
}

.chat-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.8rem;
    color: var(--text-muted, #888);
}

.chat-status .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #666;
    transition: background 0.3s;
}

.chat-status .dot.connected { background: #00d26a; }
.chat-status .dot.connecting { background: #ffc107; animation: pulse 1s infinite; }
.chat-status .dot.error { background: #ff4444; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* ── Messages Area ───────────────────────────────────────────── */
.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    scroll-behavior: smooth;
}

.chat-messages::-webkit-scrollbar {
    width: 6px;
}

.chat-messages::-webkit-scrollbar-thumb {
    background: var(--border-color, #3a3a5e);
    border-radius: 3px;
}

.message {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
    animation: fadeIn 0.2s ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

.message-avatar {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
    margin-top: 2px;
}

.message.user .message-avatar {
    background: var(--accent-primary, #6c5ce7);
    color: white;
}

.message.assistant .message-avatar {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.message.system .message-avatar {
    background: var(--bg-tertiary, #2a2a3e);
    color: var(--text-muted, #888);
}

.message-body {
    flex: 1;
    min-width: 0;
}

.message-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
}

.message-role {
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: capitalize;
}

.message.user .message-role { color: var(--accent-primary, #6c5ce7); }
.message.assistant .message-role { color: #667eea; }
.message.system .message-role { color: var(--text-muted, #888); }

.message-time {
    font-size: 0.7rem;
    color: var(--text-muted, #888);
}

.message-content {
    font-size: 0.9rem;
    line-height: 1.7;
    color: var(--text-primary, #e0e0e0);
    word-wrap: break-word;
}

.message-content p { margin: 0 0 8px 0; }
.message-content p:last-child { margin-bottom: 0; }

.message-content pre {
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #2a2a3e);
    border-radius: 8px;
    padding: 16px;
    overflow-x: auto;
    margin: 8px 0;
    position: relative;
}

.message-content pre code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    line-height: 1.5;
}

.message-content code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85em;
    background: var(--bg-tertiary, #2a2a3e);
    padding: 2px 6px;
    border-radius: 4px;
}

.message-content pre code {
    background: none;
    padding: 0;
}

.copy-code-btn {
    position: absolute;
    top: 8px;
    right: 8px;
    background: var(--bg-tertiary, #2a2a3e);
    border: 1px solid var(--border-color, #3a3a5e);
    color: var(--text-muted, #888);
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.7rem;
    opacity: 0;
    transition: opacity 0.2s;
}

.message-content pre:hover .copy-code-btn { opacity: 1; }
.copy-code-btn:hover { background: var(--accent-primary, #6c5ce7); color: white; }

/* ── Thinking Panel ──────────────────────────────────────────── */
.thinking-panel {
    background: rgba(102, 126, 234, 0.05);
    border: 1px solid rgba(102, 126, 234, 0.15);
    border-radius: 8px;
    margin-bottom: 8px;
    overflow: hidden;
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
    transition: color 0.2s;
}

.thinking-toggle:hover { color: var(--text-primary, #e0e0e0); }

.thinking-toggle .chevron {
    transition: transform 0.2s;
    font-size: 0.7rem;
}

.thinking-toggle.expanded .chevron { transform: rotate(90deg); }

.thinking-content {
    display: none;
    padding: 8px 12px 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    line-height: 1.6;
    color: var(--text-muted, #888);
    font-style: italic;
    white-space: pre-wrap;
    max-height: 300px;
    overflow-y: auto;
}

.thinking-toggle.expanded + .thinking-content { display: block; }

.thinking-token-count {
    margin-left: auto;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
    opacity: 0.7;
}

/* ── Tool Calls ──────────────────────────────────────────────── */
.tool-call-card {
    background: var(--bg-tertiary, #2a2a3e);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 8px;
    margin: 8px 0;
    overflow: hidden;
}

.tool-call-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 500;
}

.tool-call-header .tool-icon { font-size: 0.9rem; }

.tool-call-status {
    margin-left: auto;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 4px;
}

.tool-call-status.pending { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
.tool-call-status.executing { background: rgba(0, 210, 106, 0.2); color: #00d26a; }
.tool-call-status.complete { background: rgba(102, 126, 234, 0.2); color: #667eea; }
.tool-call-status.error { background: rgba(255, 68, 68, 0.2); color: #ff4444; }

.tool-call-body {
    display: none;
    padding: 8px 12px 12px;
    border-top: 1px solid var(--border-color, #3a3a5e);
}

.tool-call-card.expanded .tool-call-body { display: block; }

.tool-call-params, .tool-call-result {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    background: var(--bg-primary, #0d0d1a);
    padding: 8px;
    border-radius: 4px;
    overflow-x: auto;
    white-space: pre-wrap;
    margin-top: 4px;
}

/* ── Streaming Indicator ─────────────────────────────────────── */
.streaming-indicator {
    display: inline-flex;
    gap: 4px;
    padding: 4px 0;
}

.streaming-indicator .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #667eea;
    animation: streamPulse 1.4s ease-in-out infinite;
}

.streaming-indicator .dot:nth-child(2) { animation-delay: 0.2s; }
.streaming-indicator .dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes streamPulse {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
}

/* ── Input Area ──────────────────────────────────────────────── */
.chat-input-area {
    padding: 16px 20px;
    border-top: 1px solid var(--border-color, #2a2a3e);
    background: var(--bg-secondary, #1a1a2e);
    flex-shrink: 0;
}

.chat-input-wrapper {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    gap: 8px;
    align-items: flex-end;
}

.chat-input {
    flex: 1;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 12px;
    padding: 12px 16px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.9rem;
    font-family: inherit;
    resize: none;
    min-height: 44px;
    max-height: 200px;
    line-height: 1.5;
    outline: none;
    transition: border-color 0.2s;
}

.chat-input:focus {
    border-color: var(--accent-primary, #6c5ce7);
}

.chat-input::placeholder {
    color: var(--text-muted, #888);
}

.chat-send-btn {
    background: var(--accent-primary, #6c5ce7);
    border: none;
    border-radius: 12px;
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    color: white;
    transition: background 0.2s, transform 0.1s;
    flex-shrink: 0;
}

.chat-send-btn:hover { background: #5a4bd6; }
.chat-send-btn:active { transform: scale(0.95); }
.chat-send-btn:disabled { opacity: 0.4; cursor: default; }

.chat-input-meta {
    display: flex;
    justify-content: space-between;
    max-width: 900px;
    margin: 6px auto 0;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
}

/* ── Scroll to Bottom ────────────────────────────────────────── */
.scroll-bottom-btn {
    position: absolute;
    bottom: 100px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #3a3a5e);
    color: var(--text-primary, #e0e0e0);
    padding: 6px 16px;
    border-radius: 20px;
    cursor: pointer;
    font-size: 0.8rem;
    display: none;
    z-index: 10;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    transition: opacity 0.2s;
}

.scroll-bottom-btn:hover { background: var(--bg-tertiary, #2a2a3e); }
.scroll-bottom-btn.visible { display: flex; align-items: center; gap: 6px; }

/* ── Empty State ─────────────────────────────────────────────── */
.chat-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted, #888);
    text-align: center;
    padding: 40px;
}

.chat-empty .icon { font-size: 3rem; margin-bottom: 16px; opacity: 0.5; }
.chat-empty h3 { margin: 0 0 8px; color: var(--text-primary, #e0e0e0); }
.chat-empty p { margin: 0; font-size: 0.9rem; max-width: 400px; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
    .chat-container { flex-direction: column; }
    .chat-messages { padding: 12px; }
    .chat-input-area { padding: 12px; }
    .message-avatar { width: 28px; height: 28px; font-size: 12px; }
}
</style>
{% endblock %}

{% block content %}
<div class="chat-container" id="chatContainer">
    <!-- Main Chat Area -->
    <div class="chat-main">
        <!-- Header -->
        <div class="chat-header">
            <div class="chat-header-left">
                <button id="sidebarToggle" class="page-btn" title="Toggle sessions"
                        style="padding:6px 10px;font-size:1rem;">☰</button>
                <h2 id="chatTitle">New Chat</h2>
            </div>
            <div class="chat-status">
                <span class="dot" id="statusDot"></span>
                <span id="statusText">Disconnected</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <select id="modelSelector" class="page-limit-select" title="Select model">
                    <option value="">Loading models…</option>
                </select>
            </div>
        </div>

        <!-- Messages -->
        <div class="chat-messages" id="chatMessages" style="position:relative;">
            <div class="chat-empty" id="chatEmpty">
                <div class="icon">🌟</div>
                <h3>Chat with Aria</h3>
                <p>Send a message to start a conversation. Aria supports markdown, code highlighting, and tool calling.</p>
            </div>
            <button class="scroll-bottom-btn" id="scrollBottomBtn" onclick="scrollToBottom()">
                ↓ New messages
            </button>
        </div>

        <!-- Input -->
        <div class="chat-input-area">
            <div class="chat-input-wrapper">
                <textarea id="chatInput" class="chat-input" placeholder="Send a message to Aria…"
                          rows="1" autofocus></textarea>
                <button id="sendBtn" class="chat-send-btn" onclick="sendMessage()" title="Send (Enter)">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13"></line>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                    </svg>
                </button>
            </div>
            <div class="chat-input-meta">
                <span id="tokenInfo"></span>
                <span id="modelInfo"></span>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>
(function() {
    'use strict';

    // ── State ───────────────────────────────────────────────────
    let ws = null;
    let sessionId = '{{ session_id or "" }}';
    let currentModel = '';
    let isStreaming = false;
    let streamingMessageEl = null;
    let streamContent = '';
    let streamThinking = '';
    let autoScroll = true;
    const API = '{{ api_base_url }}';

    // ── Marked config ───────────────────────────────────────────
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                return hljs.highlight(code, { language: lang }).value;
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true,
    });

    // ── Init ────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        loadModels();
        setupInput();
        setupScrollDetection();
        if (sessionId) {
            loadSession(sessionId);
        }
    });

    // ── Models ──────────────────────────────────────────────────
    async function loadModels() {
        try {
            const resp = await fetch('/api/models/available');
            const data = await resp.json();
            const select = document.getElementById('modelSelector');
            select.innerHTML = '';
            const models = data.models || data || [];
            if (Array.isArray(models)) {
                models.forEach(m => {
                    const opt = document.createElement('option');
                    const id = m.model_id || m.id || m;
                    opt.value = id;
                    opt.textContent = m.display_name || m.name || id;
                    select.appendChild(opt);
                });
            }
            if (!currentModel && select.options.length) {
                currentModel = select.options[0].value;
            }
            select.value = currentModel;
            select.onchange = () => { currentModel = select.value; };
        } catch(e) {
            console.warn('Failed to load models:', e);
        }
    }

    // ── WebSocket ───────────────────────────────────────────────
    function connectWS() {
        if (ws && ws.readyState <= 1) return;
        if (!sessionId) return;

        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/api/ws/chat/${sessionId}`;
        setStatus('connecting');

        ws = new WebSocket(url);

        ws.onopen = () => {
            setStatus('connected');
            console.log('WebSocket connected to session:', sessionId);
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            handleWSMessage(msg);
        };

        ws.onclose = (e) => {
            setStatus('disconnected');
            console.log('WebSocket closed:', e.code, e.reason);
            // Auto-reconnect after 3s
            if (sessionId) {
                setTimeout(() => connectWS(), 3000);
            }
        };

        ws.onerror = (e) => {
            setStatus('error');
            console.error('WebSocket error:', e);
        };
    }

    function handleWSMessage(msg) {
        switch(msg.type) {
            case 'stream_start':
                startStreamingMessage();
                break;
            case 'content':
                appendStreamContent(msg.content || '');
                break;
            case 'thinking':
                appendStreamThinking(msg.content || '');
                break;
            case 'tool_call':
                addToolCall(msg);
                break;
            case 'tool_result':
                updateToolResult(msg);
                break;
            case 'stream_end':
                finalizeStreamingMessage(msg);
                break;
            case 'error':
                showError(msg.content || msg.error || 'Unknown error');
                break;
            case 'message':
                // Full message (non-streaming)
                addMessage(msg.role || 'assistant', msg.content, {
                    thinking: msg.thinking,
                    tool_calls: msg.tool_calls,
                    model: msg.model,
                    tokens: msg.tokens,
                });
                break;
        }
    }

    // ── Streaming ───────────────────────────────────────────────
    function startStreamingMessage() {
        isStreaming = true;
        streamContent = '';
        streamThinking = '';
        document.getElementById('chatEmpty').style.display = 'none';

        const container = document.getElementById('chatMessages');
        const msgEl = createMessageElement('assistant', '');
        msgEl.classList.add('streaming');

        // Add streaming indicator
        const indicator = document.createElement('div');
        indicator.className = 'streaming-indicator';
        indicator.id = 'streamIndicator';
        indicator.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
        msgEl.querySelector('.message-content').appendChild(indicator);

        container.appendChild(msgEl);
        streamingMessageEl = msgEl;
        scrollToBottom();

        document.getElementById('sendBtn').disabled = true;
    }

    function appendStreamContent(text) {
        if (!streamingMessageEl) return;
        streamContent += text;
        renderStreamContent();
        if (autoScroll) scrollToBottom();
    }

    function appendStreamThinking(text) {
        if (!streamingMessageEl) return;
        streamThinking += text;
        renderStreamThinking();
        if (autoScroll) scrollToBottom();
    }

    function renderStreamContent() {
        if (!streamingMessageEl) return;
        const contentEl = streamingMessageEl.querySelector('.message-content');
        const indicator = document.getElementById('streamIndicator');
        const html = marked.parse(streamContent);
        contentEl.innerHTML = html;
        if (indicator) contentEl.appendChild(indicator);
        // Re-apply code highlighting
        contentEl.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
            addCopyButton(block.closest('pre'));
        });
    }

    function renderStreamThinking() {
        if (!streamingMessageEl || !streamThinking) return;
        let panel = streamingMessageEl.querySelector('.thinking-panel');
        if (!panel) {
            panel = document.createElement('div');
            panel.className = 'thinking-panel';
            panel.innerHTML = `
                <button class="thinking-toggle" onclick="this.classList.toggle('expanded')">
                    <span class="chevron">▶</span>
                    Thinking…
                    <span class="thinking-token-count"></span>
                </button>
                <div class="thinking-content"></div>
            `;
            const body = streamingMessageEl.querySelector('.message-body');
            body.insertBefore(panel, body.querySelector('.message-content'));
        }
        const thinkingContent = panel.querySelector('.thinking-content');
        thinkingContent.textContent = streamThinking;
        const tokenCount = panel.querySelector('.thinking-token-count');
        tokenCount.textContent = `${streamThinking.split(/\s+/).length} tokens`;
    }

    function finalizeStreamingMessage(msg) {
        isStreaming = false;
        if (streamingMessageEl) {
            streamingMessageEl.classList.remove('streaming');
            const indicator = document.getElementById('streamIndicator');
            if (indicator) indicator.remove();
            renderStreamContent(); // Final render

            // Add metadata
            if (msg && (msg.tokens_input || msg.tokens_output)) {
                const meta = document.createElement('div');
                meta.className = 'message-time';
                meta.style.marginTop = '8px';
                meta.textContent = `${msg.model || currentModel} · ${msg.tokens_input || 0} in / ${msg.tokens_output || 0} out`;
                streamingMessageEl.querySelector('.message-body').appendChild(meta);
            }
        }
        streamingMessageEl = null;
        streamContent = '';
        streamThinking = '';
        document.getElementById('sendBtn').disabled = false;
        document.getElementById('chatInput').focus();
    }

    // ── Messages ────────────────────────────────────────────────
    function addMessage(role, content, opts = {}) {
        document.getElementById('chatEmpty').style.display = 'none';
        const container = document.getElementById('chatMessages');
        const msgEl = createMessageElement(role, content, opts);
        container.appendChild(msgEl);
        scrollToBottom();
    }

    function createMessageElement(role, content, opts = {}) {
        const msg = document.createElement('div');
        msg.className = `message ${role}`;

        const avatarText = role === 'user' ? '👤' : role === 'assistant' ? '🌟' : '⚙️';

        let thinkingHTML = '';
        if (opts.thinking) {
            const tokenCount = (opts.thinking || '').split(/\s+/).length;
            thinkingHTML = `
                <div class="thinking-panel">
                    <button class="thinking-toggle" onclick="this.classList.toggle('expanded')">
                        <span class="chevron">▶</span>
                        Show Thinking
                        <span class="thinking-token-count">${tokenCount} tokens</span>
                    </button>
                    <div class="thinking-content">${escapeHtml(opts.thinking)}</div>
                </div>
            `;
        }

        let toolCallsHTML = '';
        if (opts.tool_calls && opts.tool_calls.length) {
            toolCallsHTML = opts.tool_calls.map(tc => `
                <div class="tool-call-card" onclick="this.classList.toggle('expanded')">
                    <div class="tool-call-header">
                        <span class="tool-icon">🔧</span>
                        <span>${escapeHtml(tc.function?.name || tc.name || 'tool')}</span>
                        <span class="tool-call-status complete">complete</span>
                    </div>
                    <div class="tool-call-body">
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">Parameters:</div>
                        <div class="tool-call-params">${escapeHtml(typeof tc.function?.arguments === 'string' ? tc.function.arguments : JSON.stringify(tc.function?.arguments || tc.arguments, null, 2))}</div>
                    </div>
                </div>
            `).join('');
        }

        const renderedContent = content ? marked.parse(content) : '';
        const time = new Date().toLocaleTimeString();

        msg.innerHTML = `
            <div class="message-avatar">${avatarText}</div>
            <div class="message-body">
                <div class="message-header">
                    <span class="message-role">${role}</span>
                    <span class="message-time">${time}</span>
                </div>
                ${thinkingHTML}
                ${toolCallsHTML}
                <div class="message-content">${renderedContent}</div>
            </div>
        `;

        // Highlight code blocks and add copy buttons
        msg.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
            addCopyButton(block.closest('pre'));
        });

        return msg;
    }

    function addCopyButton(preEl) {
        if (!preEl || preEl.querySelector('.copy-code-btn')) return;
        const btn = document.createElement('button');
        btn.className = 'copy-code-btn';
        btn.textContent = 'Copy';
        btn.onclick = (e) => {
            e.stopPropagation();
            const code = preEl.querySelector('code')?.textContent || '';
            navigator.clipboard.writeText(code).then(() => {
                btn.textContent = 'Copied!';
                setTimeout(() => { btn.textContent = 'Copy'; }, 2000);
            });
        };
        preEl.style.position = 'relative';
        preEl.appendChild(btn);
    }

    function addToolCall(msg) {
        if (!streamingMessageEl) return;
        const body = streamingMessageEl.querySelector('.message-body');
        const card = document.createElement('div');
        card.className = 'tool-call-card';
        card.id = `tool-${msg.id || Date.now()}`;
        card.innerHTML = `
            <div class="tool-call-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="tool-icon">🔧</span>
                <span>${escapeHtml(msg.name || 'tool')}</span>
                <span class="tool-call-status executing">
                    <span class="streaming-indicator" style="display:inline-flex;gap:2px;">
                        <span class="dot" style="width:4px;height:4px;"></span>
                        <span class="dot" style="width:4px;height:4px;"></span>
                        <span class="dot" style="width:4px;height:4px;"></span>
                    </span>
                    executing
                </span>
            </div>
            <div class="tool-call-body">
                <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:4px;">Parameters:</div>
                <div class="tool-call-params">${escapeHtml(JSON.stringify(msg.arguments || {}, null, 2))}</div>
            </div>
        `;
        const contentEl = body.querySelector('.message-content');
        body.insertBefore(card, contentEl);
    }

    function updateToolResult(msg) {
        const card = document.getElementById(`tool-${msg.id}`);
        if (!card) return;
        const status = card.querySelector('.tool-call-status');
        const isError = msg.error || msg.status === 'error';
        status.className = `tool-call-status ${isError ? 'error' : 'complete'}`;
        status.textContent = isError ? 'error' : 'complete';
        const body = card.querySelector('.tool-call-body');
        const resultDiv = document.createElement('div');
        resultDiv.innerHTML = `
            <div style="font-size:0.75rem;color:var(--text-muted);margin:8px 0 4px;">Result:</div>
            <div class="tool-call-result">${escapeHtml(typeof msg.result === 'string' ? msg.result : JSON.stringify(msg.result, null, 2))}</div>
        `;
        body.appendChild(resultDiv);
    }

    // ── Send ────────────────────────────────────────────────────
    async function sendMessage() {
        const input = document.getElementById('chatInput');
        const text = input.value.trim();
        if (!text || isStreaming) return;

        // Create session if needed
        if (!sessionId) {
            await createSession();
        }

        // Display user message
        addMessage('user', text);
        input.value = '';
        autoResizeInput();

        // Send via WebSocket
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: 'message',
                content: text,
                model: currentModel || undefined,
            }));
        } else {
            showError('Not connected. Attempting to reconnect…');
            connectWS();
        }
    }

    async function createSession() {
        try {
            const resp = await fetch('/api/engine/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: 'main',
                    model: currentModel || undefined,
                }),
            });
            const data = await resp.json();
            sessionId = data.id || data.session_id;
            document.getElementById('chatTitle').textContent = data.title || 'New Chat';
            history.replaceState(null, '', `/chat/${sessionId}`);
            connectWS();
        } catch(e) {
            showError('Failed to create session: ' + e.message);
        }
    }

    async function loadSession(sid) {
        try {
            // Load history
            const resp = await fetch(`/api/engine/sessions/${sid}/messages`);
            if (resp.ok) {
                const data = await resp.json();
                const messages = data.messages || data || [];
                if (messages.length) {
                    document.getElementById('chatEmpty').style.display = 'none';
                }
                messages.forEach(m => {
                    addMessage(m.role, m.content, {
                        thinking: m.thinking,
                        tool_calls: m.tool_calls,
                        model: m.model,
                    });
                });
            }
            // Connect WebSocket
            connectWS();
        } catch(e) {
            console.error('Failed to load session:', e);
            connectWS();
        }
    }

    // ── Input handling ──────────────────────────────────────────
    function setupInput() {
        const input = document.getElementById('chatInput');

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        input.addEventListener('input', autoResizeInput);
    }

    function autoResizeInput() {
        const input = document.getElementById('chatInput');
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    }

    // ── Scroll detection ────────────────────────────────────────
    function setupScrollDetection() {
        const container = document.getElementById('chatMessages');
        container.addEventListener('scroll', () => {
            const { scrollTop, scrollHeight, clientHeight } = container;
            const atBottom = scrollHeight - scrollTop - clientHeight < 100;
            autoScroll = atBottom;
            const btn = document.getElementById('scrollBottomBtn');
            btn.classList.toggle('visible', !atBottom);
        });
    }

    function scrollToBottom() {
        const container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
    }

    // ── Status ──────────────────────────────────────────────────
    function setStatus(status) {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        dot.className = `dot ${status}`;
        text.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }

    // ── Errors ──────────────────────────────────────────────────
    function showError(msg) {
        isStreaming = false;
        if (streamingMessageEl) {
            finalizeStreamingMessage(null);
        }
        addMessage('system', `⚠️ ${msg}`);
        document.getElementById('sendBtn').disabled = false;
    }

    // ── Utility ─────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Export for global onclick handlers
    window.sendMessage = sendMessage;
    window.scrollToBottom = scrollToBottom;
})();
</script>
{% endblock %}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | UI calls API, API calls engine |
| 2 | .env for secrets (zero in code) | ✅ | API_BASE_URL from Flask config |
| 3 | models.yaml single source of truth | ✅ | Model list populated via /api/models/available |
| 4 | Docker-first testing | ✅ | Flask serves template, connects to aria-api container |
| 5 | aria_memories only writable path | ❌ | No file writes, UI only |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S2-03 (WebSocket streaming endpoint at `/ws/chat/{session_id}`)
- S2-06 (REST chat endpoints for session creation and message history)
- S6-03 (Session sidebar — integrated separately)

## Verification
```bash
# 1. Template renders:
curl -s http://aria-web:5000/chat/ | grep -c "chat-container"
# EXPECTED: 1

# 2. Route exists:
curl -s -o /dev/null -w "%{http_code}" http://aria-web:5000/chat/
# EXPECTED: 200

# 3. Session route with ID:
curl -s -o /dev/null -w "%{http_code}" http://aria-web:5000/chat/test-session-id
# EXPECTED: 200

# 4. marked.js loaded:
curl -s http://aria-web:5000/chat/ | grep -c "marked.min.js"
# EXPECTED: 1

# 5. highlight.js loaded:
curl -s http://aria-web:5000/chat/ | grep -c "highlight.min.js"
# EXPECTED: 1
```

## Prompt for Agent
```
Build the main web chat UI for Aria with WebSocket streaming, markdown rendering, and code highlighting.

FILES TO READ FIRST:
- src/web/app.py (full file — existing Flask routes, template rendering pattern)
- src/web/templates/base.html (full file — base template with nav, CSS framework)
- src/web/templates/sessions.html (first 50 lines — example of existing page pattern)
- aria_engine/streaming.py (if exists — WebSocket message format)
- src/api/routers/chat.py (if exists — WebSocket endpoint spec)

STEPS:
1. Read all files above to understand patterns
2. Add /chat/ and /chat/<session_id> routes to src/web/app.py
3. Create src/web/templates/engine_chat.html extending base.html
4. Implement WebSocket connection to /ws/chat/{session_id}
5. Implement message rendering with marked.js for markdown
6. Implement code syntax highlighting with highlight.js
7. Implement streaming display with real-time token rendering
8. Implement thinking panel, tool call cards, copy-code buttons
9. Implement auto-scroll with "scroll to bottom" button
10. Verify mobile responsiveness

CONSTRAINTS:
- Constraint 1: UI calls /api/ endpoints only — no direct DB access
- Constraint 3: Model list from /api/models/available (sourced from models.yaml)
- Template must extend base.html for consistent nav
- Use existing CSS variables from variables.css
```
