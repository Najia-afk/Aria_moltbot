# RT-06: Chat UI — No Agent Selector / Responder Identity Invisible

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P1 🟡 | **Points:** 3 | **Phase:** 2

---

## Roundtable Exchange

**SM:** Shiva says he only sees "Aria" in the chat. With 6+ agents configured
(aria, aria-talk, aria-analyst, aria-memeothy, aria-creative, aria-coder) there's
no way to choose who to talk to or to see which model just responded.

**Aria (PO):** Two things needed:
1. **Agent selector** in the chat header — a dropdown of available agents loaded from
   `GET /api/agents` (or `GET /api/engine/agents`). Defaults to `aria`.
2. **Responder badge** on each assistant message showing `agent_id` + `model` used.
   Already in the message data (`EngineChatMessage.agent_id`, `EngineChatMessage.model`).

Acceptance:
- User can select agent before sending first message
- Each assistant reply shows `🤖 aria-analyst · deepseek-free` badge
- Selection persists per session (stored in session.agent_id)

---

## Problem

`engine_chat.html` chat header — no agent dropdown or model indicator.
Assistant message rendering: only shows text content, no model/agent metadata.
`EngineChatMessage` already stores `agent_id` and `model` fields (verified in `db/models.py`).

---

## Root Cause

The chat frontend was built for a single-agent scenario. Multi-agent data is stored
in the DB but never surfaced to the user interface.

---

## Fix Plan

### Agent selector (chat header)
```html
<!-- In .chat-header-left, add after h2 -->
<select id="agent-selector" class="agent-select" title="Select agent">
  <option value="">Loading agents...</option>
</select>
```

```javascript
// Load agents from API
async function loadAgents() {
    const res = await fetch('/api/engine/agents?limit=20');
    const data = await res.json();
    const sel = document.getElementById('agent-selector');
    sel.innerHTML = data.agents.map(a =>
        `<option value="${a.id}">${a.display_name || a.id}</option>`
    ).join('');
}
```

### Responder badge on messages
```javascript
// In renderMessage() — add below content
if (role === 'assistant' && msg.agent_id) {
    const badge = document.createElement('div');
    badge.className = 'msg-badge';
    badge.textContent = `🤖 ${msg.agent_id}${msg.model ? ' · ' + msg.model.split('/').pop() : ''}`;
    bubble.appendChild(badge);
}
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend reads from API — no direct DB |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Browser test required |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Verify agents API returns list:
curl http://localhost:8000/api/engine/agents | python3 -m json.tool | grep -i "id\|display_name"
# EXPECTED: list with aria, aria-talk, aria-analyst etc.

# 2. Send message as aria-analyst and verify model badge appears:
# Open /chat, select "aria-analyst" in dropdown, send a message
# EXPECTED: reply shows badge "🤖 aria-analyst · <model>"

# 3. Verify agent_id stored in session:
curl http://localhost:8000/api/engine/sessions/CURRENT_SESSION_ID | \
  python3 -m json.tool | grep agent_id
# EXPECTED: "agent_id": "aria-analyst"
```

---

## Prompt for Agent

Read: `src/web/templates/engine_chat.html` (full, especially renderMessage() and chat header HTML),
`src/api/routers/engine_agents.py` (for the agents endpoint shape).

Steps:
1. Add `<select id="agent-selector">` to chat header HTML
2. Add `loadAgents()` JS function called on `DOMContentLoaded`
3. Pass selected `agent_id` in each chat request payload
4. In `renderMessage()`, add `.msg-badge` div for assistant messages with agent_id + model
5. Add CSS for `.agent-select` and `.msg-badge` in the `<style>` block

Constraints: 1, 4. Dependencies: RT-02 (model diversity must work for badge to show varied models).
