# S6-03: Session Sidebar for Chat Page
**Epic:** E5 — Web Dashboard Evolution | **Priority:** P0 | **Points:** 5 | **Phase:** 6

## Problem
The chat page needs a session management sidebar so users can create new sessions, resume existing ones, delete old ones, search/filter, and switch between agents — all without leaving the chat UI.

## Root Cause
OpenClaw managed sessions internally with its own sidebar. With OpenClaw removal, the chat UI (S6-01) has no session management. Sessions are stored in `aria_engine.chat_sessions` but no UI exposes them in the chat context.

## Fix

### 1. Sidebar HTML — add to `engine_chat.html` inside `.chat-container`

Insert this sidebar before `.chat-main` in the chat container:

```html
<!-- Session Sidebar — insert as first child of .chat-container -->
<aside class="chat-sidebar" id="chatSidebar">
    <div class="sidebar-header">
        <h3>Sessions</h3>
        <button class="sidebar-close-btn" onclick="toggleSidebar()" title="Close sidebar">✕</button>
    </div>

    <!-- Agent Selector -->
    <div class="sidebar-section">
        <label class="sidebar-label">Agent</label>
        <select id="agentSelector" class="sidebar-select" onchange="filterSessions()">
            <option value="">All Agents</option>
        </select>
    </div>

    <!-- Search -->
    <div class="sidebar-section">
        <input type="text" id="sessionSearch" class="sidebar-search"
               placeholder="Search sessions…" oninput="filterSessions()">
    </div>

    <!-- New Session Button -->
    <button class="sidebar-new-btn" onclick="createNewSession()">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"/>
        </svg>
        New Chat
    </button>

    <!-- Session List -->
    <div class="session-list" id="sessionList">
        <div class="session-list-loading" id="sessionListLoading">
            Loading sessions…
        </div>
    </div>
</aside>
```

### 2. Sidebar CSS — add to `engine_chat.html` styles

```css
/* ── Session Sidebar ─────────────────────────────────────────── */
.chat-sidebar {
    width: 300px;
    min-width: 300px;
    background: var(--bg-secondary, #1a1a2e);
    border-right: 1px solid var(--border-color, #2a2a3e);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: margin-left 0.3s ease;
}

.chat-sidebar.collapsed {
    margin-left: -300px;
    min-width: 0;
    width: 0;
}

.sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px;
    border-bottom: 1px solid var(--border-color, #2a2a3e);
}

.sidebar-header h3 {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--text-primary, #e0e0e0);
}

.sidebar-close-btn {
    background: none;
    border: none;
    color: var(--text-muted, #888);
    cursor: pointer;
    font-size: 1rem;
    padding: 4px;
    border-radius: 4px;
    transition: color 0.2s, background 0.2s;
}

.sidebar-close-btn:hover {
    color: var(--text-primary, #e0e0e0);
    background: var(--bg-tertiary, #2a2a3e);
}

.sidebar-section {
    padding: 8px 16px;
}

.sidebar-label {
    display: block;
    font-size: 0.7rem;
    text-transform: uppercase;
    color: var(--text-muted, #888);
    margin-bottom: 4px;
    letter-spacing: 0.05em;
}

.sidebar-select {
    width: 100%;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 6px;
    padding: 8px 10px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.85rem;
    font-family: inherit;
}

.sidebar-search {
    width: 100%;
    background: var(--bg-primary, #0d0d1a);
    border: 1px solid var(--border-color, #3a3a5e);
    border-radius: 6px;
    padding: 8px 10px;
    color: var(--text-primary, #e0e0e0);
    font-size: 0.85rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
    box-sizing: border-box;
}

.sidebar-search:focus {
    border-color: var(--accent-primary, #6c5ce7);
}

.sidebar-new-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin: 8px 16px;
    padding: 10px;
    background: var(--accent-primary, #6c5ce7);
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: background 0.2s;
    font-family: inherit;
}

.sidebar-new-btn:hover {
    background: #5a4bd6;
}

/* ── Session List ────────────────────────────────────────────── */
.session-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.session-list::-webkit-scrollbar {
    width: 4px;
}

.session-list::-webkit-scrollbar-thumb {
    background: var(--border-color, #3a3a5e);
    border-radius: 2px;
}

.session-list-loading {
    text-align: center;
    padding: 20px;
    color: var(--text-muted, #888);
    font-size: 0.85rem;
}

.session-item {
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;
    margin-bottom: 2px;
    position: relative;
}

.session-item:hover {
    background: var(--bg-tertiary, #2a2a3e);
}

.session-item.active {
    background: rgba(108, 92, 231, 0.15);
    border: 1px solid rgba(108, 92, 231, 0.3);
}

.session-item-title {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-primary, #e0e0e0);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-bottom: 4px;
}

.session-item-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.7rem;
    color: var(--text-muted, #888);
}

.session-item-meta .agent-badge {
    background: rgba(108, 92, 231, 0.2);
    color: var(--accent-primary, #6c5ce7);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 500;
}

.session-item-actions {
    position: absolute;
    top: 8px;
    right: 8px;
    display: none;
    gap: 4px;
}

.session-item:hover .session-item-actions {
    display: flex;
}

.session-action-btn {
    background: var(--bg-secondary, #1a1a2e);
    border: 1px solid var(--border-color, #3a3a5e);
    color: var(--text-muted, #888);
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.7rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.15s;
}

.session-action-btn:hover {
    background: var(--bg-tertiary, #2a2a3e);
    color: var(--text-primary, #e0e0e0);
}

.session-action-btn.delete:hover {
    background: rgba(255, 68, 68, 0.15);
    color: #ff4444;
    border-color: rgba(255, 68, 68, 0.3);
}

.session-empty {
    text-align: center;
    padding: 40px 20px;
    color: var(--text-muted, #888);
    font-size: 0.85rem;
}

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 768px) {
    .chat-sidebar {
        position: fixed;
        top: 64px;
        left: 0;
        bottom: 0;
        z-index: 100;
        box-shadow: 4px 0 20px rgba(0,0,0,0.4);
    }
    .chat-sidebar.collapsed {
        transform: translateX(-100%);
        margin-left: 0;
    }
}
```

