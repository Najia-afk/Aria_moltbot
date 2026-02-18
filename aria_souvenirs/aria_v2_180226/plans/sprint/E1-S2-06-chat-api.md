# S2-06: Chat API Endpoints (REST + WebSocket Router)
**Epic:** E1 — Engine Core | **Priority:** P0 | **Points:** 5 | **Phase:** 2

## Problem
The engine has a `ChatEngine` (S2-01), `ContextManager` (S2-02), `StreamManager` (S2-03), and export functions (S2-04) — but no HTTP/WebSocket endpoints expose them. The existing `src/api/routers/sessions.py` is 80% OpenClaw sync logic that reads from the filesystem. We need a new, clean router that exposes the native engine's chat capabilities via REST + WebSocket.

## Root Cause
All existing session endpoints in `src/api/routers/sessions.py` (962 lines) are coupled to OpenClaw: `OPENCLAW_SESSIONS_INDEX_PATH`, `OPENCLAW_AGENTS_ROOT`, `_OPENCLAW_UUID_NAMESPACE`, `_normalize_live_session()`, etc. These read from OpenClaw's filesystem, sync to PostgreSQL, and serve hybrid data. A clean engine router must be created separately so we can:
1. Run both old (OpenClaw) and new (engine) routers in parallel during migration
2. Provide a clean API surface for the new chat UI
3. Eventually deprecate and remove the old sessions router (Sprint 8)

