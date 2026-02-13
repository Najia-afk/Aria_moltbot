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
from sqlalchemy import delete, func, select, text, update
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


def _extract_live_label(session: dict[str, Any]) -> str | None:
    direct_label = session.get("label")
    if isinstance(direct_label, str) and direct_label.strip():
        return direct_label.strip()

    origin = session.get("origin")
    if isinstance(origin, dict):
        origin_label = origin.get("label")
        if isinstance(origin_label, str) and origin_label.strip():
            return origin_label.strip()

    delivery = session.get("deliveryContext")
    if isinstance(delivery, dict):
        to_value = delivery.get("to")
        if isinstance(to_value, str) and to_value.strip():
            return to_value.strip()

    last_to = session.get("lastTo")
    if isinstance(last_to, str) and last_to.strip():
        return last_to.strip()

    return None


def _extract_live_channel(session: dict[str, Any]) -> str | None:
    delivery = session.get("deliveryContext")
    if isinstance(delivery, dict):
        channel = delivery.get("channel")
        if isinstance(channel, str) and channel.strip():
            return channel.strip().lower()

    for key in ("lastChannel", "channel"):
        raw = session.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()

    origin = session.get("origin")
    if isinstance(origin, dict):
        provider = origin.get("provider")
        if isinstance(provider, str) and provider.strip():
            return provider.strip().lower()

    source_key = str(session.get("source_key") or "")
    if source_key and ":" in source_key and not source_key.startswith("agent:"):
        prefix = source_key.split(":", 1)[0].strip().lower()
        if prefix and prefix != "agent":
            return prefix

    return None


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

    source_key = str(session.get("source_key") or "").strip()
    identity_seed = f"openclaw:{openclaw_sid}"
    if source_key:
        identity_seed = f"openclaw_key:{source_key}"
    stable_id = uuid.uuid5(_OPENCLAW_UUID_NAMESPACE, identity_seed)
    compact_session = {
        "id": openclaw_sid,
        "agentId": session.get("agentId") or session.get("agent_id") or session.get("agent"),
        "status": _extract_live_status(session),
        "type": session.get("type") or session.get("session_type"),
        "createdAt": session.get("createdAt") or session.get("created_at") or session.get("startedAt") or session.get("started_at"),
        "updatedAt": session.get("updatedAt") or session.get("updated_at"),
        "endedAt": session.get("endedAt") or session.get("ended_at"),
        "label": _extract_live_label(session),
        "channel": _extract_live_channel(session),
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
            "openclaw_source_key": source_key or None,
            "openclaw_source_channel": _extract_live_channel(session),
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

        label_raw = _extract_live_label(value)
        source_channel = _extract_live_channel(value)
        label = str(label_raw or "").strip().lower()

        origin_provider = ""
        origin = value.get("origin")
        if isinstance(origin, dict):
            provider = origin.get("provider")
            if isinstance(provider, str):
                origin_provider = provider.strip().lower()

        delivery_to = ""
        delivery = value.get("deliveryContext")
        if isinstance(delivery, dict):
            to_value = delivery.get("to")
            if isinstance(to_value, str):
                delivery_to = to_value.strip().lower()

        session_type = "openclaw"
        if ":cron:" in key_str:
            session_type = "openclaw_cron"
        elif ":subagent:" in key_str:
            session_type = "openclaw_subagent"
        elif ":run:" in key_str:
            session_type = "openclaw_run"
        elif key_str.endswith(":main"):
            session_type = "openclaw_main"
        if label == "heartbeat" or origin_provider == "heartbeat" or delivery_to == "heartbeat":
            session_type = "openclaw_heartbeat"

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
                "label": label_raw,
                "channel": source_channel,
                "model": value.get("model"),
                "contextTokens": value.get("contextTokens"),
                "source_key": key_str,
            }
        )

    # Deduplicate by sessionId: same OpenClaw session can appear under multiple keys
    # (e.g. agent:* and channel-prefixed keys). Keep the richest row.
    def _row_score(row: dict[str, Any]) -> tuple[int, int, int, int]:
        session_type = str(row.get("session_type") or "")
        type_score = {
            "openclaw_subagent": 40,
            "openclaw_heartbeat": 35,
            "openclaw_cron": 30,
            "openclaw_main": 20,
            "openclaw": 10,
            "openclaw_run": 5,
        }.get(session_type, 0)
        channel_score = 10 if str(row.get("channel") or "").strip() else 0
        label_score = 5 if str(row.get("label") or "").strip() else 0
        updated_score = 1 if str(row.get("updatedAt") or "").strip() else 0
        return (type_score, channel_score, label_score, updated_score)

    best_by_sid: dict[str, dict[str, Any]] = {}
    for row in sessions:
        sid = str(row.get("sessionId") or row.get("id") or "").strip()
        if not sid:
            continue
        current = best_by_sid.get(sid)
        if current is None or _row_score(row) > _row_score(current):
            best_by_sid[sid] = row

    return list(best_by_sid.values())


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

        metadata = normalized.get("metadata_json") or {}
        openclaw_sid = str(metadata.get("openclaw_session_id") or "").strip()
        source_key = str(metadata.get("openclaw_source_key") or "").strip()

        # Legacy compatibility cleanup:
        # older sync used id = uuid5("openclaw:<session_id>") which can collide across keys
        # (e.g., agent:*:main, heartbeat/main variants). If we now have source_key-based id,
        # remove the old legacy row for the same OpenClaw session id.
        if openclaw_sid and source_key:
            legacy_id = uuid.uuid5(_OPENCLAW_UUID_NAMESPACE, f"openclaw:{openclaw_sid}")
            if legacy_id != normalized["id"]:
                await db.execute(
                    delete(AgentSession).where(AgentSession.id == legacy_id)
                )

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
    source_channel: Optional[str] = None,
    sync_live: bool = False,
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    db: AsyncSession = Depends(get_db),
):
    await _maybe_autosync_sessions(db, force=sync_live)

    base = select(AgentSession).order_by(AgentSession.started_at.desc())
    if not include_runtime_events:
        base = base.where(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        base = base.where(AgentSession.session_type != "openclaw_cron")
    if status:
        base = base.where(AgentSession.status == status)
    if agent_id:
        base = base.where(AgentSession.agent_id == agent_id)
    if source_channel:
        base = base.where(
            AgentSession.metadata_json["openclaw_source_channel"].astext == source_channel
        )

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
            "source_channel": (s.metadata_json or {}).get("openclaw_source_channel")
            or ((s.metadata_json or {}).get("openclaw_session") or {}).get("channel"),
            "metadata": s.metadata_json or {},
        }
        for s in rows
    ]
    return build_paginated_response(items, total, page, limit)


