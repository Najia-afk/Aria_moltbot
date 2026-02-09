# aria_skills/database/__init__.py
"""
PostgreSQL database skill — SQLAlchemy 2.0 + psycopg 3.

⚠️  DEPRECATED: This skill is deprecated as of Aria Blue v1.1.
    All new code should use ``aria_skills.api_client`` (AriaAPIClient)
    for database operations via the REST API layer.

Provides ORM-based CRUD for all Aria tables plus generic
execute/fetch helpers that accept raw SQL when needed.

Migration note (v3.0):
  - asyncpg replaced by psycopg 3 via SQLAlchemy async
  - All Aria-specific helpers use ORM models from ``src/api/db/models``
  - Connection pooling handled by SQLAlchemy create_async_engine
"""
import os
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence

warnings.warn(
    "aria_skills.database is deprecated — use api_client skill for all DB access",
    DeprecationWarning,
    stacklevel=2,
)

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

# ---------------------------------------------------------------------------
# Optional imports – degrade gracefully when deps are missing
# ---------------------------------------------------------------------------
try:
    from sqlalchemy import text, select, insert, update, delete, func, desc
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

# Try to import the canonical ORM models.  When running *inside* the
# aria-api container the import path is straightforward.  Outside the
# container (e.g. tests) models may not be on sys.path, so we tolerate
# an ImportError and fall back to raw-SQL-only mode.
try:
    from db.models import (
        Base,
        Memory, Thought, Goal, ActivityLog, SocialPost,
        HourlyGoal, KnowledgeEntity, KnowledgeRelation,
        PerformanceLog, PendingComplexTask, HeartbeatLog,
        ScheduledJob, SecurityEvent, ScheduleTick,
        AgentSession, ModelUsage, RateLimit, ApiKeyRotation,
    )
    HAS_ORM_MODELS = True
except ImportError:
    HAS_ORM_MODELS = False


def _as_psycopg_url(dsn: str) -> str:
    """Convert any postgres:// URL to the psycopg async dialect."""
    url = dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    url = url.replace("postgres://", "postgresql+psycopg://")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@SkillRegistry.register
