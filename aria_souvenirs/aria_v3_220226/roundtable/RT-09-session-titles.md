# RT-09: Session Titles Stay "Untitled" for Empty Sessions

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P2 🟠 | **Points:** 2 | **Phase:** 3

---

## Roundtable Exchange

**SM:** When a user starts a chat, the session shows as "New Conversation" or a raw UUID
in the sidebar. Only after the first exchange does the chat engine attempt to auto-title it.
Empty/ghost sessions always appear as "Untitled" or "New Chat".

**Aria (PO):** Two things:
1. Ghost sessions (RT-01) disappear before needing titles — so this mainly affects sessions
   where the user typed something but the title generation failed.
2. For real sessions: auto-generate title from first 8 words of first user message,
   immediately (synchronously), so the sidebar updates without waiting for LLM title generation.
3. LLM-generated title (current behaviour) should still run async but the quick title
   appears first.

Acceptance:
- Session title = first 8 words of first user message, truncated + "..." if needed
- LLM-generated long title replaces it within 5 seconds
- Empty/untitled sessions marked with italic "— empty —" in sidebar

---

## Problem

`aria_engine/chat_engine.py` title generation: uses LLM to generate a summary title,
which takes 2–5 seconds. During that window the session shows a UUID or placeholder.
No immediate fallback title from message content.

---

## Root Cause

Title generation is async and waits for LLM response. No synchronous first-pass title.

---

## Fix Plan

In `chat_engine.py`, immediately after receiving first user message:

```python
# Quick title — first 8 words, instant, no LLM call
def _quick_title(self, content: str) -> str:
    words = content.split()[:8]
    title = " ".join(words)
    return title + ("..." if len(content.split()) > 8 else "")

# After creating/receiving first message:
quick = self._quick_title(user_message)
await mgr.update_session_title(session_id, quick)
# Then fire LLM title generation async (existing behaviour)
asyncio.create_task(self._generate_llm_title(session_id, user_message))
```

In `engine_chat.html`, show italic "— empty —" placeholder for 0-message sessions in sidebar:
```javascript
// In session list rendering:
const title = s.title || (s.message_count === 0 ? '<em>— empty —</em>' : s.session_id.slice(0,8));
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Engine layer for title generation |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ❌ | Not applicable |
| 4 | Docker-first testing | ✅ | Verify in browser after send |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Start chat, send first message — title should update within 1 second:
# Browser: sidebar session title changes from UUID to first-8-words immediately

# 2. Verify 0-message sessions show "— empty —" in sidebar:
# Any ghost session remaining shows italic placeholder

# 3. LLM title eventually replaces quick title (async):
# After ~5 seconds: title replaced by full LLM summary
```

---

## Prompt for Agent

Read: `aria_engine/chat_engine.py` (title generation section), `src/web/templates/engine_chat.html`
(session list rendering JS).

Steps:
1. Add `_quick_title(content)` to `ChatEngine`
2. Call it synchronously after first message received, fire LLM title as `asyncio.create_task`
3. In `engine_chat.html` session list render, show "— empty —" for 0-message sessions

Constraints: 1, 4. Dependencies: RT-01 (ghost sessions reduced), RT-06 (sidebar rendering).
