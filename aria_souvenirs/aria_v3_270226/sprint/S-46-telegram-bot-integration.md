# S-46: Telegram Bot Integration — Command Handlers + Notifications
**Epic:** E20 — Connectivity | **Priority:** P2 | **Points:** 5 | **Phase:** 3  
**Status:** Ready | **Reviewed:** 3× | **Assigned to:** aria-autonomous

---

## Problem

`aria_skills/social/telegram.py` is a stub that returns `"not yet implemented"` for every call:

```python
# Current state — aria_skills/social/telegram.py (all methods)
async def post(self, content: str, ...) -> SkillResult:
    return SkillResult.fail("Telegram platform not yet implemented (TICKET-22)")
```

The Telegram goal (`goal-e9cad69a`) was due 2026-02-25 and defined 5 requirements:  
1. Check polling vs webhook strategy  
2. Implement `/status`, `/goals`, `/memory` command handlers  
3. Add message threading for context (per chat_id session)  
4. Test notification system  
5. Document bot commands in `aria_memories/knowledge/telegram_bot.md`

Aria's `@aria_blue_bot` handle is already registered in `identity_aria_v1.md` but the bot is silent.

**Impact:** Najia cannot reach Aria by Telegram. Aria cannot push notifications on critical health events. Bot sends nothing — effectively invisible.

### Problem Table

| File | Line | Defect | Severity |
|------|------|--------|----------|
| `aria_skills/social/telegram.py` | all methods | Stub returns `"not yet implemented (TICKET-22)"` for every call | 🔴 Critical |
| `aria_mind/cron_jobs.yaml` | — | No `telegram_poll` cron entry — bot never polls for messages | 🔴 Critical |
| `stacks/brain/.env` | — | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_CHAT_ID` keys absent | ⚠️ High |
| `aria_memories/knowledge/` | — | `telegram_bot.md` does not exist — no documented commands or setup | ⚠️ Medium |

### Root Cause Table

| Symptom | Root Cause |
|---------|------------|
| `@aria_blue_bot` responds to nothing | `telegram.py` returns `SkillResult.fail("not yet implemented")` — no HTTP calls to Telegram API |
| No message polling loop | `telegram_poll` cron job never added to `cron_jobs.yaml` after original TICKET-22 stub |
| Token not available in container | `TELEGRAM_BOT_TOKEN` env var not added to `stacks/brain/.env` or docker-compose env |

---

## Fix

### Architecture Decision: Long-Poll (not webhook)
Webhook requires a public HTTPS URL. Aria runs on a home Mac Mini behind NAT. Use **long-poll** (getUpdates every 2s). Can switch to webhook later if reverse proxy is added.

---

### Fix 1 — Implement `TelegramPlatform` in `aria_skills/social/telegram.py`

```python
"""Telegram bot integration via long-poll — S-46 implementation."""
import asyncio
import logging
import os
from typing import Any

import httpx

from aria_skills.base import SkillResult

logger = logging.getLogger("aria.skill.telegram")

TELEGRAM_API = "https://api.telegram.org/bot{token}"