### 3. Sidebar JavaScript — add to `engine_chat.html` script

```javascript
(function() {
    'use strict';

    let allSessions = [];
    let sidebarVisible = true;

    // ── Init ────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
        loadAgents();
        loadSessions();

        // Mobile: start collapsed
        if (window.innerWidth <= 768) {
            toggleSidebar();
        }
    });

    // ── Toggle Sidebar ──────────────────────────────────────────
    function toggleSidebar() {
        const sidebar = document.getElementById('chatSidebar');
        sidebarVisible = !sidebarVisible;
        sidebar.classList.toggle('collapsed', !sidebarVisible);
    }

    // ── Load Agents ─────────────────────────────────────────────
    async function loadAgents() {
        try {
            const resp = await fetch('/api/engine/agents');
            const data = await resp.json();
            const select = document.getElementById('agentSelector');
            const agents = data.agents || data || [];
            agents.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.agent_id || a.id;
                opt.textContent = a.display_name || a.agent_id || a.id;
                select.appendChild(opt);
            });
        } catch(e) {
            console.warn('Failed to load agents:', e);
        }
    }

    // ── Load Sessions ───────────────────────────────────────────
    async function loadSessions() {
        const loading = document.getElementById('sessionListLoading');
        try {
            const resp = await fetch('/api/engine/sessions?limit=100&sort=updated_at:desc');
            const data = await resp.json();
            allSessions = data.sessions || data.items || data || [];
            renderSessionList(allSessions);
        } catch(e) {
            console.error('Failed to load sessions:', e);
            loading.textContent = 'Failed to load sessions';
        }
    }

    // ── Render Session List ─────────────────────────────────────
    function renderSessionList(sessions) {
        const container = document.getElementById('sessionList');

        if (!sessions.length) {
            container.innerHTML = '<div class="session-empty">No sessions yet.<br>Start a new chat!</div>';
            return;
        }

        container.innerHTML = sessions.map(s => {
            const title = s.title || s.label || `Chat ${(s.id || '').substring(0, 8)}`;
            const agent = s.agent_id || 'main';
            const date = s.updated_at || s.created_at;
            const dateStr = date ? new Date(date).toLocaleDateString() : '';
            const msgCount = s.message_count || 0;
            const model = s.model || '';
            const isActive = s.id === sessionId;

            return `
                <div class="session-item ${isActive ? 'active' : ''}"
                     onclick="switchSession('${s.id}')" data-id="${s.id}"
                     data-agent="${agent}" data-title="${escapeAttr(title)}">
                    <div class="session-item-title">${escapeHtml(title)}</div>
                    <div class="session-item-meta">
                        <span class="agent-badge">${escapeHtml(agent)}</span>
                        <span>${dateStr}</span>
                        ${msgCount ? `<span>${msgCount} msgs</span>` : ''}
                        ${model ? `<span>${escapeHtml(model.split('/').pop())}</span>` : ''}
                    </div>
                    <div class="session-item-actions">
                        <button class="session-action-btn delete" onclick="event.stopPropagation(); deleteSession('${s.id}')" title="Delete">🗑</button>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ── Filter Sessions ─────────────────────────────────────────
    function filterSessions() {
        const agentFilter = document.getElementById('agentSelector').value;
        const searchQuery = document.getElementById('sessionSearch').value.toLowerCase().trim();

        let filtered = allSessions;

        if (agentFilter) {
            filtered = filtered.filter(s => (s.agent_id || 'main') === agentFilter);
        }

        if (searchQuery) {
            filtered = filtered.filter(s => {
                const title = (s.title || s.label || '').toLowerCase();
                const agent = (s.agent_id || '').toLowerCase();
                const model = (s.model || '').toLowerCase();
                return title.includes(searchQuery) || agent.includes(searchQuery) || model.includes(searchQuery);
            });
        }

        renderSessionList(filtered);
    }

    // ── Switch Session ──────────────────────────────────────────
    async function switchSession(sid) {
        if (sid === sessionId) return;

        // Close existing WebSocket
        if (ws && ws.readyState <= 1) {
            ws.close();
        }

        sessionId = sid;
        history.replaceState(null, '', `/chat/${sid}`);

        // Clear messages
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';

        // Update active state
        document.querySelectorAll('.session-item').forEach(el => {
            el.classList.toggle('active', el.dataset.id === sid);
        });

        // Update title
        const item = document.querySelector(`.session-item[data-id="${sid}"]`);
        if (item) {
            document.getElementById('chatTitle').textContent = item.dataset.title || 'Chat';
        }

        // Load session messages and reconnect
        await loadSession(sid);
    }

    // ── Create New Session ──────────────────────────────────────
    async function createNewSession() {
        // Reset state
        if (ws && ws.readyState <= 1) {
            ws.close();
        }
        sessionId = '';
        streamingMessageEl = null;
        isStreaming = false;

        // Clear UI
        document.getElementById('chatMessages').innerHTML = `
            <div class="chat-empty" id="chatEmpty">
                <div class="icon">🌟</div>
                <h3>Chat with Aria</h3>
                <p>Send a message to start a conversation.</p>
            </div>
        `;
        document.getElementById('chatTitle').textContent = 'New Chat';
        history.replaceState(null, '', '/chat/');

        // Clear active state
        document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));

        document.getElementById('chatInput').focus();
    }

    // ── Delete Session ──────────────────────────────────────────
    async function deleteSession(sid) {
        if (!confirm('Delete this session? This cannot be undone.')) return;

        try {
            await fetch(`/api/engine/sessions/${sid}`, { method: 'DELETE' });
            allSessions = allSessions.filter(s => s.id !== sid);
            filterSessions();

            if (sid === sessionId) {
                await createNewSession();
            }
        } catch(e) {
            alert('Failed to delete session: ' + e.message);
        }
    }

    // ── Helpers ─────────────────────────────────────────────────
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function escapeAttr(str) {
        return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    // ── Exports for onclick handlers ────────────────────────────
    window.toggleSidebar = toggleSidebar;
    window.switchSession = switchSession;
    window.createNewSession = createNewSession;
    window.deleteSession = deleteSession;
    window.filterSessions = filterSessions;
})();
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Sidebar calls /api/engine/ endpoints |
| 2 | .env for secrets (zero in code) | ❌ | No secrets involved |
| 3 | models.yaml single source of truth | ❌ | No model access (agent list from API) |
| 4 | Docker-first testing | ✅ | Part of Flask template rendering |
| 5 | aria_memories only writable path | ❌ | No file writes |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- S6-01 (Chat UI — sidebar integrates into the chat template)
- S2-01 (Chat engine — session CRUD endpoints must exist)
- S4-01 (Agent pool — `/api/engine/agents` endpoint for agent list)

