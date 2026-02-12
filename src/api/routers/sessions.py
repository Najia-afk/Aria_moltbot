"""
Agent sessions endpoints — CRUD + stats with LiteLLM enrichment.
"""

import json as json_lib
import asyncio
import glob
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    OPENCLAW_SESSIONS_INDEX_PATH,
    OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS,
    OPENCLAW_AGENTS_ROOT,
    SERVICE_URLS,
)
from db.models import AgentSession, ModelUsage
from deps import get_db, get_litellm_db
from pagination import paginate_query, build_paginated_response

router = APIRouter(tags=["Sessions"])

_OPENCLAW_UUID_NAMESPACE = uuid.UUID("0e6fb78b-7809-4b90-a5e4-16f39f307220")
_OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL: datetime | None = None
_LAST_OPENCLAW_SYNC_AT: datetime | None = None
_OPENCLAW_SYNC_LOCK = asyncio.Lock()


def _parse_iso_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _parse_epoch_ms_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None


def _extract_live_session_id(session: dict[str, Any]) -> str | None:
    for key in ("id", "session_id", "sessionId"):
        raw = session.get(key)
        if raw is not None:
            sid = str(raw).strip()
            if sid:
                return sid
    return None


def _extract_live_agent_id(session: dict[str, Any]) -> str:
    for key in ("agentId", "agent_id", "agent", "name"):
        raw = session.get(key)
        if raw:
            return str(raw)
    return "main"


def _extract_live_status(session: dict[str, Any]) -> str:
    status = str(session.get("status", "") or "").strip().lower()
    if status in {"active", "completed", "ended", "error"}:
        return status
    if session.get("endedAt") or session.get("ended_at"):
        return "completed"
    return "active"


def _normalize_live_session(
    session: dict[str, Any],
    source: str = "openclaw_live",
) -> dict[str, Any] | None:
    openclaw_sid = _extract_live_session_id(session)
    if not openclaw_sid:
        return None

    started_at = _parse_iso_dt(
        session.get("createdAt") or session.get("created_at") or session.get("startedAt") or session.get("started_at")
    )
    ended_at = _parse_iso_dt(session.get("endedAt") or session.get("ended_at"))

    stable_id = uuid.uuid5(_OPENCLAW_UUID_NAMESPACE, f"openclaw:{openclaw_sid}")
    compact_session = {
        "id": openclaw_sid,
        "agentId": session.get("agentId") or session.get("agent_id") or session.get("agent"),
        "status": _extract_live_status(session),
        "type": session.get("type") or session.get("session_type"),
        "createdAt": session.get("createdAt") or session.get("created_at") or session.get("startedAt") or session.get("started_at"),
        "updatedAt": session.get("updatedAt") or session.get("updated_at"),
        "endedAt": session.get("endedAt") or session.get("ended_at"),
        "label": session.get("label"),
        "model": session.get("model"),
        "contextTokens": session.get("contextTokens"),
    }

    return {
        "id": stable_id,
        "agent_id": _extract_live_agent_id(session),
        "session_type": str(session.get("type") or session.get("session_type") or "openclaw_live"),
        "started_at": started_at,
        "ended_at": ended_at,
        "status": _extract_live_status(session),
        "metadata_json": {
            "source": source,
            "openclaw_session_id": openclaw_sid,
            "openclaw_session": compact_session,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        },
    }


def _extract_session_id_from_index_key(index_key: str) -> str | None:
    if not index_key:
        return None
    parts = [p for p in index_key.split(":") if p]
    if not parts:
        return None
    for part in reversed(parts):
        if "-" in part and len(part) >= 8:
            return part
    return parts[-1]