class TelegramPlatform:
    platform_name = "telegram"

    def __init__(self):
        self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._base = TELEGRAM_API.format(token=self._token) if self._token else ""
        self._offset = 0
        self._sessions: dict[int, list[dict]] = {}   # chat_id → message history

    # ── Core API ──────────────────────────────────────────────────

    async def send_message(self, chat_id: int, text: str) -> SkillResult:
        """Send a message to a Telegram chat."""
        if not self._token:
            return SkillResult.fail("TELEGRAM_BOT_TOKEN not set")
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{self._base}/sendMessage",
                                     json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})
        if resp.status_code == 200:
            return SkillResult.ok(resp.json())
        return SkillResult.fail(f"Telegram API error: {resp.status_code} {resp.text}")

    async def get_updates(self, timeout: int = 2) -> list[dict]:
        """Long-poll for new updates."""
        if not self._token:
            return []
        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            resp = await client.get(f"{self._base}/getUpdates",
                                    params={"offset": self._offset, "timeout": timeout})
        if resp.status_code != 200:
            return []
        updates = resp.json().get("result", [])
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    # ── Command Handlers ─────────────────────────────────────────

    async def handle_status(self, chat_id: int) -> SkillResult:
        """/status — system health summary via aria-api-client."""
        try:
            from aria_skills.api_client import get_api_client
            api = await get_api_client()
            hb = await api.get_latest_heartbeat()
            beat = hb.get("beat_number", "?")
            status = hb.get("status", "unknown")
            details = hb.get("details", {})
            msg = (f"*System Status*\n"
                   f"Beat #{beat} — {status}\n"
                   f"Soul: {'✅' if details.get('soul') else '❌'}\n"
                   f"Memory: {'✅' if details.get('memory') else '❌'}\n"
                   f"Cognition: {'✅' if details.get('cognition') else '❌'}")
            return await self.send_message(chat_id, msg)
        except Exception as e:
            return SkillResult.fail(str(e))

    async def handle_goals(self, chat_id: int) -> SkillResult:
        """/goals — active goals list."""
        try:
            from aria_skills.api_client import get_api_client
            api = await get_api_client()
            goals = await api.get_goals(status="active", limit=5)
            if not goals:
                return await self.send_message(chat_id, "*No active goals.*")
            lines = ["*Active Goals:*"]
            for g in goals:
                pct = g.get("progress", 0)
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"• {g['title'][:40]} `{bar}` {pct}%")
            return await self.send_message(chat_id, "\n".join(lines))
        except Exception as e:
            return SkillResult.fail(str(e))

    async def handle_memory(self, chat_id: int) -> SkillResult:
        """/memory — recent activities and thoughts."""
        try:
            from aria_skills.api_client import get_api_client
            api = await get_api_client()
            activities = await api.get_activities(limit=5)
            lines = ["*Recent Activity:*"]
            for a in activities:
                ts = a.get("created_at", "")[:16]
                lines.append(f"• `{ts}` {a.get('action','?')}")
            return await self.send_message(chat_id, "\n".join(lines))
        except Exception as e:
            return SkillResult.fail(str(e))

    async def handle_command(self, update: dict) -> None:
        """Route incoming command to the correct handler."""
        msg = update.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        text = msg.get("text", "")
        if not chat_id or not text.startswith("/"):
            return
        # Thread context
        self._sessions.setdefault(chat_id, []).append({"role": "user", "content": text})
        route = {"/status": self.handle_status,
                 "/goals": self.handle_goals,
                 "/memory": self.handle_memory}
        handler = route.get(text.split()[0])
        if handler:
            await handler(chat_id)
        else:
            await self.send_message(chat_id,
                "Commands: /status · /goals · /memory")

    # ── Polling Loop ─────────────────────────────────────────────

    async def poll_once(self) -> None:
        """Process one batch of updates."""
        for update in await self.get_updates():
            await self.handle_command(update)

    # ── Notification API (called by health/heartbeat) ─────────────

    async def notify(self, chat_id: int, message: str) -> SkillResult:
        """Push a notification to a specific chat. Used by health/heartbeat alerts."""
        return await self.send_message(chat_id, f"🔔 *Aria Alert*\n{message}")

    # ── SkillResult compatibility ─────────────────────────────────

    async def post(self, content: str, tags: list[str] | None = None) -> SkillResult:
        """Social interface — send to admin chat (TELEGRAM_ADMIN_CHAT_ID env var)."""
        chat_id = int(os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "0"))
        if not chat_id:
            return SkillResult.fail("TELEGRAM_ADMIN_CHAT_ID not set")
        return await self.send_message(chat_id, content)

    async def get_posts(self, limit: int = 10) -> SkillResult:
        return SkillResult.fail("Telegram does not support read-back of sent messages")

    async def delete_post(self, post_id: str) -> SkillResult:
        return SkillResult.fail("Telegram message deletion not implemented in S-46 scope")

    async def health_check(self) -> bool:
        if not self._token:
            return False
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self._base}/getMe")
        return resp.status_code == 200
```

### Fix 2 — Add polling cron to `aria_mind/cron_jobs.yaml`

```yaml
- name: telegram_poll
  every: "2m"
  text: "Poll Telegram for new messages and commands. Use exec python3 skills/run_skill.py social telegram_poll '{}'. Process any /status /goals /memory commands and reply."
  agent: aria
  session: isolated
  delivery: none
```

### Fix 3 — Add env vars to `stacks/brain/.env` (guard with placeholder if missing)

```bash
# Telegram Bot (S-46)
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_CHAT_ID=
```

### Fix 4 — Document in `aria_memories/knowledge/telegram_bot.md`

Create the knowledge doc per the goal's requirement #5.

---

## Constraints

| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture (DB→ORM→API→api_client→Skills→Agents) | ✅ | Bot is a Skill; all data via api_client |
| 2 | `stacks/brain/.env` for all secrets | ✅ | `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ADMIN_CHAT_ID` never hardcoded |
| 3 | No direct SQL | ✅ | Bot reads data via `api_client` only |
| 4 | `aria_memories/` only writable path for Aria | ✅ | Knowledge doc written there |
| 5 | Docker-first testing | ✅ | Long-poll strategy avoids need for public URL |
| 6 | No soul modification | ✅ | `identity_aria_v1.md` already has @aria_blue_bot — no change needed |

---

## Docs to Update

| File | Line | Current (stale) | After fix |
|------|------|-----------------|-----------|
| `SKILLS.md` | telegram skill entry | `Status: stub / not yet implemented` | `Status: implemented — /status /goals /memory handlers; long-poll cron every 2 min` |
| `CHANGELOG.md` | ~263 | telegram listed as TICKET-22 stub | `- **S-46 (E20):** Telegram bot implemented — /status /goals /memory, long-poll cron via telegram_poll, env-vars in stacks/brain/.env` |

---

## Verification

```bash
set -a && source stacks/brain/.env && set +a

