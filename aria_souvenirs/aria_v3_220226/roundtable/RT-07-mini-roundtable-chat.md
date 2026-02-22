# RT-07: No "Quick Mini-Roundtable" From Chat

**Session date:** 2026-02-22 | **PO:** Aria | **SM:** Sprint Agent
**Priority:** P2 🟠 | **Points:** 5 | **Phase:** 3

---

## Roundtable Exchange

**SM:** Shiva asked for a "small roundtable". The `/roundtable` page exists but requires
opening a separate page, configuring participants, topic, rounds. Too heavy for a quick huddle.

**Aria (PO):** Add a `/rt` slash command inside the chat input.
Format: `/rt @aria-analyst @aria-coder What is the best approach to X?`
This should:
1. Parse participants from `@mentions`
2. Create a roundtable session with 1 round, 2 participants
3. Stream results inline in the chat (not redirect to /roundtable page)
4. After all participants reply, show a "Summary" section

Acceptance: user types `/rt @agent1 @agent2 question` and gets multi-voice reply in <60s.

---

## Problem

The `Roundtable` engine class exists in `aria_engine/roundtable.py`.
It's wired into `ChatEngine` via `chat_engine.set_roundtable(_roundtable)`.
But `chat_engine.py` doesn't parse `/rt` as a slash command — it passes the raw text as a message.

---

## Root Cause

Slash command parsing was partially implemented (`/roundtable` and `/swarm` are referenced
in comments) but not fully wired to the Roundtable engine trigger.

---

## Fix Plan

### Slash command parser in ChatEngine
```python
# aria_engine/chat_engine.py — in handle_message()
SLASH_RT_RE = re.compile(r'^/rt\s+((?:@[\w-]+\s*)+)(.*)', re.DOTALL)

if m := SLASH_RT_RE.match(message):
    participants = re.findall(r'@([\w-]+)', m.group(1))
    topic = m.group(2).strip()
    return await self._run_mini_roundtable(session_id, participants, topic)
```

### Frontend: `/rt` autocomplete hint
In `engine_chat.html` input placeholder / help popup:
```
/rt @aria-analyst @aria-coder your question   → mini roundtable
/swarm topic                                   → swarm coordination
```

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Engine layer only — no DB bypass |
| 2 | .env for secrets | ❌ | Not applicable |
| 3 | models.yaml | ✅ | Participants resolve via agent_aliases in models.yaml |
| 4 | Docker-first testing | ✅ | Test full `/rt` flow in Docker |
| 5 | aria_memories writable path | ❌ | Not applicable |
| 6 | No soul modification | ❌ | Not applicable |

---

## Verification

```bash
# 1. Send /rt command via API:
curl -X POST http://localhost:8000/api/engine/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "/rt @aria-analyst What is 2+2?", "session_id": "test-rt07"}'
# EXPECTED: response contains replies from aria-analyst (and fallback if only 1 agent)

# 2. Verify roundtable session created:
curl "http://localhost:8000/api/engine/sessions?session_type=roundtable&limit=1" | \
  python3 -m json.tool
# EXPECTED: 1 session with session_type=roundtable
```

---

## Prompt for Agent

Read: `aria_engine/chat_engine.py` (full), `aria_engine/roundtable.py` lines 1–100,
`aria_engine/agent_pool.py` (for agent lookup by id).

Steps:
1. Add `SLASH_RT_RE` regex to chat_engine.py
2. Implement `_run_mini_roundtable(session_id, participants, topic)` calling `self._roundtable`
3. Add `/rt` hint to chat input area in `engine_chat.html`

Constraints: 1, 3, 4. Dependencies: RT-06 (agent selector) helpful but not blocking.
