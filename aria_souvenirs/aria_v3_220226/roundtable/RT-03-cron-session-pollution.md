# RT-03: Cron Sessions Pollute the Chat Sidebar

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P1 🟡 | **Points:** 2 | **Phase:** 2

---

## Roundtable Exchange

**SM:** The sessions page and chat sidebar show `session_type = "cron"` sessions mixed
with real user chat sessions. There's a "Show cron sessions" toggle on the sessions admin
page — but the chat sidebar (engine_chat.html) has no such filter.

**Aria (PO):** The chat sidebar should ONLY show `session_type = "chat"` (and "roundtable"
if the user wants it). Cron and internal sessions are operational noise.
Acceptance: chat sidebar requests sessions with `?session_type=chat` by default.
A toggle labelled "Show agent sessions" can optionally expand it.

---

## Problem

- `engine_chat.html` template: session list fetch calls `GET /api/engine/sessions` with no
  `session_type` filter — returns all types including cron, roundtable, swarm
- Users see 100+ cron execution sessions cluttering their personal chat history
- Existing toggle in `sessions.html` is admin-only, not present in chat UI

---

## Root Cause

Session list API endpoint defaults to `session_type=None` (all types).
Chat sidebar JS was built without type filtering.

---

## Fix Plan

In `engine_chat.html` JavaScript, change the sessions fetch:
```javascript
// BEFORE:
const res = await fetch('/api/engine/sessions?limit=50&order=desc');

// AFTER:
const res = await fetch('/api/engine/sessions?limit=50&order=desc&session_type=chat');
```

Add a small toggle button in the chat sidebar header:
```html
<button id="show-all-sessions-toggle" title="Show agent sessions" onclick="toggleAllSessions()">
  🤖
</button>
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Frontend-only change + API query param |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Test in local browser |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Verify session_type filter works:
curl "http://localhost:8000/api/engine/sessions?session_type=chat&limit=5" | python3 -m json.tool
# EXPECTED: all returned sessions have "session_type": "chat"

# 2. Verify no cron sessions in chat sidebar (manual browser check):
# Open /chat — sidebar should not show entries with "cron" badge
```

---

## Prompt for Agent

Read: `src/web/templates/engine_chat.html` lines 1–200 (JS section for session list loading).

Steps:
1. Find the `fetch('/api/engine/sessions` call in `engine_chat.html`
2. Add `&session_type=chat` to the URL
3. Add a "🤖 Show all" toggle button in the sidebar actions bar
4. Toggle switches between `session_type=chat` and no filter (all)

Constraints: 4 (browser test in Docker).
Dependencies: None — standalone frontend change.