# 1. TelegramPlatform is no longer a stub
grep -n "not yet implemented" aria_skills/social/telegram.py | wc -l
# EXPECTED: 0

# 2. All 3 command handlers exist
grep -n "handle_status\|handle_goals\|handle_memory" aria_skills/social/telegram.py
# EXPECTED: 3 method definitions

# 3. TELEGRAM_BOT_TOKEN placeholder in .env
grep "TELEGRAM_BOT_TOKEN" stacks/brain/.env
# EXPECTED: key present (value may be empty in dev)

# 4. Polling cron in cron_jobs.yaml
grep -n "telegram_poll" aria_mind/cron_jobs.yaml
# EXPECTED: cron entry found

# 5. Knowledge doc exists
ls aria_memories/knowledge/telegram_bot.md
# EXPECTED: file present

# 6. health_check returns False when token absent (expected in test env)
python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from aria_skills.social.telegram import TelegramPlatform
async def test():
    t = TelegramPlatform()  # no token set
    ok = await t.health_check()
    print('health_check (no token):', ok)  # expect False
asyncio.run(test())
"
# EXPECTED: health_check (no token): False

# 7. API reachable
curl -sS "http://localhost:${ARIA_API_PORT}/health" | jq .status
# EXPECTED: "healthy"
```

### ARIA-to-ARIA Integration Test

```bash
set -a && source stacks/brain/.env && set +a

