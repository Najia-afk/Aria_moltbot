# aria_skills/session_manager/__init__.py
"""
Session management skill.

List, prune, and delete Aria engine sessions via the aria-api REST layer.
All session data lives in PostgreSQL (aria_engine.chat_sessions / chat_messages).

Tools:
  - list_sessions        — list active sessions (from DB via API)
  - delete_session       — delete a session + its messages
  - prune_sessions       — prune stale sessions older than N minutes
  - get_session_stats    — summary statistics
  - cleanup_after_delegation — delete a sub-agent session after completion
  - cleanup_orphans      — purge ghost sessions (0 messages, stale)
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class SessionManagerSkill(BaseSkill):
    """
    Manage Aria sessions — list, prune stale ones, delete by ID.

    All operations go through aria-api REST endpoints which read/write
    the PostgreSQL aria_engine schema (chat_sessions + chat_messages).
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._stale_threshold_minutes: int = int(
            config.config.get("stale_threshold_minutes", 60)
        )
        self._api = None

    @property
    def name(self) -> str:
        return "session_manager"

    async def initialize(self) -> bool:
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Session manager initialized (DB-backed via aria-api)")
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    # ── Internal helpers ───────────────────────────────────────────

    async def _fetch_sessions(
        self,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch sessions from the engine sessions API."""
        params: dict[str, Any] = {
            "limit": limit,
            "sort": "updated_at",
            "order": "desc",
        }
        result = await self._api.get("/engine/sessions", params=params)
        if not result.success:
            return []
        data = result.data if isinstance(result.data, dict) else {}
        return data.get("sessions", data.get("items", []))

    # ── Public tool functions ──────────────────────────────────────────

    @logged_method()
    async def list_sessions(self, agent: str = "", **kwargs) -> SkillResult:
        """
        List all active sessions from the database.

        Args:
            agent: Filter by agent_id (default: all agents).
        """
        agent = agent or kwargs.get("agent", "")
        try:
            sessions = await self._fetch_sessions()

            if agent:
                sessions = [s for s in sessions if s.get("agent_id") == agent]

            normalized = []
            for s in sessions:
                normalized.append({
                    "id": s.get("session_id") or s.get("id", ""),
                    "agent_id": s.get("agent_id", ""),
                    "session_type": s.get("session_type", "interactive"),
                    "status": s.get("status", "active"),
                    "title": s.get("title", ""),
                    "model": s.get("model", ""),
                    "message_count": s.get("message_count", 0),
                    "updated_at": s.get("updated_at") or s.get("last_message_at", ""),
                    "created_at": s.get("created_at", ""),
                })

            return SkillResult.ok({
                "session_count": len(normalized),
                "sessions": normalized,
            })
        except Exception as e:
            return SkillResult.fail(f"Error listing sessions: {e}")

    @logged_method()
    async def delete_session(self, session_id: str = "", agent: str = "", **kwargs) -> SkillResult:
        """
        Delete a session and all its messages from the database.

        Args:
            session_id: The session UUID to delete.
            agent: Unused (kept for backward compat).
        """
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail("session_id is required")

        current_sid = os.environ.get("ARIA_SESSION_ID", "")
        if current_sid and session_id == current_sid:
            return SkillResult.fail(
                f"Cannot delete current session {session_id}: "
                "this would destroy the active conversation context."
            )

        try:
            result = await self._api.delete(f"/engine/sessions/{session_id}")
            if result.success:
                return SkillResult.ok({
                    "deleted": session_id,
                    "message": f"Session {session_id} deleted from database",
                })
            else:
                return SkillResult.fail(
                    f"Failed to delete session {session_id}: {result.error}"
                )
        except Exception as e:
            return SkillResult.fail(f"Error deleting session {session_id}: {e}")

    @logged_method()
    async def prune_sessions(
        self,
        max_age_minutes: int = 0,
        dry_run: bool = False,
        **kwargs,
    ) -> SkillResult:
        """
        Prune stale sessions older than threshold.

        Args:
            max_age_minutes: Delete sessions older than this (default: config value or 60).
            dry_run: If true, list candidates without deleting.
        """
        if not max_age_minutes:
            max_age_minutes = kwargs.get("max_age_minutes", self._stale_threshold_minutes)
            if isinstance(max_age_minutes, str):
                max_age_minutes = int(max_age_minutes) if max_age_minutes else self._stale_threshold_minutes

        dry_run = kwargs.get("dry_run", dry_run)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("true", "1", "yes")

        sessions = await self._fetch_sessions(limit=500)
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=int(max_age_minutes))

        current_sid = os.environ.get("ARIA_SESSION_ID", "")

        to_delete: list[dict[str, Any]] = []
        kept: list[dict[str, Any]] = []

        for sess in sessions:
            sid = sess.get("session_id") or sess.get("id", "")

            # Never delete current session
            if current_sid and sid == current_sid:
                kept.append(sess)
                continue

            ts_str = (
                sess.get("last_message_at")
                or sess.get("updated_at")
                or sess.get("created_at")
                or ""
            )
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        to_delete.append(sess)
                    else:
                        kept.append(sess)
                    continue
                except (ValueError, TypeError):
                    pass
            to_delete.append(sess)

        deleted_ids: list[str] = []
        errors: list[dict[str, str]] = []

        if not dry_run:
            for sess in to_delete:
                sid = sess.get("session_id") or sess.get("id", "")
                if sid:
                    try:
                        r = await self._api.delete(f"/engine/sessions/{sid}")
                        if r.success:
                            deleted_ids.append(sid)
                        else:
                            errors.append({"id": sid, "error": r.error or "unknown"})
                    except Exception as e:
                        errors.append({"id": sid, "error": str(e)})

        return SkillResult.ok({
            "total_sessions": len(sessions),
            "pruned_count": len(to_delete),
            "kept_count": len(kept),
            "dry_run": dry_run,
            "deleted_ids": deleted_ids if not dry_run else [
                s.get("session_id") or s.get("id", "") for s in to_delete
            ],
            "errors": errors,
            "threshold_minutes": max_age_minutes,
        })

    @logged_method()
    async def get_session_stats(self, **kwargs) -> SkillResult:
        """Get summary statistics about current sessions."""
        try:
            sessions = await self._fetch_sessions(limit=500)
            now = datetime.now(timezone.utc)
            agent_counts: dict[str, int] = {}
            type_counts: dict[str, int] = {}
            stale_count = 0
            total_messages = 0

            for sess in sessions:
                agent = sess.get("agent_id") or "unknown"
                stype = sess.get("session_type") or "interactive"
                agent_counts[agent] = agent_counts.get(agent, 0) + 1
                type_counts[stype] = type_counts.get(stype, 0) + 1
                total_messages += sess.get("message_count", 0)

                ts_str = (
                    sess.get("last_message_at")
                    or sess.get("updated_at")
                    or ""
                )
                if ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if (now - ts).total_seconds() > self._stale_threshold_minutes * 60:
                            stale_count += 1
                    except (ValueError, TypeError):
                        stale_count += 1
                else:
                    stale_count += 1

            return SkillResult.ok({
                "total_sessions": len(sessions),
                "stale_sessions": stale_count,
                "active_sessions": len(sessions) - stale_count,
                "total_messages": total_messages,
                "by_agent": agent_counts,
                "by_type": type_counts,
                "stale_threshold_minutes": self._stale_threshold_minutes,
            })
        except Exception as e:
            return SkillResult.fail(f"Error getting session stats: {e}")

    @logged_method()
    async def cleanup_after_delegation(self, session_id: str = "", **kwargs) -> SkillResult:
        """Clean up a session after a sub-agent delegation completes."""
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail(
                "session_id is required — pass the ID of the completed delegation session"
            )
        return await self.delete_session(session_id=session_id)

    @logged_method()
    async def cleanup_orphans(self, dry_run: bool = False, **kwargs) -> SkillResult:
        """
        Clean up ghost sessions (0 messages, stale) from the database.

        Args:
            dry_run: If true, report what would be cleaned without doing it.
        """
        dry_run = kwargs.get("dry_run", dry_run)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("true", "1", "yes")

        try:
            if dry_run:
                sessions = await self._fetch_sessions(limit=500)
                ghosts = [s for s in sessions if s.get("message_count", 0) == 0]
                return SkillResult.ok({
                    "dry_run": True,
                    "ghost_count": len(ghosts),
                    "ghosts": [
                        {
                            "id": s.get("session_id") or s.get("id", ""),
                            "agent_id": s.get("agent_id", ""),
                            "session_type": s.get("session_type", ""),
                            "created_at": s.get("created_at", ""),
                        }
                        for s in ghosts
                    ],
                })
            else:
                result = await self._api.delete(
                    "/engine/sessions/ghosts?older_than_minutes=15",
                )
                if result.success:
                    return SkillResult.ok({
                        "dry_run": False,
                        "deleted": result.data.get("deleted", 0) if isinstance(result.data, dict) else 0,
                        "message": "Ghost sessions purged",
                    })
                else:
                    return SkillResult.fail(f"Ghost cleanup failed: {result.error}")
        except Exception as e:
            return SkillResult.fail(f"Error cleaning up orphans: {e}")

    async def close(self):
        self._api = None
