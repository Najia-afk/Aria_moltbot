"""
Engine Roundtable API — REST endpoints for multi-agent roundtable discussions.

Endpoints:
  POST   /api/engine/roundtable                — start a new roundtable discussion
  GET    /api/engine/roundtable                — list recent roundtables (paginated)
  GET    /api/engine/roundtable/{session_id}   — get roundtable detail (turns, synthesis)
  GET    /api/engine/roundtable/{session_id}/turns — stream-friendly turn list
  DELETE /api/engine/roundtable/{session_id}   — end/archive a roundtable

Wires aria_engine/roundtable.py (Roundtable class) into the REST layer.
"""
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from starlette.websockets import WebSocketDisconnect, WebSocketState

from aria_engine.roundtable import Roundtable, RoundtableResult

logger = logging.getLogger("aria.api.engine_roundtable")

router = APIRouter(prefix="/engine/roundtable", tags=["Engine Roundtable"])
ws_router = APIRouter(tags=["Engine Roundtable WebSocket"])


# ── Pydantic Models ──────────────────────────────────────────────────────────


class StartRoundtableRequest(BaseModel):
    """Request body for starting a new roundtable discussion."""
    topic: str = Field(..., min_length=2, max_length=2000, description="Discussion topic")
    agent_ids: list[str] = Field(
        ..., min_length=2, max_length=10,
        description="Agent IDs to participate (min 2)"
    )
    rounds: int = Field(default=3, ge=1, le=10, description="Number of rounds")
    synthesizer_id: str = Field(default="main", description="Agent ID for final synthesis")
    agent_timeout: int = Field(default=60, ge=10, le=300, description="Seconds per agent")
    total_timeout: int = Field(default=300, ge=30, le=900, description="Max total seconds")


class RoundtableTurnResponse(BaseModel):
    """A single turn in a roundtable discussion."""
    agent_id: str
    round: int
    content: str
    duration_ms: int


class RoundtableResponse(BaseModel):
    """Full response for a completed roundtable."""
    session_id: str
    topic: str
    participants: list[str]
    rounds: int
    turn_count: int
    synthesis: str
    synthesizer_id: str
    total_duration_ms: int
    created_at: str
    turns: list[RoundtableTurnResponse] = Field(default_factory=list)


class RoundtableSummary(BaseModel):
    """Summary for list endpoints."""
    session_id: str
    title: str | None = None
    participants: list[str] = Field(default_factory=list)
    message_count: int = 0
    created_at: str | None = None


class PaginatedRoundtables(BaseModel):
    """Paginated list of roundtables."""
    items: list[RoundtableSummary]
    total: int
    page: int
    page_size: int


class RoundtableStatusResponse(BaseModel):
    """Status of a running or completed roundtable."""
    session_id: str
    status: str  # "running" | "completed" | "failed"
    topic: str | None = None
    participants: list[str] = Field(default_factory=list)
    turn_count: int = 0
    message: str | None = None


# ── Dependency Injection ─────────────────────────────────────────────────────

_roundtable: Roundtable | None = None
_db_engine: AsyncEngine | None = None

# In-memory tracking of running roundtable tasks
_running: dict[str, dict[str, Any]] = {}
_completed: dict[str, RoundtableResult] = {}


def configure_roundtable(
    roundtable: Roundtable,
    db_engine: AsyncEngine,
) -> None:
    """Called from main.py lifespan to inject instances."""
    global _roundtable, _db_engine
    _roundtable = roundtable
    _db_engine = db_engine
    logger.info("Roundtable router configured")


def _get_roundtable() -> Roundtable:
    if _roundtable is None:
        raise HTTPException(status_code=503, detail="Roundtable engine not initialized")
    return _roundtable


# ── Background task runner ───────────────────────────────────────────────────

