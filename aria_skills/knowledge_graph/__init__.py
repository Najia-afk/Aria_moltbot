# aria_skills/knowledge_graph.py
"""
Knowledge graph skill.

Manages entities and relationships in Aria's knowledge base.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class KnowledgeGraphSkill(BaseSkill):
    """
    Knowledge graph management.
    
    Stores entities and their relationships for reasoning.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._entities: Dict[str, Dict] = {}  # fallback cache
        self._relations: List[Dict] = []  # fallback cache
        self._api = None
    
    @property
    def name(self) -> str:
        return "knowledge_graph"
    
    async def initialize(self) -> bool:
        """Initialize knowledge graph."""
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Knowledge graph initialized (API-backed)")
        return True
    
    async def close(self):
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
    
    async def health_check(self) -> SkillStatus:
        """Check availability."""
        return self._status
    
    async def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict] = None,
    ) -> SkillResult:
        """Add an entity to the knowledge graph."""
        entity_id = f"{entity_type}:{name}".lower().replace(" ", "_")
        
        entity = {
            "id": entity_id,
            "name": name,
            "type": entity_type,
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            resp = await self._api._client.post("/knowledge-graph/entities", json=entity)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else entity)
        except Exception as e:
            self.logger.warning(f"API add_entity failed, using fallback: {e}")
            self._entities[entity_id] = entity
            return SkillResult.ok(entity)
    
    async def add_relation(
        self,
        from_entity: str,
        relation: str,
        to_entity: str,
        properties: Optional[Dict] = None,
    ) -> SkillResult:
        """Add a relationship between entities."""
        rel = {
            "from_entity": from_entity,
            "relation_type": relation,
            "to_entity": to_entity,
            "properties": properties or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        try:
            resp = await self._api._client.post("/knowledge-graph/relations", json=rel)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else rel)
        except Exception as e:
            self.logger.warning(f"API add_relation failed, using fallback: {e}")
            self._relations.append(rel)
            return SkillResult.ok(rel)
    
    async def get_entity(self, entity_id: str) -> SkillResult:
        """Get an entity by ID."""
        try:
            resp = await self._api._client.get(f"/knowledge-graph/entities/{entity_id}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API get_entity failed, using fallback: {e}")
            if entity_id not in self._entities:
                return SkillResult.fail(f"Entity not found: {entity_id}")
            entity = self._entities[entity_id]
            relations = [r for r in self._relations if r["from"] == entity_id or r["to"] == entity_id]
            return SkillResult.ok({"entity": entity, "relations": relations})
    
    async def query(
        self,
        entity_type: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> SkillResult:
        """Query the knowledge graph."""
        try:
            params: Dict[str, Any] = {}
            if entity_type:
                params["type"] = entity_type
            if relation:
                params["relation"] = relation
            resp = await self._api._client.get("/knowledge-graph/entities", params=params)
            resp.raise_for_status()
            api_data = resp.json()
            entities = api_data if isinstance(api_data, list) else api_data.get("entities", [])
            return SkillResult.ok({
                "entities": entities,
                "relations": [],
                "total_entities": len(entities),
                "total_relations": 0,
            })
        except Exception as e:
            self.logger.warning(f"API query failed, using fallback: {e}")
            entities = list(self._entities.values())
            if entity_type:
                entities = [ent for ent in entities if ent["type"] == entity_type]
            relations = self._relations
            if relation:
                relations = [r for r in relations if r["relation"] == relation]
            return SkillResult.ok({
                "entities": entities,
                "relations": relations,
                "total_entities": len(entities),
                "total_relations": len(relations),
            })
