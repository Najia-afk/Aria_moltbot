"""
Session Protection Fix prototype
Prevents deletion of main agent session to preserve context.

This file documents the patch to apply to:
/app/skills/aria_skills/session_manager/__init__.py
"""

import os
from datetime import datetime, timezone, timedelta


# ===========================
# Helper Functions (to add)
# ===========================

def _get_current_session_id() -> str | None:
    """
    Get the current session ID from the environment.

    Aria sets session ID in environment when running a session.
    """
    return os.environ.get("ARIA_SESSION_ID")


def _get_agent_name() -> str:
    """
    Get current agent name from config/context.

    Returns: e.g., "main", "analyst", "creator"
    """
    # Option 1: From ARIA_AGENT_ID env var
    agent = os.environ.get("ARIA_AGENT_ID", "")

    # Option 2: From config (if skill has access)
    # self._config.agent_id if available

    return agent or "main"


def _is_cron_or_subagent_session(session_key: str) -> bool:
    """
    Check if a session key indicates it's a cron or subagent session.

    Examples:
        - :cron:moltbook_check
        - :subagent:task_123
        - :run:health_check
    """
    if not session_key:
        return False
    return any(marker in session_key for marker in [":cron:", ":subagent:", ":run:"])


# ===========================
# Modified delete_session Method
# ===========================

async def delete_session_fixed(
    self,
    session_id: str = "",
    agent: str = "",
    **kwargs
):
    """
    Delete a session with protection for main agent session.

    PATCH the existing delete_session method in SessionManagerSkill
    by adding these checks at the BEGINNING of the function.
    """
    if not session_id:
        session_id = kwargs.get("session_id", "")
    if not session_id:
        return SkillResult.fail("session_id is required")

    agent = agent or kwargs.get("agent", "")

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # ðŸ›¡ï¸ PROTECTION CHECKS (NEW CODE)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # 1. Check if this is the current session
    current_session_id = _get_current_session_id()
    if session_id == current_session_id:
        return SkillResult.fail(
            f"Cannot delete current session {session_id}. "
            "This would destroy active conversation context. "
            "Use 'cleanup_after_delegation' for sub-agents only."
        )

    # 2. Check if this is a main agent session
    # Load sessions.json for the specified agent
    agents = [agent] if agent else _list_all_agents()

    for ag in agents:
        index = _load_sessions_index(ag)

        for key, value in index.items():
            if isinstance(value, dict) and value.get("sessionId") == session_id:
                # Is this a main agent session?
                is_main_agent = (
                    ag == "main" and
                    not _is_cron_or_subagent_session(key)
                )

                if is_main_agent:
                    return SkillResult.fail(
                        f"Cannot delete main agent session {session_id}. "
                        "Main sessions are preserved to maintain conversation context. "
                        "Only cron and sub-agent sessions can be deleted automatically."
                    )

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Existing delete logic continues below...
    # (keep all the existing deletion code unchanged)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # ... rest of the original delete_session function ...


# ===========================
# Modified prune_sessions Method
# ===========================

async def prune_sessions_fixed(
    self,
    max_age_minutes: int = 0,
    dry_run: bool = False,
    **kwargs,
):
    """
    Prune stale sessions with protection for current session.

    PATCH the existing prune_sessions method by adding filter BEFORE deletion.
    """
    # ... existing logic to build list of sessions to delete ...

    list_result = await self.list_sessions()
    if not list_result.success:
        return list_result

    sessions = list_result.data.get("sessions", [])
    now = datetime.now(timezone.utc)
    max_age_minutes = max_age_minutes or self._stale_threshold_minutes
    cutoff = now - timedelta(minutes=int(max_age_minutes))

    to_delete = []
    for sess in sessions:
        ts_str = sess.get("updatedAt") or ""
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    to_delete.append(sess)
            except (ValueError, TypeError):
                to_delete.append(sess)

    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # ðŸ›¡ï¸ FILTER: Remove current session from deletion candidates (NEW)
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    current_session_id = _get_current_session_id()
    if current_session_id:
        original_count = len(to_delete)
        to_delete = [
            s for s in to_delete
            if s.get("sessionId") != current_session_id
        ]
        if len(to_delete) < original_count:
            print(f"â„¹ï¸  Protected current session {current_session_id} from pruning")

    # Also filter out main agent sessions
    to_delete_filtered = []
    for sess in to_delete:
        # Skip main agent sessions
        if sess.get("agentId") == "main" and not _is_cron_or_subagent_session(sess.get("key", "")):
            continue
        to_delete_filtered.append(sess)

    to_delete = to_delete_filtered
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

    # Continue with existing deletion logic...
    # (rest of prune_sessions unchanged)


# ===========================
# Complete Patched delete_session
# ===========================