async def _run_roundtable_task(
    request: StartRoundtableRequest,
    roundtable: Roundtable,
) -> None:
    """Run a roundtable in the background and store the result."""
    # Generate a predictable session_id prefix so we can track it
    import hashlib
    key = hashlib.sha256(f"{request.topic}:{','.join(request.agent_ids)}".encode()).hexdigest()[:16]

    try:
        _running[key] = {"status": "running", "topic": request.topic, "participants": request.agent_ids}

        result = await roundtable.discuss(
            topic=request.topic,
            agent_ids=request.agent_ids,
            rounds=request.rounds,
            synthesizer_id=request.synthesizer_id,
            agent_timeout=request.agent_timeout,
            total_timeout=request.total_timeout,
        )

        _completed[result.session_id] = result
        _running[key] = {"status": "completed", "session_id": result.session_id}
        logger.info("Roundtable completed: %s (%d turns)", result.session_id, result.turn_count)

    except Exception as e:
        logger.error("Roundtable failed: %s", e)
        _running[key] = {"status": "failed", "error": str(e)}


# ── REST Endpoints ───────────────────────────────────────────────────────────


@router.post("", response_model=RoundtableResponse, status_code=201)
async def start_roundtable(
    body: StartRoundtableRequest,
    roundtable: Roundtable = Depends(_get_roundtable),
):
    """
    Start a new roundtable discussion (synchronous — waits for completion).

    Runs all rounds + synthesis, then returns the full result.
    For large discussions, use the /async endpoint instead.
    """
    try:
        result = await roundtable.discuss(
            topic=body.topic,
            agent_ids=body.agent_ids,
            rounds=body.rounds,
            synthesizer_id=body.synthesizer_id,
            agent_timeout=body.agent_timeout,
            total_timeout=body.total_timeout,
        )

        _completed[result.session_id] = result

        return RoundtableResponse(
            session_id=result.session_id,
            topic=result.topic,
            participants=result.participants,
            rounds=result.rounds,
            turn_count=result.turn_count,
            synthesis=result.synthesis,
            synthesizer_id=result.synthesizer_id,
            total_duration_ms=result.total_duration_ms,
            created_at=result.created_at.isoformat(),
            turns=[
                RoundtableTurnResponse(
                    agent_id=t.agent_id,
                    round=t.round_number,
                    content=t.content,
                    duration_ms=t.duration_ms,
                )
                for t in result.turns
            ],
        )
    except Exception as e:
        logger.error("Roundtable failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/async", response_model=RoundtableStatusResponse, status_code=202)
async def start_roundtable_async(
    body: StartRoundtableRequest,
    background_tasks: BackgroundTasks,
    roundtable: Roundtable = Depends(_get_roundtable),
):
    """
    Start a roundtable in the background (non-blocking).

    Returns immediately with a tracking key. Poll /status/{key} to check.
    """
    import hashlib
    key = hashlib.sha256(f"{body.topic}:{','.join(body.agent_ids)}".encode()).hexdigest()[:16]

    background_tasks.add_task(_run_roundtable_task, body, roundtable)

    return RoundtableStatusResponse(
        session_id=key,
        status="running",
        topic=body.topic,
        participants=body.agent_ids,
        message="Roundtable started in background. Poll GET /engine/roundtable/status/{session_id}",
    )