@router.get("/sessions/hourly")
async def get_sessions_hourly(
    hours: int = 24,
    sync_live: bool = False,
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    source_channel: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Hourly session counts grouped by agent for time-series charts."""
    await _maybe_autosync_sessions(db, force=sync_live)

    bounded_hours = max(1, min(int(hours), 168))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=bounded_hours)
    hour_bucket = func.date_trunc("hour", AgentSession.started_at).label("hour")

    hourly_stmt = (
        select(
            hour_bucket,
            AgentSession.agent_id,
            func.count(AgentSession.id).label("count"),
        )
        .where(AgentSession.started_at.is_not(None))
        .where(AgentSession.started_at >= cutoff)
    )
    if not include_runtime_events:
        hourly_stmt = hourly_stmt.where(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        hourly_stmt = hourly_stmt.where(AgentSession.session_type != "openclaw_cron")
    if source_channel:
        hourly_stmt = hourly_stmt.where(
            AgentSession.metadata_json["openclaw_source_channel"].astext == source_channel
        )
    if status:
        hourly_stmt = hourly_stmt.where(AgentSession.status == status)
    if agent_id:
        hourly_stmt = hourly_stmt.where(AgentSession.agent_id == agent_id)

    result = await db.execute(
        hourly_stmt
        .group_by(hour_bucket, AgentSession.agent_id)
        .order_by(hour_bucket.asc(), AgentSession.agent_id.asc())
    )

    items = [
        {
            "hour": row.hour.isoformat() if row.hour else None,
            "agent_id": row.agent_id,
            "count": int(row.count or 0),
        }
        for row in result.all()
        if row.hour is not None
    ]

    return {
        "hours": bounded_hours,
        "timezone": "UTC",
        "items": items,
    }


@router.post("/sessions")
async def create_agent_session(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    status = str(data.get("status") or "active").strip().lower()
    allowed_status = {"active", "completed", "ended", "error"}
    if status not in allowed_status:
        status = "active"

    started_at = _parse_iso_dt(data.get("started_at"))
    ended_at = _parse_iso_dt(data.get("ended_at"))
    if status in {"completed", "ended", "error"} and ended_at is None:
        ended_at = datetime.now(timezone.utc)

    payload = {
        "id": uuid.uuid4(),
        "agent_id": data.get("agent_id", "main"),
        "session_type": data.get("session_type", "interactive"),
        "messages_count": int(data.get("messages_count") or 0),
        "tokens_used": int(data.get("tokens_used") or 0),
        "cost_usd": float(data.get("cost_usd") or 0),
        "status": status,
        "metadata_json": data.get("metadata", {}),
    }
    if started_at is not None:
        payload["started_at"] = started_at
    if ended_at is not None:
        payload["ended_at"] = ended_at

    session = AgentSession(**payload)
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
    include_runtime_events: bool = False,
    include_cron_events: bool = False,
    source_channel: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    litellm_db: AsyncSession = Depends(get_litellm_db),
):
    """Session statistics aligned with model-usage DB sources."""
    await _maybe_autosync_sessions(db, force=sync_live)

    session_filters = []
    if not include_runtime_events:
        session_filters.append(AgentSession.session_type != "skill_exec")
    if not include_cron_events:
        session_filters.append(AgentSession.session_type != "openclaw_cron")
    if source_channel:
        session_filters.append(
            AgentSession.metadata_json["openclaw_source_channel"].astext == source_channel
        )
    if status:
        session_filters.append(AgentSession.status == status)
    if agent_id:
        session_filters.append(AgentSession.agent_id == agent_id)

    total_stmt = select(func.count(AgentSession.id))
    if session_filters:
        total_stmt = total_stmt.where(*session_filters)
    total = (await db.execute(total_stmt)).scalar() or 0

    active_stmt = select(func.count(AgentSession.id)).where(AgentSession.status == "active")
    if session_filters:
        active_stmt = active_stmt.where(*session_filters)
    active = (
        await db.execute(active_stmt)
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

    by_agent_stmt = select(
        AgentSession.agent_id,
        func.count(AgentSession.id).label("sessions"),
    )
    if session_filters:
        by_agent_stmt = by_agent_stmt.where(*session_filters)
    by_agent_stmt = by_agent_stmt.group_by(AgentSession.agent_id).order_by(func.count(AgentSession.id).desc())
    by_agent_sessions_result = await db.execute(by_agent_stmt)
    by_agent_map: dict[str, dict[str, Any]] = {
        str(r[0]): {"agent_id": str(r[0]), "sessions": int(r[1] or 0), "tokens": 0, "cost": 0.0}
        for r in by_agent_sessions_result.all()
    }

    # Skill-side usage by linked session_id
    usage_stmt = (
        select(
            AgentSession.agent_id,
            func.coalesce(func.sum(ModelUsage.input_tokens + ModelUsage.output_tokens), 0).label("tokens"),
            func.coalesce(func.sum(ModelUsage.cost_usd), 0).label("cost"),
        )
        .select_from(ModelUsage)
        .join(AgentSession, AgentSession.id == ModelUsage.session_id)
    )
    if session_filters:
        usage_stmt = usage_stmt.where(*session_filters)
    usage_stmt = usage_stmt.group_by(AgentSession.agent_id)
    by_agent_skill_usage = await db.execute(usage_stmt)
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

    by_status_stmt = select(
        AgentSession.status,
        func.count(AgentSession.id).label("count"),
    )
    if session_filters:
        by_status_stmt = by_status_stmt.where(*session_filters)
    by_status_result = await db.execute(by_status_stmt.group_by(AgentSession.status))
    by_status = [{"status": r[0], "count": r[1]} for r in by_status_result.all()]

    by_type_stmt = select(
        AgentSession.session_type,
        func.count(AgentSession.id).label("count"),
    )
    if session_filters:
        by_type_stmt = by_type_stmt.where(*session_filters)
    by_type_result = await db.execute(by_type_stmt.group_by(AgentSession.session_type))
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