## Fix
### `src/api/routers/engine_chat.py`
```python
"""
Engine Chat API — REST + WebSocket endpoints for Aria Engine chat.

REST endpoints:
  POST   /api/engine/chat/sessions              — create a new session
  GET    /api/engine/chat/sessions              — list sessions (paginated)
  GET    /api/engine/chat/sessions/{id}         — get session with messages
  POST   /api/engine/chat/sessions/{id}/messages — send message (non-streaming)
  DELETE /api/engine/chat/sessions/{id}         — end/delete session
  GET    /api/engine/chat/sessions/{id}/export   — export JSONL or Markdown

WebSocket:
  WS     /ws/chat/{session_id}                  — streaming chat

All endpoints use the native aria_engine modules (no OpenClaw dependency).
"""
import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aria_engine.config import EngineConfig
from aria_engine.chat_engine import ChatEngine, ChatResponse
from aria_engine.context_manager import ContextManager
from aria_engine.export import export_session
from aria_engine.prompts import PromptAssembler
from aria_engine.streaming import StreamManager

logger = logging.getLogger("aria.api.engine_chat")

router = APIRouter(prefix="/api/engine/chat", tags=["Engine Chat"])
ws_router = APIRouter(tags=["Engine Chat WebSocket"])


# ── Pydantic Models ──────────────────────────────────────────────────────────


class CreateSessionRequest(BaseModel):
    """Request body for creating a new chat session."""
    agent_id: str = Field(default="main", description="Agent owning this session")
    model: Optional[str] = Field(default=None, description="LLM model (defaults to config)")
    session_type: str = Field(default="interactive", description="Session type")
    system_prompt: Optional[str] = Field(default=None, description="Override system prompt")
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    context_window: int = Field(default=50, ge=1, le=500)
    metadata: Optional[dict] = Field(default=None, description="Arbitrary metadata")


class CreateSessionResponse(BaseModel):
    """Response for session creation."""
    id: str
    agent_id: str
    model: Optional[str]
    status: str
    session_type: str
    created_at: Optional[str]


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""
    content: str = Field(..., min_length=1, max_length=100000, description="Message content")
    enable_thinking: bool = Field(default=False, description="Request reasoning tokens")
    enable_tools: bool = Field(default=True, description="Allow tool calling")


class SendMessageResponse(BaseModel):
    """Response for a sent message."""
    message_id: str
    session_id: str
    content: str
    thinking: Optional[str] = None
    tool_calls: Optional[list] = None
    tool_results: Optional[list] = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = ""


class SessionSummary(BaseModel):
    """Summary of a session for list endpoints."""
    id: str
    agent_id: str
    title: Optional[str] = None
    model: Optional[str] = None
    status: str
    session_type: str
    message_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ended_at: Optional[str] = None


class SessionDetail(SessionSummary):
    """Full session with messages."""
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context_window: int = 50
    messages: list = Field(default_factory=list)
    metadata: Optional[dict] = None


class PaginatedSessions(BaseModel):
    """Paginated list of sessions."""
    items: list[SessionSummary]
    total: int
    page: int
    page_size: int
    pages: int


# ── Dependency Injection ─────────────────────────────────────────────────────

# These will be initialized at app startup and injected via FastAPI depends.
# In production, these are set in src/api/main.py during lifespan.

_engine_config: Optional[EngineConfig] = None
_chat_engine: Optional[ChatEngine] = None
_stream_manager: Optional[StreamManager] = None
_context_manager: Optional[ContextManager] = None
_prompt_assembler: Optional[PromptAssembler] = None


def configure_engine(
    config: EngineConfig,
    chat_engine: ChatEngine,
    stream_manager: StreamManager,
    context_manager: ContextManager,
    prompt_assembler: PromptAssembler,
) -> None:
    """
    Configure the engine chat router with initialized instances.

    Called once during app startup in src/api/main.py.
    """
    global _engine_config, _chat_engine, _stream_manager, _context_manager, _prompt_assembler
    _engine_config = config
    _chat_engine = chat_engine
    _stream_manager = stream_manager
    _context_manager = context_manager
    _prompt_assembler = prompt_assembler
    logger.info("Engine chat router configured")


def _get_engine() -> ChatEngine:
    """Dependency: get ChatEngine instance."""
    if _chat_engine is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _chat_engine


def _get_config() -> EngineConfig:
    """Dependency: get EngineConfig instance."""
    if _engine_config is None:
        raise HTTPException(status_code=503, detail="Engine not initialized")
    return _engine_config


# ── REST Endpoints ───────────────────────────────────────────────────────────


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    body: CreateSessionRequest,
    engine: ChatEngine = Depends(_get_engine),
):
    """
    Create a new chat session.

    Returns the created session with its UUID.
    """
    try:
        session = await engine.create_session(
            agent_id=body.agent_id,
            model=body.model,
            session_type=body.session_type,
            system_prompt=body.system_prompt,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            context_window=body.context_window,
            metadata=body.metadata,
        )
        return CreateSessionResponse(
            id=session["id"],
            agent_id=session["agent_id"],
            model=session.get("model"),
            status=session["status"],
            session_type=session["session_type"],
            created_at=session.get("created_at"),
        )
    except Exception as e:
        logger.error("Failed to create session: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=PaginatedSessions)
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    agent_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    engine: ChatEngine = Depends(_get_engine),
):
    """
    List chat sessions with pagination and optional filtering.
    """
    from db.models import EngineChatSession
    from deps import get_db

    async for db in get_db():
        query = select(EngineChatSession).order_by(
            EngineChatSession.updated_at.desc()
        )

        if agent_id:
            query = query.where(EngineChatSession.agent_id == agent_id)
        if status:
            query = query.where(EngineChatSession.status == status)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await db.execute(query)
        sessions = result.scalars().all()

        items = [
            SessionSummary(
                id=str(s.id),
                agent_id=s.agent_id,
                title=s.title,
                model=s.model,
                status=s.status,
                session_type=s.session_type,
                message_count=s.message_count or 0,
                total_tokens=s.total_tokens or 0,
                total_cost=float(s.total_cost or 0),
                created_at=s.created_at.isoformat() if s.created_at else None,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
            )
            for s in sessions
        ]

        pages = max(1, (total + page_size - 1) // page_size)

        return PaginatedSessions(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    engine: ChatEngine = Depends(_get_engine),
):
    """
    Get a session with its full message history.
    """
    from aria_engine.exceptions import SessionError

    try:
        session = await engine.resume_session(session_id)
        messages = session.pop("messages", [])

        return SessionDetail(
            id=session["id"],
            agent_id=session["agent_id"],
            title=session.get("title"),
            model=session.get("model"),
            status=session["status"],
            session_type=session["session_type"],
            message_count=session.get("message_count", 0),
            total_tokens=session.get("total_tokens", 0),
            total_cost=session.get("total_cost", 0),
            system_prompt=session.get("system_prompt"),
            temperature=session.get("temperature"),
            max_tokens=session.get("max_tokens"),
            context_window=session.get("context_window", 50),
            messages=messages,
            metadata=session.get("metadata"),
            created_at=session.get("created_at"),
            updated_at=session.get("updated_at"),
            ended_at=session.get("ended_at"),
        )
    except SessionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(
    session_id: str,
    body: SendMessageRequest,
    engine: ChatEngine = Depends(_get_engine),
):
    """
    Send a message to a session and get a non-streaming response.

    For streaming responses, use the WebSocket endpoint at /ws/chat/{session_id}.
    """
    from aria_engine.exceptions import SessionError, LLMError

    try:
        response: ChatResponse = await engine.send_message(
            session_id=session_id,
            content=body.content,
            enable_thinking=body.enable_thinking,
            enable_tools=body.enable_tools,
        )
        return SendMessageResponse(
            message_id=response.message_id,
            session_id=response.session_id,
            content=response.content,
            thinking=response.thinking,
            tool_calls=response.tool_calls,
            tool_results=response.tool_results,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            finish_reason=response.finish_reason,
        )
    except SessionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error("send_message failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    engine: ChatEngine = Depends(_get_engine),
):
    """
    End (close) a session. Marks it as ended but preserves history.
    """
    from aria_engine.exceptions import SessionError

    try:
        session = await engine.end_session(session_id)
        return {"status": "ended", "session_id": session["id"]}
    except SessionError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sessions/{session_id}/export")
async def export_session_endpoint(
    session_id: str,
    format: str = Query(default="jsonl", regex="^(jsonl|markdown|md)$"),
    config: EngineConfig = Depends(_get_config),
    engine: ChatEngine = Depends(_get_engine),
):
    """
    Export a session as JSONL or Markdown.

    Query params:
      - format: 'jsonl' or 'markdown' (default: 'jsonl')

    Returns the export content as a downloadable response.
    """
    from fastapi.responses import Response
    from aria_engine.exceptions import SessionError

    try:
        content = await export_session(
            session_id=session_id,
            db_session_factory=engine._db_factory,
            config=config,
            format=format,
            save_to_disk=True,
        )

        if format == "jsonl":
            return Response(
                content=content,
                media_type="application/x-jsonlines",
                headers={
                    "Content-Disposition": f'attachment; filename="{session_id}.jsonl"'
                },
            )
        else:
            return Response(
                content=content,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f'attachment; filename="{session_id}.md"'
                },
            )
    except SessionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── WebSocket Endpoint ───────────────────────────────────────────────────────


@ws_router.websocket("/ws/chat/{session_id}")
async def chat_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for streaming chat.

    Protocol:
      Client sends: {"type": "message", "content": "Hello!", "enable_thinking": false}
      Server sends: {"type": "token", "content": "Hi"}, ..., {"type": "done", ...}

    See aria_engine/streaming.py for full protocol documentation.
    """
    if _stream_manager is None:
        await websocket.close(code=1013, reason="Engine not initialized")
        return

    try:
        await _stream_manager.handle_connection(websocket, session_id)
    except Exception as e:
        logger.error("WebSocket error for session %s: %s", session_id, e)
        try:
            await websocket.close(code=1011, reason=str(e))
        except Exception:
            pass


# ── Registration helper ──────────────────────────────────────────────────────


def register_engine_chat(app) -> None:
    """
    Register the engine chat routers with the FastAPI app.

    Called from src/api/main.py:
        from routers.engine_chat import register_engine_chat, configure_engine
        register_engine_chat(app)
    """
    app.include_router(router)
    app.include_router(ws_router)
    logger.info(
        "Registered engine chat routes: %s + WS /ws/chat/{session_id}",
        router.prefix,
    )
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | API router at Layer 2 (API), calls engine at business logic layer |
| 2 | .env for secrets (zero in code) | ✅ | All config via EngineConfig from env |
| 3 | models.yaml single source of truth | ✅ | Model comes from session, resolved in LLMGateway |
| 4 | Docker-first testing | ✅ | FastAPI runs in Docker container |
| 5 | aria_memories only writable path | ✅ | Export writes to aria_memories/exports/ only |
| 6 | No soul modification | ❌ | No soul access in API router |

## Dependencies
- S1-01 must complete first (aria_engine package)
- S1-05 must complete first (ORM models)
- S2-01 must complete first (ChatEngine)
- S2-02 should complete first (ContextManager)
- S2-03 must complete first (StreamManager for WebSocket)
- S2-04 must complete first (export functions)
- S2-05 should complete first (PromptAssembler)

## Verification
```bash
# 1. Module imports:
python -c "from routers.engine_chat import router, ws_router, register_engine_chat, configure_engine; print('OK')"
# EXPECTED: OK (run from src/api/ directory)