@router.get("", response_model=PaginatedRoundtables)
async def list_roundtables(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    roundtable: Roundtable = Depends(_get_roundtable),
):
    """
    List recent roundtable sessions with pagination.
    """
    offset = (page - 1) * page_size

    try:
        rows = await roundtable.list_roundtables(limit=page_size, offset=offset)

        # Get total count
        if _db_engine is not None:
            async with _db_engine.begin() as conn:
                result = await conn.execute(
                    text("""
                        SELECT COUNT(*) FROM aria_engine.chat_sessions
                        WHERE session_type = 'roundtable'
                    """)
                )
                total = result.scalar() or 0
        else:
            total = len(rows)

        return PaginatedRoundtables(
            items=[
                RoundtableSummary(
                    session_id=r["session_id"],
                    title=r.get("title"),
                    participants=r.get("participants", []),
                    message_count=r.get("message_count", 0),
                    created_at=r.get("created_at"),
                )
                for r in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
    except Exception as e:
        logger.error("List roundtables failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Static paths MUST come before /{session_id} to avoid route collision ─────


@router.get("/agents/available")
async def get_available_agents():
    """Get list of agents available for roundtable participation."""
    if _db_engine is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with _db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT agent_id, display_name, agent_type, status,
                           focus_type, pheromone_score
                    FROM aria_engine.engine_agent_state
                    WHERE status != 'terminated'
                    ORDER BY pheromone_score DESC
                """)
            )
            rows = result.mappings().all()

        return {
            "agents": [
                {
                    "agent_id": r["agent_id"],
                    "display_name": r["display_name"],
                    "agent_type": r["agent_type"],
                    "status": r["status"],
                    "focus_type": r["focus_type"],
                    "pheromone_score": float(r["pheromone_score"]) if r["pheromone_score"] else 0.0,
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error("Get available agents failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{key}")
async def get_roundtable_status(key: str):
    """Check status of an async roundtable started via /async."""
    if key in _running:
        info = _running[key]
        return RoundtableStatusResponse(
            session_id=info.get("session_id", key),
            status=info["status"],
            topic=info.get("topic"),
            participants=info.get("participants", []),
            message=info.get("error"),
        )

    # Maybe it just finished and the key matches a session_id
    if key in _completed:
        return RoundtableStatusResponse(
            session_id=key,
            status="completed",
            topic=_completed[key].topic,
            participants=_completed[key].participants,
            turn_count=_completed[key].turn_count,
        )

    raise HTTPException(status_code=404, detail=f"No roundtable tracking for key: {key}")


# ── Parameterized paths /{session_id} ────────────────────────────────────────


@router.get("/{session_id}")
async def get_roundtable(session_id: str):
    """
    Get roundtable detail — turns, synthesis, metadata.

    First checks in-memory cache of recently completed roundtables,
    then falls back to DB query.
    """
    # Check in-memory cache first (recently completed)
    if session_id in _completed:
        result = _completed[session_id]
        return result.to_dict()

    # Fallback: load from DB
    if _db_engine is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with _db_engine.begin() as conn:
            # Load session
            session_result = await conn.execute(
                text("""
                    SELECT id, title, metadata, created_at
                    FROM aria_engine.chat_sessions
                    WHERE id = :sid AND session_type = 'roundtable'
                """),
                {"sid": session_id},
            )
            session_row = session_result.mappings().first()
            if session_row is None:
                raise HTTPException(status_code=404, detail=f"Roundtable {session_id} not found")

            # Load all messages/turns
            msg_result = await conn.execute(
                text("""
                    SELECT role, content, metadata, created_at
                    FROM aria_engine.chat_messages
                    WHERE session_id = :sid
                    ORDER BY created_at ASC
                """),
                {"sid": session_id},
            )
            messages = msg_result.mappings().all()

            metadata = session_row["metadata"] or {}
            participants = metadata.get("participants", []) if isinstance(metadata, dict) else []

            turns = []
            synthesis = ""
            for msg in messages:
                meta = msg.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}

                if msg["role"] == "synthesis":
                    synthesis = msg["content"]
                else:
                    # Parse round number from role like "round-1"
                    round_num = 0
                    role = msg["role"] or ""
                    if role.startswith("round-"):
                        try:
                            round_num = int(role.split("-")[1])
                        except (IndexError, ValueError):
                            pass

                    turns.append({
                        "agent_id": meta.get("agent_id", "unknown"),
                        "round": round_num,
                        "content": msg["content"],
                        "duration_ms": 0,
                    })

            return {
                "session_id": str(session_row["id"]),
                "topic": (session_row["title"] or "").replace("Roundtable: ", ""),
                "participants": participants,
                "rounds": max((t["round"] for t in turns), default=0),
                "turn_count": len(turns),
                "synthesis": synthesis,
                "synthesizer_id": "main",
                "total_duration_ms": 0,
                "created_at": session_row["created_at"].isoformat() if session_row["created_at"] else None,
                "turns": turns,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get roundtable failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/turns")
async def get_roundtable_turns(session_id: str):
    """
    Get just the turns for a roundtable — lightweight endpoint for
    progressive loading / polling during a running roundtable.
    """
    if session_id in _completed:
        result = _completed[session_id]
        return {
            "session_id": session_id,
            "turns": [
                {
                    "agent_id": t.agent_id,
                    "round": t.round_number,
                    "content": t.content,
                    "duration_ms": t.duration_ms,
                }
                for t in result.turns
            ],
        }

    # From DB
    if _db_engine is None:
        raise HTTPException(status_code=503, detail="Database not available")

    async with _db_engine.begin() as conn:
        msg_result = await conn.execute(
            text("""
                SELECT role, content, metadata
                FROM aria_engine.chat_messages
                WHERE session_id = :sid
                ORDER BY created_at ASC
            """),
            {"sid": session_id},
        )
        messages = msg_result.mappings().all()

    turns = []
    for msg in messages:
        role = msg["role"] or ""
        if role.startswith("round-"):
            meta = msg.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            try:
                round_num = int(role.split("-")[1])
            except (IndexError, ValueError):
                round_num = 0
            turns.append({
                "agent_id": meta.get("agent_id", "unknown"),
                "round": round_num,
                "content": msg["content"],
                "duration_ms": 0,
            })

    return {"session_id": session_id, "turns": turns}


@router.delete("/{session_id}")
async def delete_roundtable(session_id: str):
    """End/archive a roundtable session."""
    if _db_engine is None:
        raise HTTPException(status_code=503, detail="Database not available")

    try:
        async with _db_engine.begin() as conn:
            result = await conn.execute(
                text("""
                    UPDATE aria_engine.chat_sessions
                    SET status = 'ended', updated_at = NOW()
                    WHERE id = :sid AND session_type = 'roundtable'
                    RETURNING id
                """),
                {"sid": session_id},
            )
            row = result.first()
            if row is None:
                raise HTTPException(status_code=404, detail=f"Roundtable {session_id} not found")

        # Clean up in-memory cache
        _completed.pop(session_id, None)

        return {"status": "ended", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete roundtable failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Swarm endpoints ──────────────────────────────────────────────────────────

_swarm_orchestrator: Any = None
_swarm_running: dict[str, dict[str, Any]] = {}
_swarm_completed: dict[str, Any] = {}


def configure_swarm(swarm) -> None:
    """Called from main.py lifespan to inject SwarmOrchestrator."""
    global _swarm_orchestrator
    _swarm_orchestrator = swarm
    logger.info("Swarm router configured")


def _get_swarm():
    if _swarm_orchestrator is None:
        raise HTTPException(status_code=503, detail="Swarm engine not initialized")
    return _swarm_orchestrator


class StartSwarmRequest(BaseModel):
    """Request body for starting a swarm decision."""
    topic: str = Field(..., min_length=2, max_length=2000)
    agent_ids: list[str] = Field(..., min_length=2, max_length=12)
    max_iterations: int = Field(default=5, ge=1, le=10)
    consensus_threshold: float = Field(default=0.7, ge=0.3, le=1.0)
    agent_timeout: int = Field(default=60, ge=10, le=300)
    total_timeout: int = Field(default=600, ge=30, le=1800)


class SwarmResponse(BaseModel):
    """Response for a completed swarm."""
    session_id: str
    topic: str
    participants: list[str]
    iterations: int
    vote_count: int
    consensus: str
    consensus_score: float
    converged: bool
    total_duration_ms: int
    created_at: str
    votes: list[dict] = Field(default_factory=list)


@router.post("/swarm", response_model=SwarmResponse, status_code=201)
async def start_swarm(body: StartSwarmRequest):
    """Start a synchronous swarm decision process."""
    swarm = _get_swarm()
    try:
        result = await swarm.execute(
            topic=body.topic,
            agent_ids=body.agent_ids,
            max_iterations=body.max_iterations,
            consensus_threshold=body.consensus_threshold,
            agent_timeout=body.agent_timeout,
            total_timeout=body.total_timeout,
        )
        _swarm_completed[result.session_id] = result
        d = result.to_dict()
        return SwarmResponse(**d)
    except Exception as e:
        logger.error("Swarm failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swarm/async", status_code=202)
async def start_swarm_async(
    body: StartSwarmRequest,
    background_tasks: BackgroundTasks,
):
    """Start a swarm in the background."""
    import hashlib
    swarm = _get_swarm()
    key = hashlib.sha256(
        f"swarm:{body.topic}:{','.join(body.agent_ids)}".encode()
    ).hexdigest()[:16]

    async def _run():
        try:
            _swarm_running[key] = {
                "status": "running", "topic": body.topic,
                "participants": body.agent_ids,
            }
            result = await swarm.execute(
                topic=body.topic, agent_ids=body.agent_ids,
                max_iterations=body.max_iterations,
                consensus_threshold=body.consensus_threshold,
            )
            _swarm_completed[result.session_id] = result
            _swarm_running[key] = {
                "status": "completed", "session_id": result.session_id,
            }
        except Exception as e:
            logger.error("Async swarm failed: %s", e)
            _swarm_running[key] = {"status": "failed", "error": str(e)}

    background_tasks.add_task(_run)
    return {
        "key": key, "status": "running",
        "topic": body.topic, "participants": body.agent_ids,
    }


@router.get("/swarm/status/{key}")
async def get_swarm_status(key: str):
    """Poll async swarm status."""
    if key in _swarm_running:
        return _swarm_running[key]
    raise HTTPException(status_code=404, detail=f"No swarm tracking for key: {key}")


@router.get("/swarm/{session_id}")
async def get_swarm(session_id: str):
    """Get swarm detail from cache or DB."""
    if session_id in _swarm_completed:
        return _swarm_completed[session_id].to_dict()

    if _db_engine is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # Fallback: load from DB (same schema as roundtable but session_type='swarm')
    try:
        async with _db_engine.begin() as conn:
            session_result = await conn.execute(
                text("""
                    SELECT id, title, metadata, created_at
                    FROM aria_engine.chat_sessions
                    WHERE id = :sid AND session_type = 'swarm'
                """),
                {"sid": session_id},
            )
            row = session_result.mappings().first()
            if row is None:
                raise HTTPException(status_code=404, detail=f"Swarm {session_id} not found")

            msg_result = await conn.execute(
                text("""
                    SELECT role, content, metadata
                    FROM aria_engine.chat_messages
                    WHERE session_id = :sid ORDER BY created_at ASC
                """),
                {"sid": session_id},
            )
            messages = msg_result.mappings().all()

            metadata = row["metadata"] or {}
            participants = metadata.get("participants", []) if isinstance(metadata, dict) else []

            votes = []
            consensus = ""
            for msg in messages:
                meta = msg.get("metadata") or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}

                if msg["role"] == "consensus":
                    consensus = msg["content"]
                elif (msg["role"] or "").startswith("swarm-"):
                    try:
                        iteration = int(msg["role"].split("-")[1])
                    except (IndexError, ValueError):
                        iteration = 0
                    votes.append({
                        "agent_id": meta.get("agent_id", "unknown"),
                        "iteration": iteration,
                        "content": msg["content"],
                        "vote": "extend",
                        "confidence": 0.5,
                        "duration_ms": 0,
                    })

            return {
                "session_id": str(row["id"]),
                "topic": (row["title"] or "").replace("Swarm: ", ""),
                "participants": participants,
                "iterations": max((v["iteration"] for v in votes), default=0),
                "vote_count": len(votes),
                "consensus": consensus,
                "consensus_score": 0.0,
                "converged": False,
                "total_duration_ms": 0,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "votes": votes,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get swarm failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket streaming for roundtable + swarm ───────────────────────────────


@ws_router.websocket("/ws/roundtable")
async def roundtable_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for streaming roundtable/swarm in real-time.

    Client sends: {"type": "start", "mode": "roundtable"|"swarm", "topic": "...", "agent_ids": [...]}
    Server sends: {"type": "turn", "agent_id": "...", "round": 1, "content": "...", "duration_ms": N}
    Server sends: {"type": "vote", "agent_id": "...", "iteration": 1, "vote": "agree", ...}
    Server sends: {"type": "synthesis"|"consensus", "content": "..."}
    Server sends: {"type": "done", "session_id": "...", ...}
    Server sends: {"type": "error", "message": "..."}
    """
    if _roundtable is None:
        await websocket.close(code=1013, reason="Roundtable not initialized")
        return

    await websocket.accept()
    logger.info("Roundtable WS connected")

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "ping":
                await _ws_send(websocket, {"type": "pong"})

            elif msg_type == "start":
                mode = data.get("mode", "roundtable")
                topic = data.get("topic", "").strip()
                agent_ids = data.get("agent_ids", [])

                if not topic or len(agent_ids) < 2:
                    await _ws_send(websocket, {
                        "type": "error",
                        "message": "Need topic and at least 2 agent_ids",
                    })
                    continue

                if mode == "swarm" and _swarm_orchestrator is not None:
                    await _handle_swarm_ws(websocket, topic, agent_ids, data)
                else:
                    await _handle_roundtable_ws(websocket, topic, agent_ids, data)

            else:
                await _ws_send(websocket, {
                    "type": "error",
                    "message": f"Unknown type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("Roundtable WS disconnected")
    except Exception as e:
        logger.error("Roundtable WS error: %s", e)
        try:
            await _ws_send(websocket, {"type": "error", "message": str(e)})
        except Exception:
            pass


async def _handle_roundtable_ws(
    websocket: WebSocket,
    topic: str,
    agent_ids: list[str],
    data: dict,
) -> None:
    """Run a roundtable with turn-by-turn WS streaming."""
    rounds = data.get("rounds", 3)
    synthesizer = data.get("synthesizer_id", "main")

    async def on_turn(turn):
        """Callback fired after each agent turn."""
        await _ws_send(websocket, {
            "type": "turn",
            "agent_id": turn.agent_id,
            "round": turn.round_number,
            "content": turn.content,
            "duration_ms": turn.duration_ms,
        })

    try:
        result = await _roundtable.discuss(
            topic=topic,
            agent_ids=agent_ids,
            rounds=rounds,
            synthesizer_id=synthesizer,
            on_turn=on_turn,
        )
        _completed[result.session_id] = result

        await _ws_send(websocket, {
            "type": "synthesis",
            "content": result.synthesis,
            "synthesizer_id": result.synthesizer_id,
        })
        await _ws_send(websocket, {
            "type": "done",
            "session_id": result.session_id,
            "turn_count": result.turn_count,
            "total_duration_ms": result.total_duration_ms,
        })
    except Exception as e:
        await _ws_send(websocket, {"type": "error", "message": str(e)})


async def _handle_swarm_ws(
    websocket: WebSocket,
    topic: str,
    agent_ids: list[str],
    data: dict,
) -> None:
    """Run a swarm with vote-by-vote WS streaming."""
    max_iterations = data.get("max_iterations", 5)
    threshold = data.get("consensus_threshold", 0.7)

    async def on_vote(vote):
        """Callback fired after each agent vote."""
        await _ws_send(websocket, {
            "type": "vote",
            "agent_id": vote.agent_id,
            "iteration": vote.iteration,
            "content": vote.content,
            "vote": vote.vote,
            "confidence": vote.confidence,
            "duration_ms": vote.duration_ms,
        })

    try:
        result = await _swarm_orchestrator.execute(
            topic=topic,
            agent_ids=agent_ids,
            max_iterations=max_iterations,
            consensus_threshold=threshold,
            on_vote=on_vote,
        )
        _swarm_completed[result.session_id] = result

        await _ws_send(websocket, {
            "type": "consensus",
            "content": result.consensus,
            "consensus_score": result.consensus_score,
            "converged": result.converged,
        })
        await _ws_send(websocket, {
            "type": "done",
            "session_id": result.session_id,
            "vote_count": result.vote_count,
            "iterations": result.iterations,
            "total_duration_ms": result.total_duration_ms,
        })
    except Exception as e:
        await _ws_send(websocket, {"type": "error", "message": str(e)})


async def _ws_send(websocket: WebSocket, data: dict) -> None:
    """Send JSON over WebSocket, silently handling disconnection."""
    try:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps(data))
    except Exception:
        pass


# ── Registration helper ──────────────────────────────────────────────────────


def register_roundtable(app) -> None:
    """Register both REST + WebSocket routers."""
    app.include_router(router)
    app.include_router(ws_router)
    logger.info("Registered roundtable routes: %s + WS /ws/roundtable", router.prefix)
