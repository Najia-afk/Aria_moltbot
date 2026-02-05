# aria_skills/database.py
"""
PostgreSQL database skill.

Handles all database operations with connection pooling and safe queries.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


@SkillRegistry.register
class DatabaseSkill(BaseSkill):
    """
    PostgreSQL database skill with connection pooling.
    
    Config:
        dsn: Connection string or use env:VAR_NAME
        pool_size:
            min: Minimum pool connections (default: 2)
            max: Maximum pool connections (default: 10)
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._pool: Optional["asyncpg.Pool"] = None
        self._dsn: Optional[str] = None
    
    @property
    def name(self) -> str:
        return "database"
    
    async def initialize(self) -> bool:
        """Initialize connection pool."""
        if not HAS_ASYNCPG:
            self.logger.error("asyncpg not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        self._dsn = self._get_env_value("dsn")
        
        if not self._dsn:
            self.logger.error("No DSN configured")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        pool_config = self.config.config.get("pool_size", {})
        min_size = pool_config.get("min", 2)
        max_size = pool_config.get("max", 10)
        
        try:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=min_size,
                max_size=max_size,
                command_timeout=60,
            )
            self._status = SkillStatus.AVAILABLE
            self.logger.info("Database pool initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"Pool creation failed: {e}")
            self._status = SkillStatus.ERROR
            return False
    
    async def health_check(self) -> SkillStatus:
        """Check database connectivity."""
        if not self._pool:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            self._status = SkillStatus.AVAILABLE
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._status = SkillStatus.UNAVAILABLE
            self.logger.info("Database pool closed")
    
    @asynccontextmanager
    async def connection(self) -> AsyncGenerator["asyncpg.Connection", None]:
        """Get a connection from the pool."""
        if not self._pool:
            raise RuntimeError("Database not initialized")
        
        async with self._pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args) -> SkillResult:
        """
        Execute a query without returning results.
        
        Args:
            query: SQL query with $1, $2, etc. placeholders
            *args: Query parameters
            
        Returns:
            SkillResult with affected row count
        """
        if not self.is_available:
            return SkillResult.fail("Database not available")
        
        try:
            async with self.connection() as conn:
                result = await conn.execute(query, *args)
                self._log_usage("execute", True)
                
                # Parse "DELETE 5" -> 5
                affected = result.split()[-1] if result else "0"
                return SkillResult.ok({"affected_rows": int(affected)})
                
        except Exception as e:
            self._log_usage("execute", False)
            return SkillResult.fail(str(e))
    
    async def fetch_one(self, query: str, *args) -> SkillResult:
        """
        Fetch a single row.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            SkillResult with row data or None
        """
        if not self.is_available:
            return SkillResult.fail("Database not available")
        
        try:
            async with self.connection() as conn:
                row = await conn.fetchrow(query, *args)
                self._log_usage("fetch_one", True)
                
                if row:
                    return SkillResult.ok(dict(row))
                return SkillResult.ok(None)
                
        except Exception as e:
            self._log_usage("fetch_one", False)
            return SkillResult.fail(str(e))
    
    async def fetch_all(self, query: str, *args) -> SkillResult:
        """
        Fetch all matching rows.
        
        Args:
            query: SQL query
            *args: Query parameters
            
        Returns:
            SkillResult with list of rows
        """
        if not self.is_available:
            return SkillResult.fail("Database not available")
        
        try:
            async with self.connection() as conn:
                rows = await conn.fetch(query, *args)
                self._log_usage("fetch_all", True)
                
                return SkillResult.ok([dict(row) for row in rows])
                
        except Exception as e:
            self._log_usage("fetch_all", False)
            return SkillResult.fail(str(e))
    
    async def fetch_value(self, query: str, *args) -> SkillResult:
        """
        Fetch a single value.
        
        Args:
            query: SQL query returning single column
            *args: Query parameters
            
        Returns:
            SkillResult with the value
        """
        if not self.is_available:
            return SkillResult.fail("Database not available")
        
        try:
            async with self.connection() as conn:
                value = await conn.fetchval(query, *args)
                self._log_usage("fetch_value", True)
                
                return SkillResult.ok(value)
                
        except Exception as e:
            self._log_usage("fetch_value", False)
            return SkillResult.fail(str(e))
    
    # -------------------------------------------------------------------------
    # Aria-specific helpers
    # -------------------------------------------------------------------------
    
    async def log_thought(
        self,
        content: str,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Log a thought to the thoughts table."""
        return await self.execute(
            """
            INSERT INTO thoughts (content, category, metadata, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            content,
            category,
            metadata or {},
            datetime.utcnow(),
        )
    
    async def get_recent_thoughts(self, limit: int = 10) -> SkillResult:
        """Get recent thoughts."""
        return await self.fetch_all(
            """
            SELECT id, content, category, created_at 
            FROM thoughts 
            ORDER BY created_at DESC 
            LIMIT $1
            """,
            limit,
        )
    
    async def store_memory(
        self,
        key: str,
        value: Any,
        category: str = "general",
    ) -> SkillResult:
        """Store a key-value memory with upsert."""
        return await self.execute(
            """
            INSERT INTO memories (key, value, category, updated_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                category = EXCLUDED.category,
                updated_at = EXCLUDED.updated_at
            """,
            key,
            value,
            category,
            datetime.utcnow(),
        )
    
    async def recall_memory(self, key: str) -> SkillResult:
        """Retrieve a memory by key."""
        result = await self.fetch_one(
            "SELECT value, category, updated_at FROM memories WHERE key = $1",
            key,
        )
        return result
    
    async def search_memories(
        self,
        pattern: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> SkillResult:
        """Search memories by key pattern."""
        if category:
            return await self.fetch_all(
                """
                SELECT key, value, category, updated_at 
                FROM memories 
                WHERE key ILIKE $1 AND category = $2
                ORDER BY updated_at DESC 
                LIMIT $3
                """,
                f"%{pattern}%",
                category,
                limit,
            )
        else:
            return await self.fetch_all(
                """
                SELECT key, value, category, updated_at 
                FROM memories 
                WHERE key ILIKE $1
                ORDER BY updated_at DESC 
                LIMIT $2
                """,
                f"%{pattern}%",
                limit,
            )

    # -------------------------------------------------------------------------
    # Operations tracking helpers
    # -------------------------------------------------------------------------

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
        """Log model usage for cost and performance tracking."""
        return await self.execute(
            """
            INSERT INTO model_usage 
            (model, provider, input_tokens, output_tokens, cost_usd, 
             latency_ms, success, error_message, session_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::uuid, NOW())
            """,
            model,
            provider,
            input_tokens,
            output_tokens,
            cost_usd,
            latency_ms,
            success,
            error_message,
            session_id,
        )

    async def get_model_usage_summary(self, hours: int = 24) -> SkillResult:
        """Get model usage summary for the last N hours."""
        return await self.fetch_all(
            """
            SELECT model, provider,
                   COUNT(*) as request_count,
                   SUM(input_tokens) as total_input,
                   SUM(output_tokens) as total_output,
                   SUM(cost_usd) as total_cost,
                   AVG(latency_ms)::int as avg_latency
            FROM model_usage
            WHERE created_at > NOW() - make_interval(hours => $1)
            GROUP BY model, provider
            ORDER BY total_cost DESC
            """,
            hours,
        )

    async def start_agent_session(
        self,
        agent_id: str,
        session_type: str = "interactive",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Start a new agent session and return its ID."""
        result = await self.fetch_one(
            """
            INSERT INTO agent_sessions (agent_id, session_type, metadata, started_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id
            """,
            agent_id,
            session_type,
            metadata or {},
        )
        return result

    async def end_agent_session(
        self,
        session_id: str,
        messages_count: int = 0,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
    ) -> SkillResult:
        """End an agent session with final stats."""
        return await self.execute(
            """
            UPDATE agent_sessions
            SET ended_at = NOW(),
                status = 'completed',
                messages_count = $2,
                tokens_used = $3,
                cost_usd = $4
            WHERE id = $1::uuid
            """,
            session_id,
            messages_count,
            tokens_used,
            cost_usd,
        )

    async def get_active_sessions(self) -> SkillResult:
        """Get all active agent sessions."""
        return await self.fetch_all(
            """
            SELECT id, agent_id, session_type, started_at, 
                   messages_count, tokens_used, cost_usd, metadata
            FROM agent_sessions
            WHERE status = 'active'
            ORDER BY started_at DESC
            """
        )

    async def update_rate_limit(
        self,
        skill: str,
        action_type: str = "action",
    ) -> SkillResult:
        """Update rate limit tracking for a skill."""
        if action_type == "post":
            return await self.execute(
                """
                INSERT INTO rate_limits (skill, last_post, action_count, window_start, updated_at)
                VALUES ($1, NOW(), 1, NOW(), NOW())
                ON CONFLICT (skill) DO UPDATE SET
                    last_post = NOW(),
                    action_count = rate_limits.action_count + 1,
                    updated_at = NOW()
                """,
                skill,
            )
        else:
            return await self.execute(
                """
                INSERT INTO rate_limits (skill, last_action, action_count, window_start, updated_at)
                VALUES ($1, NOW(), 1, NOW(), NOW())
                ON CONFLICT (skill) DO UPDATE SET
                    last_action = NOW(),
                    action_count = rate_limits.action_count + 1,
                    updated_at = NOW()
                """,
                skill,
            )

    async def check_rate_limit(
        self,
        skill: str,
        max_actions: int = 100,
        window_seconds: int = 3600,
    ) -> SkillResult:
        """Check if a skill is within rate limits."""
        result = await self.fetch_one(
            """
            SELECT skill, action_count, window_start,
                   EXTRACT(EPOCH FROM (NOW() - window_start)) as window_age
            FROM rate_limits
            WHERE skill = $1
            """,
            skill,
        )
        if not result.success or result.data is None:
            return SkillResult.ok({"allowed": True, "remaining": max_actions})
        
        data = result.data
        window_age = data.get("window_age", 0)
        
        # Reset window if expired
        if window_age > window_seconds:
            await self.execute(
                "UPDATE rate_limits SET action_count = 0, window_start = NOW() WHERE skill = $1",
                skill,
            )
            return SkillResult.ok({"allowed": True, "remaining": max_actions})
        
        count = data.get("action_count", 0)
        remaining = max(0, max_actions - count)
        return SkillResult.ok({
            "allowed": count < max_actions,
            "remaining": remaining,
            "window_age": window_age,
        })

    async def log_security_event(
        self,
        threat_level: str,
        threat_type: str,
        source: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        blocked: bool = False,
    ) -> SkillResult:
        """Log a security event."""
        return await self.execute(
            """
            INSERT INTO security_events 
            (threat_level, threat_type, source, details, blocked, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            """,
            threat_level.upper(),
            threat_type,
            source,
            details or {},
            blocked,
        )

    async def log_api_key_rotation(
        self,
        service: str,
        reason: Optional[str] = None,
        rotated_by: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Log an API key rotation event."""
        return await self.execute(
            """
            INSERT INTO api_key_rotations (service, reason, rotated_by, metadata, rotated_at)
            VALUES ($1, $2, $3, $4, NOW())
            """,
            service,
            reason,
            rotated_by,
            metadata or {},
        )

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
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        
        return await self.execute(
            """
            INSERT INTO key_value_memory (key, value, category, ttl_seconds, expires_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                category = EXCLUDED.category,
                ttl_seconds = EXCLUDED.ttl_seconds,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            """,
            key,
            value,
            category,
            ttl_seconds,
            expires_at,
        )

    async def kv_get(self, key: str) -> SkillResult:
        """Get a key-value pair (checks expiry)."""
        result = await self.fetch_one(
            """
            SELECT key, value, category, expires_at
            FROM key_value_memory
            WHERE key = $1 AND (expires_at IS NULL OR expires_at > NOW())
            """,
            key,
        )
        return result

    async def kv_delete(self, key: str) -> SkillResult:
        """Delete a key-value pair."""
        return await self.execute(
            "DELETE FROM key_value_memory WHERE key = $1",
            key,
        )

    # -------------------------------------------------------------------------
    # Knowledge graph helpers
    # -------------------------------------------------------------------------

    async def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Create a knowledge graph entity."""
        return await self.fetch_one(
            """
            INSERT INTO knowledge_entities (name, entity_type, properties)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            name,
            entity_type,
            properties or {},
        )

    async def create_relation(
        self,
        from_entity_id: str,
        to_entity_id: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        """Create a knowledge graph relation."""
        return await self.execute(
            """
            INSERT INTO knowledge_relations 
            (from_entity_id, to_entity_id, relation_type, properties)
            VALUES ($1::uuid, $2::uuid, $3, $4)
            """,
            from_entity_id,
            to_entity_id,
            relation_type,
            properties or {},
        )

    async def get_entity_relations(
        self,
        entity_id: str,
        direction: str = "both",
    ) -> SkillResult:
        """Get all relations for an entity."""
        if direction == "outgoing":
            query = """
                SELECT r.*, e.name as target_name, e.entity_type as target_type
                FROM knowledge_relations r
                JOIN knowledge_entities e ON r.to_entity_id = e.id
                WHERE r.from_entity_id = $1::uuid
            """
        elif direction == "incoming":
            query = """
                SELECT r.*, e.name as source_name, e.entity_type as source_type
                FROM knowledge_relations r
                JOIN knowledge_entities e ON r.from_entity_id = e.id
                WHERE r.to_entity_id = $1::uuid
            """
        else:
            query = """
                SELECT r.*, 
                       e1.name as from_name, e1.entity_type as from_type,
                       e2.name as to_name, e2.entity_type as to_type
                FROM knowledge_relations r
                JOIN knowledge_entities e1 ON r.from_entity_id = e1.id
                JOIN knowledge_entities e2 ON r.to_entity_id = e2.id
                WHERE r.from_entity_id = $1::uuid OR r.to_entity_id = $1::uuid
            """
        return await self.fetch_all(query, entity_id)
