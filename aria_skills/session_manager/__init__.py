# aria_skills/session_manager/__init__.py
"""
Session management skill.

List, prune, and delete OpenClaw agent sessions.
Two-layer approach:
  1. Filesystem (clawdbot shared volume) — the live source of truth.
     sessions.json index + per-session .jsonl transcripts.
  2. aria-api PostgreSQL — historical record. On delete we mark
     the PG row as "ended" so /sessions on the dashboard keeps history.

Aria invokes this after standalone sub-agent delegations and during
periodic cleanup cycles.
"""
import glob
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

# ── Filesystem defaults (inside clawdbot container) ──────────────────

_AGENTS_DIR = "/root/.openclaw/agents"
# Allow override via env (useful for tests / non-standard mounts)
_env_workspace = os.environ.get("OPENCLAW_WORKSPACE", "")
if _env_workspace:
    _candidate = os.path.join(os.path.dirname(_env_workspace), "agents")
    if os.path.isdir(_candidate):
        _AGENTS_DIR = _candidate


def _load_sessions_index(agent: str = "main") -> Dict[str, Any]:
    """Read sessions.json for a given agent."""
    path = os.path.join(_AGENTS_DIR, agent, "sessions", "sessions.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_sessions_index(data: Dict[str, Any], agent: str = "main") -> None:
    """Write sessions.json atomically for a given agent."""
    path = os.path.join(_AGENTS_DIR, agent, "sessions", "sessions.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def _archive_transcript(session_id: str, agent: str = "main") -> bool:
    """Rename .jsonl → .jsonl.deleted.<timestamp> (matches clawdbot pattern)."""
    base = os.path.join(_AGENTS_DIR, agent, "sessions", f"{session_id}.jsonl")
    if not os.path.exists(base):
        return False
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H-%M-%S.") + f"{now.microsecond // 1000:03d}Z"
    os.rename(base, f"{base}.deleted.{ts}")
    return True


def _list_all_agents() -> List[str]:
    """Discover agent directories that have sessions."""
    if not os.path.isdir(_AGENTS_DIR):
        return ["main"]
    agents = []
    for entry in os.listdir(_AGENTS_DIR):
        sess_dir = os.path.join(_AGENTS_DIR, entry, "sessions")
        if os.path.isdir(sess_dir):
            agents.append(entry)
    return agents or ["main"]


def _epoch_ms_to_iso(ms: Any) -> Optional[str]:
    """Convert epoch-ms timestamp to ISO string."""
    if ms is None:
        return None
    try:
        val = int(ms)
        if val <= 0:
            return None
        return datetime.fromtimestamp(val / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _flatten_sessions(index: Dict[str, Any], agent: str = "main") -> List[Dict[str, Any]]:
    """Convert sessions.json index into a flat deduplicated list."""
    seen: Dict[str, Dict[str, Any]] = {}
    for key, value in index.items():
        if not isinstance(value, dict):
            continue
        sid = value.get("sessionId")
        if not sid:
            continue

        updated_iso = _epoch_ms_to_iso(value.get("updatedAt"))

        session_type = "direct"
        if ":cron:" in key:
            session_type = "cron"
        elif ":subagent:" in key:
            session_type = "subagent"
        elif ":run:" in key:
            session_type = "cron_run"

        label = value.get("label") or ""
        origin = value.get("origin")
        if not label and isinstance(origin, dict):
            label = origin.get("label", "")
        delivery = value.get("deliveryContext")
        if not label and isinstance(delivery, dict):
            label = delivery.get("to", "")

        row = {
            "id": sid,
            "sessionId": sid,
            "key": key,
            "agentId": agent,
            "session_type": session_type,
            "label": label or None,
            "updatedAt": updated_iso,
            "contextTokens": value.get("contextTokens"),
            "model": value.get("model"),
        }

        existing = seen.get(sid)
        if existing is None:
            seen[sid] = row
        elif session_type in ("cron", "subagent") and existing["session_type"] == "direct":
            seen[sid] = row
        elif row.get("label") and not existing.get("label"):
            seen[sid] = row

    return list(seen.values())


@SkillRegistry.register
class SessionManagerSkill(BaseSkill):
    """
    Manage OpenClaw sessions — list, prune stale ones, delete by ID.

    Two-layer delete:
      1. Remove from clawdbot filesystem (live sessions)
      2. Mark as ended in aria-api PG (historical record for /sessions dashboard)
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._stale_threshold_minutes: int = int(
            config.config.get("stale_threshold_minutes", 60)
        )
        self._api_url = (
            config.config.get("api_url")
            or os.environ.get("ARIA_API_URL")
            or "http://aria-api:8000"
        ).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._api_url,
            timeout=httpx.Timeout(30.0),
            headers={"Content-Type": "application/json"},
        )

    @property
    def name(self) -> str:
        return "session_manager"

    async def initialize(self) -> bool:
        """Initialize session manager."""
        self._status = SkillStatus.AVAILABLE
        self.logger.info(
            "Session manager initialized  agents_dir=%s  api=%s",
            _AGENTS_DIR, self._api_url,
        )
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    # ── Public tool functions ──────────────────────────────────────────

    @logged_method()
    async def list_sessions(self, agent: str = "", **kwargs) -> SkillResult:
        """
        List all active sessions from the filesystem (sessions.json).

        Args:
            agent: Agent name (default: all agents).
        """
        agent = agent or kwargs.get("agent", "")
        try:
            agents = [agent] if agent else _list_all_agents()
            sessions: List[Dict[str, Any]] = []
            for ag in agents:
                index = _load_sessions_index(ag)
                sessions.extend(_flatten_sessions(index, ag))
            return SkillResult.ok({
                "session_count": len(sessions),
                "sessions": sessions,
            })
        except Exception as e:
            return SkillResult.fail(f"Error listing sessions: {e}")

    async def delete_session(self, session_id: str = "", agent: str = "", **kwargs) -> SkillResult:
        """
        Delete a session: remove from clawdbot filesystem, mark ended in PG.

        1. Remove all matching keys from sessions.json
        2. Archive the .jsonl transcript (rename to .deleted.<ts>)
        3. PATCH aria-api to set status=ended (keeps history at /sessions)

        Args:
            session_id: The OpenClaw session UUID.
            agent: Agent name (default: searches all agents).
        """
        if not session_id:
            session_id = kwargs.get("session_id", "")
        if not session_id:
            return SkillResult.fail("session_id is required")
        agent = agent or kwargs.get("agent", "")

        agents = [agent] if agent else _list_all_agents()
        removed_keys: List[str] = []
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

            for k in keys_to_remove:
                del index[k]
                removed_keys.append(k)

            _save_sessions_index(index, ag)

            if _archive_transcript(session_id, ag):
                archived = True

        if not removed_keys:
            return SkillResult.fail(
                f"Session {session_id} not found in any agent sessions.json"
            )

        # Best-effort: mark as ended in PG for dashboard history
        pg_updated = await self._mark_ended_in_pg(session_id)

        return SkillResult.ok({
            "deleted": session_id,
            "removed_keys": removed_keys,
            "transcript_archived": archived,
            "pg_status_updated": pg_updated,
            "message": f"Session {session_id} removed from clawdbot"
                       f" ({len(removed_keys)} keys, transcript={'archived' if archived else 'n/a'})"
                       f"{', PG marked ended' if pg_updated else ''}",
        })

    async def _mark_ended_in_pg(self, session_id: str) -> bool:
        """Best-effort PATCH to aria-api to mark session as ended."""
        try:
            resp = await self._client.get(
                "/api/sessions",
                params={"limit": 200, "include_cron_events": "true", "include_runtime_events": "true"},
            )
            if resp.status_code != 200:
                return False
            for item in resp.json().get("items", []):
                meta = item.get("metadata", {})
                if meta.get("openclaw_session_id") == session_id:
                    r = await self._client.patch(
                        f"/api/sessions/{item['id']}",
                        json={"status": "ended"},
                    )
                    return r.status_code == 200
        except Exception:
            pass
        return False

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
            max_age_minutes: Delete sessions older than this (default: config).
            dry_run: If true, list candidates without deleting.
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

        to_delete: List[Dict[str, Any]] = []
        kept: List[Dict[str, Any]] = []
        for sess in sessions:
            ts_str = sess.get("updatedAt") or ""
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

        deleted_ids: List[str] = []
        errors: List[Dict[str, str]] = []
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
            "kept_count": len(kept),
            "dry_run": dry_run,
            "deleted_ids": deleted_ids if not dry_run else [s.get("id", "") for s in to_delete],
            "errors": errors,
            "threshold_minutes": max_age_minutes,
        })

    async def get_session_stats(self, **kwargs) -> SkillResult:
        """Get summary statistics about current sessions."""
        list_result = await self.list_sessions()
        if not list_result.success:
            return list_result

        sessions = list_result.data.get("sessions", [])
        now = datetime.now(timezone.utc)
        agent_counts: Dict[str, int] = {}
        stale_count = 0

        for sess in sessions:
            agent = sess.get("agentId") or "unknown"
            agent_counts[agent] = agent_counts.get(agent, 0) + 1
            ts_str = sess.get("updatedAt") or ""
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
        """Clean up a session after a sub-agent delegation completes."""
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