def _parse_sessions_index_payload(payload: Any, agent_hint: str = "main") -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    sessions: list[dict[str, Any]] = []
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue

        sid = value.get("sessionId") or _extract_session_id_from_index_key(str(key))
        if not sid:
            continue

        key_str = str(key)
        agent_id = agent_hint or "main"
        parts = key_str.split(":")
        if len(parts) >= 2 and parts[0] == "agent":
            agent_id = parts[1]

        session_type = "openclaw"
        if ":cron:" in key_str:
            session_type = "openclaw_cron"
        elif ":run:" in key_str:
            session_type = "openclaw_run"
        elif key_str.endswith(":main"):
            session_type = "openclaw_main"

        updated_at_dt = _parse_epoch_ms_dt(value.get("updatedAt"))
        updated_iso = updated_at_dt.isoformat() if updated_at_dt else None

        sessions.append(
            {
                "id": str(sid),
                "sessionId": str(sid),
                "agentId": agent_id,
                "session_type": session_type,
                "status": "active",
                "updatedAt": updated_iso,
                "createdAt": updated_iso,
                "label": value.get("label"),
                "model": value.get("model"),
                "contextTokens": value.get("contextTokens"),
                "source_key": key_str,
            }
        )

    return sessions


def _fetch_volume_openclaw_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    # Backward-compatible explicit path
    explicit_path = OPENCLAW_SESSIONS_INDEX_PATH
    if explicit_path and os.path.exists(explicit_path):
        seen_paths.add(explicit_path)
        try:
            with open(explicit_path, "r", encoding="utf-8") as f:
                payload = json_lib.load(f)
            sessions.extend(_parse_sessions_index_payload(payload, agent_hint="main"))
        except Exception:
            pass

    # Preferred: all agents mounted under /openclaw/agents/*/sessions/sessions.json
    pattern = os.path.join(OPENCLAW_AGENTS_ROOT, "*", "sessions", "sessions.json")
    for path in glob.glob(pattern):
        if path in seen_paths:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json_lib.load(f)
        except Exception:
            continue

        agent_hint = os.path.basename(os.path.dirname(os.path.dirname(path)))
        sessions.extend(_parse_sessions_index_payload(payload, agent_hint=agent_hint))

    return sessions


def _map_openclaw_file_session_agents() -> dict[str, str]:
    """Map OpenClaw session UUID (jsonl filename) → agent_id."""
    mapping: dict[str, str] = {}
    pattern = os.path.join(OPENCLAW_AGENTS_ROOT, "*", "sessions", "*.jsonl")
    for path in glob.glob(pattern):
        base = os.path.basename(path)
        if not base.endswith(".jsonl"):
            continue
        session_id = base[:-6]
        if not session_id:
            continue
        agent_id = os.path.basename(os.path.dirname(os.path.dirname(path)))
        mapping[session_id] = agent_id
    return mapping


def _parse_live_sessions_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        sessions = payload.get("sessions")
        if isinstance(sessions, list):
            return [item for item in sessions if isinstance(item, dict)]
    return []


