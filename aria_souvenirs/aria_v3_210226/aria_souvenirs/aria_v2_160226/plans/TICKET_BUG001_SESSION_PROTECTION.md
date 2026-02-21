# Sprint Ticket: BUG-001 — Session Protection
**Priority:** P0 (Critical) | **Points:** 1 | **Phase:** 1  
**Estimate:** 15 minutes

## Problem
`session_manager` skill's `delete_session()` at `aria_skills/session_manager/__init__.py:212` and `prune_sessions()` at line 300 have **zero protection** against deleting:
1. The currently active session (self-destruction)
2. The main agent session (permanent context loss)

Any caller can pass any session_id and destroy the active conversation.

## Root Cause
No validation exists between the `session_id` parameter and the running environment's `OPENCLAW_SESSION_ID`. The `prune_sessions()` method iterates all sessions and calls `delete_session()` for every stale one — including the active and main sessions.

## Fix

### File: `aria_skills/session_manager/__init__.py`

**1. Add helper function after line 82 (`_epoch_ms_to_iso`):**

```python
def _is_cron_or_subagent_session(session_key: str) -> bool:
    """Check if a session key belongs to a cron job or subagent (safe to delete)."""
    if not session_key:
        return False
    return any(marker in session_key for marker in [":cron:", ":subagent:", ":run:"])
```

**2. Patch `delete_session()` — add after line 229 (`agents = [agent] if agent else...`):**

```python
        # Session protection: prevent deleting current active session
        current_sid = os.environ.get("OPENCLAW_SESSION_ID", "")
        if current_sid and session_id == current_sid:
            return SkillResult.fail(
                f"Cannot delete current session {session_id}: "
                "this would destroy the active conversation context."
            )

        # Protect main agent sessions (non-cron, non-subagent)
        for ag in (agents if agents else _list_all_agents()):
            idx = _load_sessions_index(ag)
            for key, val in (idx or {}).items():
                if isinstance(val, dict) and val.get("sessionId") == session_id:
                    if ag == "main" and not _is_cron_or_subagent_session(key):
                        return SkillResult.fail(
                            f"Cannot delete main agent session {session_id} (key={key})."
                        )
```

**3. Patch `prune_sessions()` — add after the `to_delete` list is built (after line 348, before `deleted_ids`):**

```python
        # Filter out protected sessions before deletion
        current_sid = os.environ.get("OPENCLAW_SESSION_ID", "")
        if current_sid:
            to_delete = [s for s in to_delete if s.get("id", s.get("sessionId", "")) != current_sid]
        to_delete = [
            s for s in to_delete
            if not (s.get("agentId") == "main" and not _is_cron_or_subagent_session(s.get("key", "")))
        ]
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | N/A | No DB access, only session file manipulation |
| 2 | .env for secrets | N/A | Uses `OPENCLAW_SESSION_ID` env var (runtime) |
| 3 | models.yaml source of truth | N/A | No model references |
| 4 | Docker-first testing | YES | Test via `run_skill.py` inside container |
| 5 | aria_memories only writable | N/A | Modifies clawdbot session files |
| 6 | No soul modification | N/A | |

## Dependencies
None — this is the first ticket and blocks all others.

## Verification
```bash
# 1. Helper function exists:
grep -n "_is_cron_or_subagent_session" aria_skills/session_manager/__init__.py
# EXPECTED: function definition found

# 2. Protection in delete_session:
grep -n "OPENCLAW_SESSION_ID" aria_skills/session_manager/__init__.py
# EXPECTED: 2+ matches (delete_session + prune_sessions)

# 3. Protection in prune_sessions:
grep -n "Cannot delete" aria_skills/session_manager/__init__.py
# EXPECTED: 2 matches
```

## Prompt for Agent
```
Read aria_skills/session_manager/__init__.py (full file, 506 lines).
Add _is_cron_or_subagent_session() helper after _epoch_ms_to_iso().
In delete_session(), after agent resolution (line ~229), add current session + main agent protection.
In prune_sessions(), after to_delete list is built (line ~348), filter out protected sessions.
os is already imported (line 17). SkillResult is already imported (line 24).
Run grep to verify all 3 patches applied.
```