## Verification
```bash
# 1. Sidebar element exists:
curl -s http://aria-web:5000/chat/ | grep -c "chat-sidebar"
# EXPECTED: at least 2 (element + CSS)

# 2. Agent selector present:
curl -s http://aria-web:5000/chat/ | grep -c "agentSelector"
# EXPECTED: at least 2

# 3. Session search present:
curl -s http://aria-web:5000/chat/ | grep -c "sessionSearch"
# EXPECTED: at least 2

# 4. New chat button present:
curl -s http://aria-web:5000/chat/ | grep -c "createNewSession"
# EXPECTED: at least 1
```

## Prompt for Agent
```
Build the session sidebar for the Aria chat page.

FILES TO READ FIRST:
- src/web/templates/engine_chat.html (full file — chat UI from S6-01)
- src/web/templates/base.html (lines 1-50 — base template structure)
- src/api/routers/chat.py (session CRUD endpoints)
- aria_engine/agent_pool.py (agent list endpoint)

STEPS:
1. Read engine_chat.html to understand the layout
2. Add sidebar HTML as first child of .chat-container
3. Add sidebar CSS for collapsible design
4. Implement loadSessions() — fetch from /api/engine/sessions
5. Implement loadAgents() — fetch from /api/engine/agents
6. Implement filterSessions() — client-side agent + text filter
7. Implement switchSession() — navigate to different session
8. Implement createNewSession() — reset chat state
9. Implement deleteSession() — with confirmation
10. Make responsive: sidebar as overlay on mobile

CONSTRAINTS:
- Sidebar must not break the existing chat layout
- Responsive: collapses on mobile (<768px)
- Session list fetched from API, not hardcoded
- Active session must be highlighted
```
