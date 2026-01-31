# aria_skills/database.py
"""
PostgreSQL database skill.

Handles all database operations with connection pooling and safe queries.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
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