class DatabaseSkill(BaseSkill):
    """
    PostgreSQL database skill (SQLAlchemy 2 + psycopg 3).

    Config:
        dsn: Connection string or ``env:VAR_NAME``
        pool_size:
            min: Minimum pool connections (default: 2)
            max: Maximum pool connections (default: 10)
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._engine: Optional["AsyncEngine"] = None
        self._session_factory: Optional["async_sessionmaker"] = None
        self._dsn: Optional[str] = None

    @property
    def name(self) -> str:
        return "database"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Create engine + session factory."""
        if not HAS_SQLALCHEMY:
            self.logger.error("sqlalchemy[asyncio] not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._dsn = self._get_env_value("dsn")
        if not self._dsn:
            # Fallback to common env vars
            self._dsn = os.environ.get("DATABASE_URL")
        if not self._dsn:
            self.logger.error("No DSN configured")
            self._status = SkillStatus.UNAVAILABLE
            return False

        pool_config = self.config.config.get("pool_size", {})
        pool_min = pool_config.get("min", 2)
        pool_max = pool_config.get("max", 10)

        try:
            url = _as_psycopg_url(self._dsn)
            self._engine = create_async_engine(
                url,
                pool_size=pool_max,
                pool_pre_ping=True,
                echo=False,
            )
            self._session_factory = async_sessionmaker(
                self._engine, expire_on_commit=False
            )
            self._status = SkillStatus.AVAILABLE
            self.logger.info(
                f"Database engine initialized (psycopg3, pool {pool_min}-{pool_max})"
            )
            return True
        except Exception as e:
            self.logger.error(f"Engine creation failed: {e}")
            self._status = SkillStatus.ERROR
            return False

    async def health_check(self) -> SkillStatus:
        """Verify database connectivity."""
        if not self._engine:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            self._status = SkillStatus.AVAILABLE
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        return self._status

    async def close(self) -> None:
        """Dispose engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._status = SkillStatus.UNAVAILABLE
            self.logger.info("Database engine disposed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator["AsyncSession", None]:
        """Yield an ``AsyncSession`` (auto-committed on success)."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized")
        async with self._session_factory() as sess:
            try:
                yield sess
                await sess.commit()
            except Exception:
                await sess.rollback()
                raise

    # ------------------------------------------------------------------
    # Generic helpers (raw SQL via text())
    # ------------------------------------------------------------------

    async def execute(self, query: str, *args, **kwargs) -> SkillResult:
        """Execute a raw SQL statement (INSERT/UPDATE/DELETE).

        .. deprecated:: 1.1
            Use ``api_client`` skill for all DB access instead.

        Accepts either positional ``$1`` placeholders (asyncpg compat)
        or named ``:param`` placeholders.  Positional args are re-written
        to named params automatically for SQLAlchemy.
        """
        self.logger.warning(
            "DatabaseSkill.execute() is deprecated — migrate to api_client"
        )
        if not self.is_available:
            return SkillResult.fail("Database not available")
        try:
            sql, params = self._prepare_query(query, args, kwargs)
            async with self.session() as sess:
                result = await sess.execute(text(sql), params)
                rowcount = result.rowcount if result.rowcount >= 0 else 0
            self._log_usage("execute", True)
            return SkillResult.ok({"affected_rows": rowcount})
        except Exception as e:
            self._log_usage("execute", False)
            return SkillResult.fail(str(e))

    async def fetch_one(self, query: str, *args, **kwargs) -> SkillResult:
        """Fetch a single row."""
        if not self.is_available:
            return SkillResult.fail("Database not available")
        try:
            sql, params = self._prepare_query(query, args, kwargs)
            async with self.session() as sess:
                result = await sess.execute(text(sql), params)
                row = result.mappings().first()
            self._log_usage("fetch_one", True)
            return SkillResult.ok(dict(row) if row else None)
        except Exception as e:
            self._log_usage("fetch_one", False)
            return SkillResult.fail(str(e))

    async def fetch_all(self, query: str, *args, **kwargs) -> SkillResult:
        """Fetch all matching rows."""
        if not self.is_available:
            return SkillResult.fail("Database not available")
        try:
            sql, params = self._prepare_query(query, args, kwargs)
            async with self.session() as sess:
                result = await sess.execute(text(sql), params)
                rows = result.mappings().all()
            self._log_usage("fetch_all", True)
            return SkillResult.ok([dict(r) for r in rows])
        except Exception as e:
            self._log_usage("fetch_all", False)
            return SkillResult.fail(str(e))

    async def fetch_value(self, query: str, *args, **kwargs) -> SkillResult:
        """Fetch a single scalar value."""
        if not self.is_available:
            return SkillResult.fail("Database not available")
        try:
            sql, params = self._prepare_query(query, args, kwargs)
            async with self.session() as sess:
                result = await sess.execute(text(sql), params)
                value = result.scalar()
            self._log_usage("fetch_value", True)
            return SkillResult.ok(value)
        except Exception as e:
            self._log_usage("fetch_value", False)
            return SkillResult.fail(str(e))

    # ------------------------------------------------------------------
    # Query translation helper
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare_query(query: str, args: tuple, kwargs: dict):
        """Convert ``$1, $2 …`` positional placeholders to ``:p1, :p2 …``.

        If ``kwargs`` are already provided the query is assumed to use
        named params and is returned as-is.
        """
        if kwargs:
            return query, kwargs
        if not args:
            return query, {}
        # Replace $1..$N with :p1..:pN
        import re
        params = {}
        def _replacer(m):
            idx = int(m.group(1))
            key = f"p{idx}"
            if idx <= len(args):
                params[key] = args[idx - 1]
            return f":{key}"
        sql = re.sub(r"\$(\d+)", _replacer, query)
        # Remove ::uuid casts that asyncpg needed
        sql = sql.replace("::uuid", "")
        return sql, params

    # =================================================================
    # Aria-specific ORM helpers
    # =================================================================

    # ── Thoughts ─────────────────────────────────────────────────────

    async def log_thought(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Insert a thought."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    t = Thought(
                        content=content,
                        category=category,
                        metadata_json=metadata or {},
                    )
                    sess.add(t)
                self._log_usage("log_thought", True)
                return SkillResult.ok({"id": str(t.id) if t.id else None})
            except Exception as e:
                self._log_usage("log_thought", False)
                return SkillResult.fail(str(e))
        # Fallback to raw SQL
        return await self.execute(
            "INSERT INTO thoughts (content, category, metadata, created_at) "
            "VALUES (:content, :category, :metadata, NOW())",
            content=content, category=category, metadata=metadata or {},
        )

    async def get_recent_thoughts(self, limit: int = 10) -> SkillResult:
        """Recent thoughts ordered by date."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    stmt = (
                        select(Thought)
                        .order_by(Thought.created_at.desc())
                        .limit(limit)
                    )
                    rows = (await sess.execute(stmt)).scalars().all()
                self._log_usage("get_recent_thoughts", True)
                return SkillResult.ok([r.to_dict() for r in rows])
            except Exception as e:
                self._log_usage("get_recent_thoughts", False)
                return SkillResult.fail(str(e))
        return await self.fetch_all(
            "SELECT id, content, category, created_at "
            "FROM thoughts ORDER BY created_at DESC LIMIT :lim",
            lim=limit,
        )

    # ── Memories ─────────────────────────────────────────────────────

    async def store_memory(
        self,
        key: str,
        value: Any,
        category: str = "general",
    ) -> SkillResult:
        """Upsert a memory."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    stmt = pg_insert(Memory).values(
                        key=key, value=value, category=category,
                        updated_at=datetime.now(timezone.utc),
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["key"],
                        set_={
                            "value": stmt.excluded.value,
                            "category": stmt.excluded.category,
                            "updated_at": stmt.excluded.updated_at,
                        },
                    )
                    await sess.execute(stmt)
                self._log_usage("store_memory", True)
                return SkillResult.ok({"key": key})
            except Exception as e:
                self._log_usage("store_memory", False)
                return SkillResult.fail(str(e))
        return await self.execute(
            "INSERT INTO memories (key, value, category, updated_at) "
            "VALUES (:key, :value, :cat, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET "
            "value=EXCLUDED.value, category=EXCLUDED.category, updated_at=NOW()",
            key=key, value=value, cat=category,
        )

    async def recall_memory(self, key: str) -> SkillResult:
        """Retrieve a memory by key."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    stmt = select(Memory).where(Memory.key == key)
                    row = (await sess.execute(stmt)).scalars().first()
                self._log_usage("recall_memory", True)
                return SkillResult.ok(row.to_dict() if row else None)
            except Exception as e:
                self._log_usage("recall_memory", False)
                return SkillResult.fail(str(e))
        return await self.fetch_one(
            "SELECT value, category, updated_at FROM memories WHERE key = :k",
            k=key,
        )

    async def search_memories(
        self,
        pattern: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> SkillResult:
        """Search memories by key ILIKE."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    stmt = select(Memory).where(
                        Memory.key.ilike(f"%{pattern}%")
                    )
                    if category:
                        stmt = stmt.where(Memory.category == category)
                    stmt = stmt.order_by(Memory.updated_at.desc()).limit(limit)
                    rows = (await sess.execute(stmt)).scalars().all()
                self._log_usage("search_memories", True)
                return SkillResult.ok([r.to_dict() for r in rows])
            except Exception as e:
                self._log_usage("search_memories", False)
                return SkillResult.fail(str(e))
        if category:
            return await self.fetch_all(
                "SELECT key, value, category, updated_at FROM memories "
                "WHERE key ILIKE :pat AND category = :cat "
                "ORDER BY updated_at DESC LIMIT :lim",
                pat=f"%{pattern}%", cat=category, lim=limit,
            )
        return await self.fetch_all(
            "SELECT key, value, category, updated_at FROM memories "
            "WHERE key ILIKE :pat ORDER BY updated_at DESC LIMIT :lim",
            pat=f"%{pattern}%", lim=limit,
        )

    # ── Model Usage ──────────────────────────────────────────────────

    async def log_model_usage(
        self,
        model: str,
        provider: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> SkillResult:
        """Log model usage for cost / performance tracking."""
        if HAS_ORM_MODELS:
            try:
                import uuid
                async with self.session() as sess:
                    row = ModelUsage(
                        model=model, provider=provider,
                        input_tokens=input_tokens, output_tokens=output_tokens,
                        cost_usd=cost_usd, latency_ms=latency_ms,
                        success=success, error_message=error_message,
                        session_id=uuid.UUID(session_id) if session_id else None,
                    )
                    sess.add(row)
                self._log_usage("log_model_usage", True)
                return SkillResult.ok({"id": str(row.id) if row.id else None})
            except Exception as e:
                self._log_usage("log_model_usage", False)
                return SkillResult.fail(str(e))
        return await self.execute(
            "INSERT INTO model_usage "
            "(model, provider, input_tokens, output_tokens, cost_usd, "
            "latency_ms, success, error_message, session_id, created_at) "
            "VALUES (:model, :prov, :inp, :out, :cost, :lat, :ok, :err, :sid, NOW())",
            model=model, prov=provider,
            inp=input_tokens, out=output_tokens, cost=cost_usd,
            lat=latency_ms, ok=success, err=error_message, sid=session_id,
        )

    async def get_model_usage_summary(self, hours: int = 24) -> SkillResult:
        """Aggregated model usage for the last *hours*."""
        return await self.fetch_all(
            "SELECT model, provider, "
            "  COUNT(*) as request_count, "
            "  SUM(input_tokens) as total_input, "
            "  SUM(output_tokens) as total_output, "
            "  SUM(cost_usd) as total_cost, "
            "  AVG(latency_ms)::int as avg_latency "
            "FROM model_usage "
            "WHERE created_at > NOW() - make_interval(hours => :h) "
            "GROUP BY model, provider ORDER BY total_cost DESC",
            h=hours,
        )

    # ── Agent Sessions ───────────────────────────────────────────────

    async def start_agent_session(
        self,
        agent_id: str,
        session_type: str = "interactive",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Start a new agent session."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    row = AgentSession(
                        agent_id=agent_id,
                        session_type=session_type,
                        metadata_json=metadata or {},
                    )
                    sess.add(row)
                    await sess.flush()
                    sid = str(row.id)
                self._log_usage("start_agent_session", True)
                return SkillResult.ok({"id": sid})
            except Exception as e:
                self._log_usage("start_agent_session", False)
                return SkillResult.fail(str(e))
        return await self.fetch_one(
            "INSERT INTO agent_sessions (agent_id, session_type, metadata, started_at) "
            "VALUES (:aid, :stype, :meta, NOW()) RETURNING id",
            aid=agent_id, stype=session_type, meta=metadata or {},
        )

    async def end_agent_session(
        self,
        session_id: str,
        messages_count: int = 0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> SkillResult:
        """Close an agent session."""
        return await self.execute(
            "UPDATE agent_sessions SET ended_at=NOW(), status='completed', "
            "messages_count=:mc, tokens_used=:tu, cost_usd=:cost "
            "WHERE id = :sid",
            sid=session_id, mc=messages_count, tu=tokens_used, cost=cost_usd,
        )

    async def get_active_sessions(self) -> SkillResult:
        """All active agent sessions."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    stmt = (
                        select(AgentSession)
                        .where(AgentSession.status == "active")
                        .order_by(AgentSession.started_at.desc())
                    )
                    rows = (await sess.execute(stmt)).scalars().all()
                self._log_usage("get_active_sessions", True)
                return SkillResult.ok([r.to_dict() for r in rows])
            except Exception as e:
                self._log_usage("get_active_sessions", False)
                return SkillResult.fail(str(e))
        return await self.fetch_all(
            "SELECT id, agent_id, session_type, started_at, "
            "messages_count, tokens_used, cost_usd, metadata "
            "FROM agent_sessions WHERE status='active' ORDER BY started_at DESC",
        )

    # ── Rate Limits ──────────────────────────────────────────────────

    async def update_rate_limit(self, skill: str, action_type: str = "action") -> SkillResult:
        """Upsert rate limit tracking."""
        col = "last_post" if action_type == "post" else "last_action"
        return await self.execute(
            f"INSERT INTO rate_limits (skill, {col}, action_count, window_start, updated_at) "
            f"VALUES (:skill, NOW(), 1, NOW(), NOW()) "
            f"ON CONFLICT (skill) DO UPDATE SET "
            f"{col}=NOW(), action_count=rate_limits.action_count+1, updated_at=NOW()",
            skill=skill,
        )

    async def check_rate_limit(
        self, skill: str, max_actions: int = 100, window_seconds: int = 3600,
    ) -> SkillResult:
        """Check if a skill is within rate limits."""
        result = await self.fetch_one(
            "SELECT skill, action_count, window_start, "
            "EXTRACT(EPOCH FROM (NOW()-window_start)) as window_age "
            "FROM rate_limits WHERE skill = :skill",
            skill=skill,
        )
        if not result.success or result.data is None:
            return SkillResult.ok({"allowed": True, "remaining": max_actions})
        data = result.data
        window_age = data.get("window_age", 0)
        if window_age > window_seconds:
            await self.execute(
                "UPDATE rate_limits SET action_count=0, window_start=NOW() WHERE skill=:skill",
                skill=skill,
            )
            return SkillResult.ok({"allowed": True, "remaining": max_actions})
        count = data.get("action_count", 0)
        remaining = max(0, max_actions - count)
        return SkillResult.ok({
            "allowed": count < max_actions,
            "remaining": remaining,
            "window_age": window_age,
        })

    # ── Security Events ──────────────────────────────────────────────

    async def log_security_event(
        self,
        threat_level: str,
        threat_type: str,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        blocked: bool = False,
    ) -> SkillResult:
        """Record a security event."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    row = SecurityEvent(
                        threat_level=threat_level.upper(),
                        threat_type=threat_type,
                        source=source,
                        details=details or {},
                        blocked=blocked,
                    )
                    sess.add(row)
                self._log_usage("log_security_event", True)
                return SkillResult.ok({"id": str(row.id) if row.id else None})
            except Exception as e:
                self._log_usage("log_security_event", False)
                return SkillResult.fail(str(e))
        return await self.execute(
            "INSERT INTO security_events "
            "(threat_level, threat_type, source, details, blocked, created_at) "
            "VALUES (:tl, :tt, :src, :det, :blk, NOW())",
            tl=threat_level.upper(), tt=threat_type, src=source,
            det=details or {}, blk=blocked,
        )

    # ── API Key Rotations ────────────────────────────────────────────

    async def log_api_key_rotation(
        self,
        service: str,
        reason: Optional[str] = None,
        rotated_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Log an API key rotation."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    row = ApiKeyRotation(
                        service=service, reason=reason,
                        rotated_by=rotated_by, metadata_json=metadata or {},
                    )
                    sess.add(row)
                self._log_usage("log_api_key_rotation", True)
                return SkillResult.ok({"id": str(row.id) if row.id else None})
            except Exception as e:
                self._log_usage("log_api_key_rotation", False)
                return SkillResult.fail(str(e))
        return await self.execute(
            "INSERT INTO api_key_rotations "
            "(service, reason, rotated_by, metadata, rotated_at) "
            "VALUES (:svc, :reason, :by, :meta, NOW())",
            svc=service, reason=reason, by=rotated_by, meta=metadata or {},
        )

    # ── Key-Value Memory ─────────────────────────────────────────────

    async def kv_set(
        self,
        key: str,
        value: Any,
        category: str = "general",
        ttl_seconds: Optional[int] = None,
    ) -> SkillResult:
        """Set a key-value pair with optional TTL."""
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        return await self.execute(
            "INSERT INTO key_value_memory (key, value, category, ttl_seconds, expires_at, updated_at) "
            "VALUES (:k, :v, :cat, :ttl, :exp, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET "
            "value=EXCLUDED.value, category=EXCLUDED.category, "
            "ttl_seconds=EXCLUDED.ttl_seconds, expires_at=EXCLUDED.expires_at, updated_at=NOW()",
            k=key, v=value, cat=category, ttl=ttl_seconds, exp=expires_at,
        )

    async def kv_get(self, key: str) -> SkillResult:
        """Get a KV pair (checks expiry)."""
        return await self.fetch_one(
            "SELECT key, value, category, expires_at FROM key_value_memory "
            "WHERE key=:k AND (expires_at IS NULL OR expires_at > NOW())",
            k=key,
        )

    async def kv_delete(self, key: str) -> SkillResult:
        """Delete a KV pair."""
        return await self.execute(
            "DELETE FROM key_value_memory WHERE key=:k", k=key,
        )

    # ── Knowledge Graph ──────────────────────────────────────────────

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Create a knowledge-graph entity."""
        if HAS_ORM_MODELS:
            try:
                async with self.session() as sess:
                    row = KnowledgeEntity(
                        name=name, type=entity_type,
                        properties=properties or {},
                    )
                    sess.add(row)
                    await sess.flush()
                self._log_usage("create_entity", True)
                return SkillResult.ok({"id": str(row.id)})
            except Exception as e:
                self._log_usage("create_entity", False)
                return SkillResult.fail(str(e))
        return await self.fetch_one(
            "INSERT INTO knowledge_entities (name, type, properties) "
            "VALUES (:name, :etype, :props) RETURNING id",
            name=name, etype=entity_type, props=properties or {},
        )

    async def create_relation(
        self,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Create a knowledge-graph relation."""
        if HAS_ORM_MODELS:
            try:
                import uuid
                async with self.session() as sess:
                    row = KnowledgeRelation(
                        from_entity=uuid.UUID(from_entity_id),
                        to_entity=uuid.UUID(to_entity_id),
                        relation_type=relation_type,
                        properties=properties or {},
                    )
                    sess.add(row)
                self._log_usage("create_relation", True)
                return SkillResult.ok({"id": str(row.id) if row.id else None})
            except Exception as e:
                self._log_usage("create_relation", False)
                return SkillResult.fail(str(e))
        return await self.execute(
            "INSERT INTO knowledge_relations "
            "(from_entity, to_entity, relation_type, properties) "
            "VALUES (:fid, :tid, :rtype, :props)",
            fid=from_entity_id, tid=to_entity_id,
            rtype=relation_type, props=properties or {},
        )

    async def get_entity_relations(
        self, entity_id: str, direction: str = "both",
    ) -> SkillResult:
        """Get all relations for an entity."""
        if direction == "outgoing":
            query = (
                "SELECT r.*, e.name as target_name, e.type as target_type "
                "FROM knowledge_relations r "
                "JOIN knowledge_entities e ON r.to_entity = e.id "
                "WHERE r.from_entity = :eid"
            )
        elif direction == "incoming":
            query = (
                "SELECT r.*, e.name as source_name, e.type as source_type "
                "FROM knowledge_relations r "
                "JOIN knowledge_entities e ON r.from_entity = e.id "
                "WHERE r.to_entity = :eid"
            )
        else:
            query = (
                "SELECT r.*, "
                "  e1.name as from_name, e1.type as from_type, "
                "  e2.name as to_name, e2.type as to_type "
                "FROM knowledge_relations r "
                "JOIN knowledge_entities e1 ON r.from_entity = e1.id "
                "JOIN knowledge_entities e2 ON r.to_entity = e2.id "
                "WHERE r.from_entity = :eid OR r.to_entity = :eid"
            )
        return await self.fetch_all(query, eid=entity_id)