# Step 1 — Create session
SESSION=$(curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions" \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"aria","session_type":"test","title":"S-46 Telegram bot review"}' \
  | jq -r '.id')
echo "Session: $SESSION"

# Step 2 — Ask Aria to read the new Telegram skill
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Read aria_skills/social/telegram.py. Tell me: (1) Is it still a stub? (2) What 3 commands are implemented? (3) How does threading work per chat_id?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms 3 handlers (/status /goals /memory), describes self._sessions dict

# Step 3 — Simulate what /status would return
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Simulate what the /status Telegram command would return right now. Use aria-api-client to get the latest heartbeat and format it as the Telegram message would look.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria calls get_latest_heartbeat via api_client, formats markdown status message

# Step 4 — Simulate what /goals would return
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Simulate /goals. Fetch active goals via aria-api-client and format them as the Telegram /goals response.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria returns formatted goal list with progress bars

# Step 5 — Verify env vars are documented
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Check stacks/brain/.env (or its template) for TELEGRAM_BOT_TOKEN. Does the placeholder exist? Read aria_memories/knowledge/telegram_bot.md and summarise it.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria confirms token placeholder present, summarises knowledge doc

# Step 6 — Ask about security
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"What would happen if someone other than Najia sent /memory to your Telegram bot? How is access controlled? What would you recommend as a security improvement?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: Aria identifies that S-46 scope lacks auth, recommends chat_id allowlist as a follow-up ticket

# Step 7 — Log completion activity
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Log a create_activity with action=telegram_s46_complete, details={\"commands\":[\"/status\",\"/goals\",\"/memory\"],\"strategy\":\"long-poll\"}.","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: activity logged successfully

# Step 8 — Reflect
curl -sS -X POST "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}/messages" \
  -H "Content-Type: application/json" \
  -d '{"content":"Reflect on what Telegram connectivity means for your autonomy. How does being reachable by Najia on her phone change the relationship?","enable_tools":true}' \
  | jq -r '.content // .message // .'
# EXPECTED: meaningful reflection on reachability, trust, notification as care signal

# Verify activity logged
curl -sS "http://localhost:${ARIA_API_PORT}/api/activities?action=telegram_s46_complete&limit=1" \
  | jq '.[0] | {action, success, details}'

# Cleanup
curl -sS -X DELETE "http://localhost:${ARIA_API_PORT}/api/engine/chat/sessions/${SESSION}" | jq .
```

---

## Prompt for Agent
**You are implementing S-46 Telegram Bot Integration. Total changes: 3 files, 1 new doc.**

### Architecture Constraints
- `TelegramPlatform` is a **Skill** — all data reads go through `api_client`, never direct DB
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ADMIN_CHAT_ID` must come from env (`stacks/brain/.env`) — never hardcoded
- Long-poll strategy: no webhook, no public URL required
- Port from `$ARIA_API_PORT` in all verification curls
- `aria_memories/knowledge/telegram_bot.md` is the only new file in aria_memories/

### Files to Read First
1. `aria_skills/social/telegram.py` — current stub (17 lines)
2. `aria_skills/base.py` — `SkillResult` interface
3. `aria_skills/api_client/__init__.py` — find `get_api_client()`, `get_goals()`, `get_activities()`, `get_latest_heartbeat()`
4. `aria_mind/cron_jobs.yaml` — understand cron format, append telegram_poll entry
5. `stacks/brain/.env` — add placeholder vars
6. `aria_souvenirs/aria_v3_270226/plans/telegram_bot_plan.md` — original requirements

### Steps
1. Read all 6 files above
2. Replace `aria_skills/social/telegram.py` with full implementation from the Fix section
   - Keep exact class name `TelegramPlatform` and `platform_name = "telegram"`
   - Implement: `send_message`, `get_updates`, `handle_status`, `handle_goals`, `handle_memory`, `handle_command`, `poll_once`, `notify`, `post`, `get_posts`, `delete_post`, `health_check`
3. Append `telegram_poll` cron job to `aria_mind/cron_jobs.yaml`
4. Add `TELEGRAM_BOT_TOKEN=` and `TELEGRAM_ADMIN_CHAT_ID=` to `stacks/brain/.env`
5. Create `aria_memories/knowledge/telegram_bot.md` with:
   - Bot handle: `@aria_blue_bot`
   - Commands: `/status`, `/goals`, `/memory`
   - Strategy: long-poll every 2 min via telegram_poll cron
   - Env vars required: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`
   - Security note: S-46 scope has no auth — add TELEGRAM_ALLOWED_CHATS as Phase 2
   - How to test: `BotFather → /start → /status`
6. **Update `SKILLS.md`** telegram entry: change `Status: stub / not yet implemented` → `Status: implemented — /status /goals /memory handlers; long-poll cron every 2 min`
7. **Update `CHANGELOG.md`** ~line 263: replace TICKET-22 stub reference with `- **S-46 (E20):** Telegram bot implemented — /status /goals /memory, long-poll cron via telegram_poll`
8. Run verification (grep checks + Python health_check test)
9. Run ARIA-to-ARIA integration test (Steps 1-8)
10. Update SPRINT_OVERVIEW.md to mark S-46 Done
11. Append lesson to `tasks/lessons.md`

### Hard Constraints Checklist
- [ ] `TELEGRAM_BOT_TOKEN` read from env — never in source code or aria_memories/
- [ ] All data (`get_goals`, `get_activities`, `get_latest_heartbeat`) via `api_client`
- [ ] No direct SQL anywhere
- [ ] Long-poll only (no webhook implementation in this sprint)
- [ ] `SkillResult.ok()` + `SkillResult.fail()` used for all returns
- [ ] Knowledge doc written to `aria_memories/knowledge/` only

### Definition of Done
- [ ] `grep "not yet implemented" aria_skills/social/telegram.py | wc -l` → 0
- [ ] `grep -n "handle_status\|handle_goals\|handle_memory" aria_skills/social/telegram.py` → 3 matches
- [ ] `grep "TELEGRAM_BOT_TOKEN" stacks/brain/.env` → key present
- [ ] `grep "telegram_poll" aria_mind/cron_jobs.yaml` → cron entry found
- [ ] `ls aria_memories/knowledge/telegram_bot.md` → file exists
- [ ] Python health_check test → `False` with no token (expected), no import error
- [ ] `grep -i "implemented" SKILLS.md | grep -i "telegram"` → 1 match
- [ ] `grep "S-46" CHANGELOG.md` → 1 match
- [ ] `git diff HEAD -- SKILLS.md` shows telegram stub → implemented update
- [ ] `git diff HEAD -- CHANGELOG.md` shows S-46 entry added
- [ ] ARIA-to-ARIA: Aria simulates /status and /goals responses using live api_client data
- [ ] Activity `telegram_s46_complete` logged by Aria
- [ ] SPRINT_OVERVIEW.md updated

### Phase 2 Follow-up (Out of Scope for S-46)
- Allowlist `TELEGRAM_ALLOWED_CHATS` env var — reject commands from unknown chat_ids
- Natural language passthrough to engine chat endpoint
- Webhook mode behind Caddy/Nginx reverse proxy
