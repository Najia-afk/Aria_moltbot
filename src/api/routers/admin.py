"""
Admin endpoints — service control + soul file access.
"""

import asyncio
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from config import ARIA_ADMIN_TOKEN, SERVICE_CONTROL_ENABLED

router = APIRouter(tags=["Admin"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _service_cmd_env(service_id: str, action: str) -> str:
    normalized_service = service_id.upper().replace("-", "_")
    normalized_action = action.upper().replace("-", "_")
    return f"ARIA_SERVICE_CMD_{normalized_service}_{normalized_action}"


async def _run_docker_command(command: str) -> Optional[dict]:
    tokens = command.strip().split()
    if len(tokens) < 3 or tokens[0] != "docker":
        return None
    action, target = tokens[1], tokens[2]
    if action not in {"restart", "stop", "start"}:
        return None
    socket_path = "/var/run/docker.sock"
    if not os.path.exists(socket_path):
        return {
            "status": "error", "code": 1,
            "stdout": "", "stderr": "docker socket not found",
        }
    endpoint = f"/containers/{target}/{action}"
    transport = httpx.AsyncHTTPTransport(uds=socket_path)
    async with httpx.AsyncClient(transport=transport, base_url="http://docker") as client:
        resp = await client.post(endpoint)
        if resp.status_code in {204, 200}:
            return {"status": "ok", "code": 0, "stdout": "", "stderr": ""}
        return {
            "status": "error", "code": resp.status_code,
            "stdout": "", "stderr": resp.text[:2000],
        }


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/admin/services/{service_id}/{action}")
async def api_service_control(service_id: str, action: str, request: Request):
    if not SERVICE_CONTROL_ENABLED:
        raise HTTPException(status_code=403, detail="Service control disabled")
    if ARIA_ADMIN_TOKEN:
        token = request.headers.get("X-Admin-Token", "")
        if token != ARIA_ADMIN_TOKEN:
            raise HTTPException(status_code=401, detail="Unauthorized")
    if action not in {"restart", "stop", "start"}:
        raise HTTPException(status_code=400, detail="Invalid action")

    env_key = _service_cmd_env(service_id, action)
    command = os.getenv(env_key)
    if not command:
        raise HTTPException(
            status_code=400, detail=f"No command configured for {service_id}:{action}"
        )
    try:
        docker_result = await _run_docker_command(command)
        if docker_result is not None:
            return docker_result
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "code": proc.returncode,
            "stdout": (stdout or b"")[-2000:].decode("utf-8", errors="ignore"),
            "stderr": (stderr or b"")[-2000:].decode("utf-8", errors="ignore"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/soul/{filename}")
async def read_soul_file(filename: str):
    allowed = [
        "SOUL.md", "IDENTITY.md", "USER.md", "AGENTS.md",
        "HEARTBEAT.md", "BOOTSTRAP.md",
    ]
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Soul file not found")
    soul_path = f"/app/memory/soul/{filename}"
    try:
        with open(soul_path, "r", encoding="utf-8") as f:
            return {"filename": filename, "content": f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Soul file not found")