async def _fetch_live_openclaw_sessions() -> list[dict[str, Any]]:
    global _OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL

    now = datetime.now(timezone.utc)
    if _OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL and now < _OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL:
        return []

    base_url = SERVICE_URLS.get("clawdbot", ("http://clawdbot:18789",))[0].rstrip("/")
    token = os.getenv("CLAWDBOT_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=8.0) as client:
        try:
            resp = await client.get(f"{base_url}/api/sessions", headers=headers)
        except Exception:
            return []

        if resp.status_code == 404:
            _OPENCLAW_SESSIONS_UNAVAILABLE_UNTIL = now + timedelta(minutes=10)
            return []

        if resp.status_code >= 400:
            return []

        try:
            payload = resp.json()
            return _parse_live_sessions_payload(payload)
        except ValueError:
            text = (resp.text or "").strip()
            if not text:
                return []
            try:
                payload = json_lib.loads(text)
                return _parse_live_sessions_payload(payload)
            except ValueError:
                return []


async def _sync_live_sessions_to_db(db: AsyncSession) -> dict[str, int]:
    try:
        live_sessions = await _fetch_live_openclaw_sessions()
    except Exception:
        live_sessions = []

    if live_sessions:
        result = await _sync_payload_sessions_to_db(
            db,
            live_sessions,
            source="openclaw_live",
        )
        result["source"] = "openclaw_live"
        return result

    volume_sessions = _fetch_volume_openclaw_sessions()
    result = await _sync_payload_sessions_to_db(
        db,
        volume_sessions,
        source="openclaw_volume",
    )
    result["source"] = "openclaw_volume"
    return result


async def _maybe_autosync_sessions(db: AsyncSession, force: bool = False) -> dict[str, Any]:
    global _LAST_OPENCLAW_SYNC_AT

    now = datetime.now(timezone.utc)
    min_interval = max(1, int(OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS))
    if not force and _LAST_OPENCLAW_SYNC_AT:
        age = (now - _LAST_OPENCLAW_SYNC_AT).total_seconds()
        if age < min_interval:
            return {
                "performed": False,
                "source": "cached",
                "age_seconds": round(age, 2),
                "interval_seconds": min_interval,
            }

    async with _OPENCLAW_SYNC_LOCK:
        now = datetime.now(timezone.utc)
        if not force and _LAST_OPENCLAW_SYNC_AT:
            age = (now - _LAST_OPENCLAW_SYNC_AT).total_seconds()
            if age < min_interval:
                return {
                    "performed": False,
                    "source": "cached",
                    "age_seconds": round(age, 2),
                    "interval_seconds": min_interval,
                }

        result = await _sync_live_sessions_to_db(db)
        _LAST_OPENCLAW_SYNC_AT = now
        result["performed"] = True
        result["interval_seconds"] = min_interval
        return result


async def _sync_payload_sessions_to_db(
    db: AsyncSession,
    payload_sessions: list[dict[str, Any]],
    source: str = "openclaw_live",
) -> dict[str, int]:
    if not payload_sessions:
        return {"fetched": 0, "synced": 0}

    synced = 0
    for raw in payload_sessions:
        normalized = _normalize_live_session(raw, source=source)
        if not normalized:
            continue

        stmt = pg_insert(AgentSession).values(**normalized).on_conflict_do_update(
            index_elements=["id"],
            set_={
                "agent_id": normalized["agent_id"],
                "session_type": normalized["session_type"],
                "started_at": normalized["started_at"] or AgentSession.started_at,
                "ended_at": normalized["ended_at"],
                "status": normalized["status"],
                "metadata": normalized["metadata_json"],
            },
        )
        await db.execute(stmt)
        synced += 1

    if synced:
        await db.commit()
    return {"fetched": len(payload_sessions), "synced": synced}


@router.get("/sessions/live")
async def get_live_openclaw_sessions():
    """Fetch OpenClaw sessions (gateway first, then volume index fallback)."""
    try:
        sessions = await _fetch_live_openclaw_sessions()
        source = "openclaw_live"
        if not sessions:
            sessions = _fetch_volume_openclaw_sessions()
            source = "openclaw_volume"
        return {"sessions": sessions, "count": len(sessions), "source": source}
    except Exception as exc:
        return {"sessions": [], "count": 0, "source": "openclaw_live", "error": str(exc)}


@router.post("/sessions/sync-live")
async def sync_live_openclaw_sessions(db: AsyncSession = Depends(get_db)):
    """Ingest OpenClaw sessions into agent_sessions table (gateway or volume fallback)."""
    result = await _maybe_autosync_sessions(db, force=True)
    return result


@router.post("/sessions/import-openclaw")
async def import_openclaw_sessions(request: Request, db: AsyncSession = Depends(get_db)):
    """Import OpenClaw sessions payload into agent_sessions table."""
    data = await request.json()
    payload_sessions = _parse_live_sessions_payload(data)
    result = await _sync_payload_sessions_to_db(
        db,
        payload_sessions,
        source="import_openclaw",
    )
    result["source"] = "import_openclaw"
    return result


@router.get("/sessions")
async def get_agent_sessions(
    page: int = 1,
    limit: int = 25,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    sync_live: bool = False,
    db: AsyncSession = Depends(get_db),
):
    await _maybe_autosync_sessions(db, force=sync_live)

    base = select(AgentSession).order_by(AgentSession.started_at.desc())
    if status:
        base = base.where(AgentSession.status == status)
    if agent_id:
        base = base.where(AgentSession.agent_id == agent_id)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt, _ = paginate_query(base, page, limit)
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": str(s.id),
            "agent_id": s.agent_id,
            "session_type": s.session_type,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "messages_count": s.messages_count,
            "tokens_used": s.tokens_used,
            "cost_usd": float(s.cost_usd) if s.cost_usd else 0,
            "status": s.status,
            "metadata": s.metadata_json or {},
        }
        for s in rows
    ]
    return build_paginated_response(items, total, page, limit)