# 2. Pydantic models validate:
python -c "
import sys; sys.path.insert(0, 'src/api')
from routers.engine_chat import (
    CreateSessionRequest, CreateSessionResponse,
    SendMessageRequest, SendMessageResponse,
    SessionSummary, SessionDetail, PaginatedSessions,
)
# Test default creation
req = CreateSessionRequest()
assert req.agent_id == 'main'
assert req.context_window == 50

# Test message validation
msg = SendMessageRequest(content='Hello!')
assert msg.content == 'Hello!'
assert msg.enable_thinking == False

# Test response model
resp = SendMessageResponse(message_id='m1', session_id='s1', content='Hi')
assert resp.total_tokens == 0

print('Pydantic models OK')
"
# EXPECTED: Pydantic models OK

# 3. Router has correct routes:
python -c "
import sys; sys.path.insert(0, 'src/api')
from routers.engine_chat import router, ws_router
routes = [r.path for r in router.routes]
assert '/sessions' in routes or any('/sessions' in str(r.path) for r in router.routes)
print(f'REST routes: {len(router.routes)}')
print(f'WS routes: {len(ws_router.routes)}')
"
# EXPECTED: REST routes: 6, WS routes: 1

# 4. Registration helper works:
python -c "
import sys; sys.path.insert(0, 'src/api')
from fastapi import FastAPI
from routers.engine_chat import register_engine_chat
app = FastAPI()
register_engine_chat(app)
print(f'Total app routes: {len(app.routes)}')
"
# EXPECTED: Total app routes: > 6
```

## Prompt for Agent
```
Implement the Chat API endpoints — REST + WebSocket router for Aria Engine.

