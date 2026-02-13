# aria_skills/session_manager/__init__.py
"""
Session management skill.

List, prune, and delete OpenClaw agent sessions to prevent stale session bloat.
Aria should invoke this after standalone sub-agent delegations and during cleanup cycles.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


def _parse_sessions_from_api(raw: str) -> List[Dict[str, Any]]:
    """
    Parse session data from OpenClaw CLI or API output.
    Tries JSON first, falls back to line-by-line parsing.
    """
    raw = raw.strip()
    if not raw:
        return []

    # Try JSON array
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "sessions" in data:
            return data["sessions"]
        return [data]
    except json.JSONDecodeError:
        pass

    # Fallback: line-by-line parse (tab/space delimited)
    sessions = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(("-", "=", "ID", "id")):
            continue
        parts = line.split()
        if len(parts) >= 2:
            sessions.append({
                "id": parts[0],
                "name": parts[1] if len(parts) > 1 else "unknown",
                "raw": line,
            })
    return sessions


@SkillRegistry.register
class SessionManagerSkill(BaseSkill):
    """
    Manage OpenClaw sessions — list, prune stale ones, delete by ID.

    Prevents session bloat from accumulating cron-spawned and
    sub-agent sessions that are no longer needed.
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._stale_threshold_minutes: int = int(
            config.config.get("stale_threshold_minutes", 60)
        )
        self._gateway_url = config.config.get(
            "openclaw_gateway_url",
            os.environ.get("CLAWDBOT_URL", f"http://localhost:{os.environ.get('OPENCLAW_GATEWAY_PORT', '18789')}")
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    @property
    def name(self) -> str:
        return "session_manager"

    async def initialize(self) -> bool:
        """Initialize session manager."""
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Session manager initialized")
        return True

    async def health_check(self) -> SkillStatus:
        """Check own health."""
        return self._status

    # ── Public tool functions ──────────────────────────────────────────

    @logged_method()
    async def list_sessions(self, **kwargs) -> SkillResult:
        """List all active sessions with basic metadata."""
        try:
            resp = await self._client.get(
                f"{self._gateway_url}/api/sessions",
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            sessions = _parse_sessions_from_api(resp.text)
            return SkillResult.ok({
                "session_count": len(sessions),
                "sessions": sessions,
            })
        except httpx.TimeoutException:
            return SkillResult.fail("Timeout listing sessions")
        except Exception as e:
            return SkillResult.fail(f"Error listing sessions: {e}")

    async def delete_session(self, session_id: str = "", **kwargs) -> SkillResult:
        """Delete a specific session by ID."""
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail("session_id is required")
        try:
            resp = await self._client.delete(
                f"{self._gateway_url}/api/sessions/{session_id}",
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return SkillResult.ok({
                "deleted": session_id,
                "message": f"Session {session_id} deleted successfully",
            })
        except httpx.TimeoutException:
            return SkillResult.fail(f"Timeout deleting session {session_id}")
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
            max_age_minutes: Delete sessions older than this (default: stale_threshold_minutes config).
            dry_run: If true, list what would be deleted without actually deleting.
        """
        if not max_age_minutes:
            max_age_minutes = kwargs.get(
                "max_age_minutes", self._stale_threshold_minutes
            )
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
        kept = []
        for sess in sessions:
            # Try to parse created_at / updatedAt from session data
            ts_str = (
                sess.get("updatedAt")
                or sess.get("updated_at")
                or sess.get("createdAt")
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
            # If no timestamp, mark as candidate for deletion (stale)
            to_delete.append(sess)

        deleted_ids = []
        errors = []
        if not dry_run:
            for sess in to_delete:
                sid = sess.get("id", sess.get("session_id", ""))
                if sid:
                    del_result = await self.delete_session(session_id=sid)
                    if del_result.success:
                        deleted_ids.append(sid)
                    else:
                        errors.append({"id": sid, "error": del_result.error})

        return SkillResult.ok({
            "total_sessions": len(sessions),
            "pruned_count": len(to_delete),
            "kept_count": len(kept),
            "dry_run": dry_run,
            "deleted_ids": deleted_ids if not dry_run else [s.get("id", "") for s in to_delete],
            "errors": errors,
            "threshold_minutes": max_age_minutes,
        })

    async def get_session_stats(self, **kwargs) -> SkillResult:
        """
        Get summary statistics about current sessions.

        Returns counts by agent, total sessions, and staleness info.
        """
        list_result = await self.list_sessions()
        if not list_result.success:
            return list_result

        sessions = list_result.data.get("sessions", [])
        now = datetime.now(timezone.utc)
        agent_counts: Dict[str, int] = {}
        stale_count = 0

        for sess in sessions:
            agent = (
                sess.get("agentId")
                or sess.get("agent_id")
                or sess.get("agent")
                or "unknown"
            )
            agent_counts[agent] = agent_counts.get(agent, 0) + 1

            ts_str = (
                sess.get("updatedAt")
                or sess.get("updated_at")
                or sess.get("createdAt")
                or sess.get("created_at")
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
            "by_agent": agent_counts,
            "stale_threshold_minutes": self._stale_threshold_minutes,
        })

    async def cleanup_after_delegation(self, session_id: str = "", **kwargs) -> SkillResult:
        """
        Clean up a session after a standalone sub-agent delegation completes.

        Call this after receiving results from a delegated sub-agent task
        to prevent stale session accumulation.

        Args:
            session_id: The session ID of the completed delegation.
        """
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail(
                "session_id is required — pass the ID of the completed delegation session"
            )

        return await self.delete_session(session_id=session_id)

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