def get_patched_delete_session():
    """
    Returns the complete patched delete_session code to replace in __init__.py.

    Copy this function to replace the existing delete_session method.
    """
    return '''
    async def delete_session(self, session_id: str = "", agent: str = "", **kwargs) -> SkillResult:
        """
        Delete a session: remove from aria-api filesystem, mark ended in PG.

        PROTECTION: Cannot delete current session or main agent session.

        1. Remove all matching keys from sessions.json
        2. Archive the .jsonl transcript (rename to .deleted.<ts>)
        3. PATCH aria-api to set status=ended (keeps history at /sessions)
        """
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail("session_id is required")
        agent = agent or kwargs.get("agent", "")

        # ðŸ›¡ï¸ PROTECTION: Prevent deleting current session
        current_session_id = _get_current_session_id()
        if session_id == current_session_id:
            return SkillResult.fail(
                f"Cannot delete current session {session_id}: "
                "This would destroy the active conversation context. "
                "Use 'cleanup_after_delegation' for sub-agent sessions only."
            )

        agents = [agent] if agent else _list_all_agents()
        removed_keys: list[str] = []
        archived = False

        for ag in agents:
            index = _load_sessions_index(ag)
            if not index:
                continue

            keys_to_remove = [
                k for k, v in index.items()
                if isinstance(v, dict) and v.get("sessionId") == session_id
            ]
            if not keys_to_remove:
                continue

            # ðŸ›¡ï¸ PROTECTION: Check if this is a main agent session
            for k in keys_to_remove:
                # Main agent session = agent=="main" AND not a cron/subagent key
                if ag == "main" and not _is_cron_or_subagent_session(k):
                    return SkillResult.fail(
                        f"Cannot delete main agent session {session_id}: "
                        "Main sessions are preserved for context continuity. "
                        "Only cron/sub-agent sessions can be deleted."
                    )

            # Proceed with deletion
            for k in keys_to_remove:
                del index[k]
                removed_keys.append(k)

            _save_sessions_index(index, ag)

            if _archive_transcript(session_id, ag):
                archived = True

        if not removed_keys:
            return SkillResult.ok({
                "deleted": session_id,
                "removed_keys": [],
                "transcript_archived": False,
                "pg_status_updated": await self._mark_ended_in_pg(session_id),
                "message": f"Session {session_id} not found (already deleted)",
            })

        pg_updated = await self._mark_ended_in_pg(session_id)

        return SkillResult.ok({
            "deleted": session_id,
            "removed_keys": removed_keys,
            "transcript_archived": archived,
            "pg_status_updated": pg_updated,
            "message": f"Session {session_id} deleted ({len(removed_keys)} keys)",
        })
    '''


def get_patched_prune_sessions():
    """
    Returns the complete patched prune_sessions code.
    """
    return '''
    async def prune_sessions(
        self,
        max_age_minutes: int = 0,
        dry_run: bool = False,
        **kwargs,
    ) -> SkillResult:
        """
        Prune stale sessions with protection for current/main sessions.

        Args:
            max_age_minutes: Delete sessions older than this
            dry_run: If true, list candidates without deleting
        """
        if not max_age_minutes:
            max_age_minutes = kwargs.get("max_age_minutes", self._stale_threshold_minutes)
            if isinstance(max_age_minutes, str):
                max_age_minutes = int(max_age_minutes) if max_age_minutes else self._stale_threshold_minutes

        dry_run = kwargs.get("dry_run", dry_run)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("true", "1", "yes")

        list_result = await self.list_sessions()
        if not list_result.success:
            return list_result

        sessions = list_result.data.get("sessions", [])
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=int(max_age_minutes))

        to_delete = []
        for sess in sessions:
            ts_str = sess.get("updatedAt") or ""
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        to_delete.append(sess)
                except (ValueError, TypeError):
                    to_delete.append(sess)

        # ðŸ›¡ï¸ PROTECTION: Filter out current session
        current_session_id = _get_current_session_id()
        if current_session_id:
            to_delete = [s for s in to_delete if s.get("sessionId") != current_session_id]

        # ðŸ›¡ï¸ PROTECTION: Filter out main agent sessions
        to_delete = [
            s for s in to_delete
            if not (s.get("agentId") == "main" and
                    not _is_cron_or_subagent_session(s.get("key", "")))
        ]

        deleted_ids: list[str] = []
        errors: list[dict[str, str]] = []

        if not dry_run:
            for sess in to_delete:
                sid = sess.get("id") or sess.get("sessionId", "")
                ag = sess.get("agentId", "")
                if sid:
                    r = await self.delete_session(session_id=sid, agent=ag)
                    if r.success:
                        deleted_ids.append(sid)
                    else:
                        errors.append({"id": sid, "error": r.error or "unknown"})

        return SkillResult.ok({
            "total_sessions": len(sessions),
            "pruned_count": len(to_delete),
            "kept_count": len(sessions) - len(to_delete),
            "dry_run": dry_run,
            "deleted_ids": deleted_ids if not dry_run else [s.get("id", "") for s in to_delete],
            "errors": errors,
            "threshold_minutes": max_age_minutes,
        })
    '''


# ===========================
# Application Instructions
# ===========================

PATCH_INSTRUCTIONS = """
## How to Apply the Session Protection Fix

### Step 1: Add Helper Functions
Add these functions to the TOP of /app/skills/aria_skills/session_manager/__init__.py
(before the class definition):

```python
def _get_current_session_id() -> str | None:
    return os.environ.get("ARIA_SESSION_ID")

def _is_cron_or_subagent_session(session_key: str) -> bool:
    if not session_key:
        return False
    return any(marker in session_key for marker in [":cron:", ":subagent:", ":run:"])
```

### Step 2: Patch delete_session Method
Replace the entire `delete_session` method in the `SessionManagerSkill` class
with the code from `get_patched_delete_session()` above.

### Step 3: Patch prune_sessions Method
Replace the `prune_sessions` method with the code from `get_patched_prune_sessions()`.

### Step 4: Test
1. Try to delete current session (should fail with clear message)
2. Run `prune_sessions` (should skip current session)
3. Verify cron/subagent sessions still get deleted normally

### Step 5: Deploy
After testing, restart Aria gateway:
```bash
Aria gateway restart
```
"""

if __name__ == "__main__":
    print(PATCH_INSTRUCTIONS)
    print("\n" + "=" * 80)
    print("PATCHED delete_session:")
    print("=" * 80)
    print(get_patched_delete_session())
    print("\n" + "=" * 80)
    print("PATCHED prune_sessions:")
    print("=" * 80)
    print(get_patched_prune_sessions())