FILES TO READ FIRST:
- aria_engine/chat_engine.py (ChatEngine, ChatResponse — created in S2-01)
- aria_engine/context_manager.py (ContextManager — created in S2-02)
- aria_engine/streaming.py (StreamManager — created in S2-03)
- aria_engine/export.py (export_session — created in S2-04)
- aria_engine/prompts.py (PromptAssembler — created in S2-05)
- src/api/routers/sessions.py (lines 1-50 — existing router pattern, imports)
- src/api/main.py (lines 250-280 — router registration pattern)
- src/api/deps.py (full file — dependency injection pattern)
- src/api/pagination.py (full file — pagination utilities)

STEPS:
1. Read all files above
2. Create src/api/routers/engine_chat.py
3. Define Pydantic request/response models
4. Implement REST endpoints:
   - POST /api/engine/chat/sessions
   - GET /api/engine/chat/sessions (paginated)
   - GET /api/engine/chat/sessions/{id}
   - POST /api/engine/chat/sessions/{id}/messages
   - DELETE /api/engine/chat/sessions/{id}
   - GET /api/engine/chat/sessions/{id}/export
5. Implement WebSocket endpoint: /ws/chat/{session_id}
6. Implement configure_engine() for dependency injection
7. Implement register_engine_chat() for app registration
8. Run verification commands

CONSTRAINTS:
- Constraint 1: Router is at API layer — delegates to engine layer
- Use Pydantic v2 models for all request/response validation
- Separate REST router (prefix=/api/engine/chat) and WS router (no prefix)
- configure_engine() called at startup, not in each request
- register_engine_chat() must be called in src/api/main.py
```