@router.post("/sessions")
async def create_agent_session(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    session = AgentSession(
        id=uuid.uuid4(),
        agent_id=data.get("agent_id", "main"),
        session_type=data.get("session_type", "interactive"),
        status="active",
        metadata_json=data.get("metadata", {}),
    )
    db.add(session)
    await db.commit()
    return {"id": str(session.id), "created": True}


@router.patch("/sessions/{session_id}")
async def update_agent_session(
    session_id: str, request: Request, db: AsyncSession = Depends(get_db)
):
    data = await request.json()
    values: dict = {}
    if data.get("status"):
        values["status"] = data["status"]
        if data["status"] in ("completed", "ended", "error"):
            from sqlalchemy import text
            values["ended_at"] = text("NOW()")
    if data.get("messages_count") is not None:
        values["messages_count"] = data["messages_count"]
    if data.get("tokens_used") is not None:
        values["tokens_used"] = data["tokens_used"]
    if data.get("cost_usd") is not None:
        values["cost_usd"] = data["cost_usd"]
    if values:
        await db.execute(
            update(AgentSession).where(AgentSession.id == uuid.UUID(session_id)).values(**values)
        )
        await db.commit()
    return {"updated": True}


@router.get("/sessions/stats")
async def get_session_stats(
    sync_live: bool = False,
    db: AsyncSession = Depends(get_db),
    litellm_db: AsyncSession = Depends(get_litellm_db),
):
    """Session statistics aligned with model-usage DB sources."""
    await _maybe_autosync_sessions(db, force=sync_live)

    total = (await db.execute(select(func.count(AgentSession.id)))).scalar() or 0
    active = (
        await db.execute(
            select(func.count(AgentSession.id)).where(AgentSession.status == "active")
        )
    ).scalar() or 0
    skill_tokens = (
        await db.execute(
            select(func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0))
        )
    ).scalar() or 0
    skill_cost = (
        await db.execute(select(func.coalesce(func.sum(ModelUsage.cost_usd), 0)))
    ).scalar() or 0

    llm_totals = {"tokens": 0, "cost": 0.0, "rows": 0}
    try:
        llm_result = await litellm_db.execute(
            text(
                'SELECT COUNT(*) AS rows, '
                'COALESCE(SUM(total_tokens), 0) AS tokens, '
                'COALESCE(SUM(spend), 0) AS cost '
                'FROM "LiteLLM_SpendLogs"'
            )
        )
        row = llm_result.mappings().one()
        llm_totals = {
            "rows": int(row.get("rows") or 0),
            "tokens": int(row.get("tokens") or 0),
            "cost": float(row.get("cost") or 0),
        }
    except Exception:
        pass

    total_tokens = int(skill_tokens) + int(llm_totals["tokens"])
    total_cost = float(skill_cost) + float(llm_totals["cost"])

    by_agent_sessions_result = await db.execute(
        select(
            AgentSession.agent_id,
            func.count(AgentSession.id).label("sessions"),
        )
        .group_by(AgentSession.agent_id)
        .order_by(func.count(AgentSession.id).desc())
    )
    by_agent_map: dict[str, dict[str, Any]] = {
        str(r[0]): {"agent_id": str(r[0]), "sessions": int(r[1] or 0), "tokens": 0, "cost": 0.0}
        for r in by_agent_sessions_result.all()
    }

    # Skill-side usage by linked session_id
    by_agent_skill_usage = await db.execute(
        select(
            AgentSession.agent_id,
            func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0).label("tokens"),
            func.coalesce(func.sum(ModelUsage.cost_usd), 0).label("cost"),
        )
        .select_from(ModelUsage)
        .join(AgentSession, AgentSession.id == ModelUsage.session_id)
        .group_by(AgentSession.agent_id)
    )
    for r in by_agent_skill_usage.all():
        agent = str(r[0] or "unknown")
        if agent == "unknown":
            continue
        if agent not in by_agent_map:
            by_agent_map[agent] = {"agent_id": agent, "sessions": 0, "tokens": 0, "cost": 0.0}
        by_agent_map[agent]["tokens"] += int(r[1] or 0)
        by_agent_map[agent]["cost"] += float(r[2] or 0)

    # Build two maps so LiteLLM session_id can resolve to agent:
    # 1) direct session UUID, 2) raw openclaw session UUID in metadata
    agent_sessions_for_map = (
        await db.execute(
            select(AgentSession.id, AgentSession.agent_id, AgentSession.metadata_json)
        )
    ).all()
    agent_by_session_id: dict[str, str] = {}
    for sid, aid, meta in agent_sessions_for_map:
        if sid:
            agent_by_session_id[str(sid)] = str(aid or "unknown")
        if isinstance(meta, dict):
            raw_sid = meta.get("openclaw_session_id")
            if raw_sid:
                agent_by_session_id[str(raw_sid)] = str(aid or "unknown")

    # Also map historical OpenClaw session UUIDs by file names on mounted volume.
    for sid, aid in _map_openclaw_file_session_agents().items():
        agent_by_session_id.setdefault(str(sid), str(aid or "unknown"))

    # LiteLLM usage by session_id then map to agent
    llm_by_session = []
    try:
        llm_session_result = await litellm_db.execute(
            text(
                'SELECT session_id, '
                "COALESCE(NULLIF(metadata ->> 'agent_id', ''), "
                "NULLIF(metadata ->> 'agentId', ''), "
                "NULLIF((metadata -> 'mcp_tool_call_metadata' ->> 'agent_id'), ''), "
                "NULLIF((metadata -> 'mcp_tool_call_metadata' ->> 'agentId'), '')) AS agent_hint, "
                'COALESCE(SUM(total_tokens), 0) AS tokens, '
                'COALESCE(SUM(spend), 0) AS cost '
                'FROM "LiteLLM_SpendLogs" '
                "WHERE session_id IS NOT NULL AND session_id <> '' "
                'GROUP BY session_id, agent_hint'
            )
        )
        llm_by_session = llm_session_result.mappings().all()
    except Exception:
        llm_by_session = []

    unmapped_litellm_tokens = 0
    unmapped_litellm_cost = 0.0
    for row in llm_by_session:
        sid = str(row.get("session_id") or "")
        if not sid:
            continue
        agent_hint = str(row.get("agent_hint") or "").strip()
        agent = agent_hint or agent_by_session_id.get(sid, "unknown")
        if agent == "unknown":
            unmapped_litellm_tokens += int(row.get("tokens") or 0)
            unmapped_litellm_cost += float(row.get("cost") or 0)
            continue
        if agent not in by_agent_map:
            by_agent_map[agent] = {"agent_id": agent, "sessions": 0, "tokens": 0, "cost": 0.0}
        by_agent_map[agent]["tokens"] += int(row.get("tokens") or 0)
        by_agent_map[agent]["cost"] += float(row.get("cost") or 0)

    by_agent = sorted(
        (
            {
                "agent_id": item["agent_id"],
                "sessions": int(item["sessions"]),
                "tokens": int(item["tokens"]),
                "cost": float(item["cost"]),
            }
            for item in by_agent_map.values()
        ),
        key=lambda entry: entry["sessions"],
        reverse=True,
    )

    by_status_result = await db.execute(
        select(
            AgentSession.status,
            func.count(AgentSession.id).label("count"),
        ).group_by(AgentSession.status)
    )
    by_status = [{"status": r[0], "count": r[1]} for r in by_status_result.all()]

    by_type_result = await db.execute(
        select(
            AgentSession.session_type,
            func.count(AgentSession.id).label("count"),
        ).group_by(AgentSession.session_type)
    )
    by_type = [{"type": r[0], "count": r[1]} for r in by_type_result.all()]

    return {
        "total_sessions": total,
        "active_sessions": active,
        "total_tokens": total_tokens,
        "total_cost": float(total_cost),
        "by_agent": by_agent,
        "by_status": by_status,
        "by_type": by_type,
        "litellm": {
            "sessions": llm_totals["rows"],
            "tokens": llm_totals["tokens"],
            "cost": llm_totals["cost"],
            "unmapped_tokens": unmapped_litellm_tokens,
            "unmapped_cost": unmapped_litellm_cost,
        },
        "sources": {
            "skills": {
                "tokens": int(skill_tokens),
                "cost": float(skill_cost),
            },
            "litellm": {
                "tokens": int(llm_totals["tokens"]),
                "cost": float(llm_totals["cost"]),
            },
        },
    }
