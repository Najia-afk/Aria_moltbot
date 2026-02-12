"""Best-effort tracking helpers for run_skill."""

from __future__ import annotations

import json
import logging
import os

_API_BASE = os.environ.get("ARIA_API_URL", "http://aria-api:8000/api").rstrip("/")

try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

_tracker_log = logging.getLogger("aria.skill_tracker")


async def _api_post(endpoint: str, payload: dict) -> bool:
    """Fire-and-forget POST to aria-api. Returns True on success."""
    if not _HAS_HTTPX:
        _tracker_log.debug("httpx not installed — skipping tracking POST")
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(f"{_API_BASE}{endpoint}", json=payload)
            resp.raise_for_status()
            return True
    except Exception as exc:
        _tracker_log.debug("Tracking POST %s failed: %s", endpoint, exc)
        return False


def _log_locally(event_type: str, data: dict) -> None:
    """Fallback: log tracking data locally when the API is unreachable."""
    _tracker_log.warning(
        "API unreachable — logging %s locally: %s",
        event_type,
        json.dumps(data, default=str),
    )


async def _log_session(
    skill_name: str,
    function_name: str,
    duration_ms: float,
    success: bool,
    error_msg: str | None = None,
) -> None:
    """P2.1 — Log skill invocation to agent_sessions via aria-api."""
    payload = {
        "agent_id": os.environ.get("OPENCLAW_AGENT_ID", "main"),
        "session_type": "skill_exec",
        "status": "completed" if success else "error",
        "metadata": {
            "skill": skill_name,
            "function": function_name,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error_msg,
        },
    }
    ok = await _api_post("/sessions", payload)
    if not ok:
        _log_locally("session", payload)


async def _log_model_usage(skill_name: str, function_name: str, duration_ms: float) -> None:
    """P2.2 — Log approximate model usage via aria-api."""
    payload = {
        "model": f"skill:{skill_name}:{function_name}",
        "provider": "skill-exec",
        "latency_ms": int(duration_ms),
        "success": True,
    }
    ok = await _api_post("/model-usage", payload)
    if not ok:
        _log_locally("model_usage", payload)
