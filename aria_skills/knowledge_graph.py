# aria_skills/knowledge_graph.py
"""
Knowledge graph skill.

Stores entities and relationships in PostgreSQL for graph-style queries.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False


@SkillRegistry.register
class KnowledgeGraphSkill(BaseSkill):
    """
    Knowledge graph skill.

    Config:
        dsn: Connection string or use env:VAR_NAME
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._pool: Optional["asyncpg.Pool"] = None
        self._dsn: Optional[str] = None

    @property
    def name(self) -> str:
        return "knowledge_graph"

    async def initialize(self) -> bool:
        if not HAS_ASYNCPG:
            self.logger.error("asyncpg not installed")
            self._status = SkillStatus.UNAVAILABLE
            return False

        self._dsn = self._get_env_value("dsn") or self._get_env_value("database_url")
        if not self._dsn:
            self.logger.error("No DSN configured")
            self._status = SkillStatus.UNAVAILABLE
            return False

        try:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)
            await self._ensure_schema()
            self._status = SkillStatus.AVAILABLE
            return True
        except Exception as e:
            self.logger.error(f"Knowledge graph init failed: {e}")
            self._status = SkillStatus.ERROR
            return False

    async def health_check(self) -> SkillStatus:
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
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._status = SkillStatus.UNAVAILABLE

    async def _ensure_schema(self) -> None:
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_entities (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    properties JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(name, type)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_relations (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    from_entity UUID NOT NULL REFERENCES knowledge_entities(id) ON DELETE CASCADE,
                    to_entity UUID NOT NULL REFERENCES knowledge_entities(id) ON DELETE CASCADE,
                    relation_type TEXT NOT NULL,
                    properties JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(from_entity, to_entity, relation_type)
                )
                """
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_entity_name ON knowledge_entities(name)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_relation_from ON knowledge_relations(from_entity)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_kg_relation_to ON knowledge_relations(to_entity)"
            )

    async def add_entity(self, name: str, type: str, properties: Optional[Dict[str, Any]] = None) -> SkillResult:
        if not self.is_available:
            return SkillResult.fail("Knowledge graph not available")
        props = properties or {}
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO knowledge_entities (name, type, properties)
                    VALUES ($1, $2, $3::jsonb)
                    ON CONFLICT (name, type)
                    DO UPDATE SET properties = EXCLUDED.properties, updated_at = NOW()
                    RETURNING id, name, type, properties
                    """,
                    name,
                    type,
                    props,
                )
            self._log_usage("add_entity", True)
            return SkillResult.ok(dict(row))
        except Exception as e:
            self._log_usage("add_entity", False)
            return SkillResult.fail(str(e))

    async def add_relation(
        self,
        from_entity: str,
        to_entity: str,
        relation_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> SkillResult:
        if not self.is_available:
            return SkillResult.fail("Knowledge graph not available")

        props = properties or {}
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    WITH fe AS (
                        SELECT id FROM knowledge_entities WHERE name = $1
                    ), te AS (
                        SELECT id FROM knowledge_entities WHERE name = $2
                    )
                    INSERT INTO knowledge_relations (from_entity, to_entity, relation_type, properties)
                    SELECT fe.id, te.id, $3, $4::jsonb FROM fe, te
                    ON CONFLICT (from_entity, to_entity, relation_type)
                    DO UPDATE SET properties = EXCLUDED.properties
                    RETURNING id
                    """,
                    from_entity,
                    to_entity,
                    relation_type,
                    props,
                )
            if not row:
                return SkillResult.fail("Entities not found")
            self._log_usage("add_relation", True)
            return SkillResult.ok({"id": str(row[0])})
        except Exception as e:
            self._log_usage("add_relation", False)
            return SkillResult.fail(str(e))

    async def query_related(self, entity_name: str, depth: int = 1) -> SkillResult:
        if not self.is_available:
            return SkillResult.fail("Knowledge graph not available")
        if depth < 1:
            depth = 1
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT e2.name, e2.type, r.relation_type, r.properties
                    FROM knowledge_entities e1
                    JOIN knowledge_relations r ON r.from_entity = e1.id
                    JOIN knowledge_entities e2 ON e2.id = r.to_entity
                    WHERE e1.name = $1
                    """,
                    entity_name,
                )
            self._log_usage("query_related", True)
            return SkillResult.ok([dict(row) for row in rows])
        except Exception as e:
            self._log_usage("query_related", False)
            return SkillResult.fail(str(e))

    async def search(self, query: str) -> SkillResult:
        if not self.is_available:
            return SkillResult.fail("Knowledge graph not available")
        like = f"%{query}%"
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, name, type, properties
                    FROM knowledge_entities
                    WHERE name ILIKE $1 OR type ILIKE $1 OR properties::text ILIKE $1
                    ORDER BY name ASC
                    LIMIT 50
                    """,
                    like,
                )
            self._log_usage("search", True)
            return SkillResult.ok([dict(row) for row in rows])
        except Exception as e:
            self._log_usage("search", False)
            return SkillResult.fail(str(e))
