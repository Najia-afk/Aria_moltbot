# S4-02: Implement Graph Pathfinding API
**Epic:** E8 — Knowledge Graph | **Priority:** P0 | **Points:** 5 | **Phase:** 3

## Problem
Aria needs to traverse the knowledge graph to find which skill can solve a given task. Currently she reads TOOLS.md (~2000 tokens). With a structured graph, she could do pathfinding queries like:
- "What skills handle data analysis?" → traverse focus:data → skills with affinity
- "What tool can send a Telegram message?" → traverse tool entities → owning skill
- "What depends on api_client?" → traverse depends_on relations

## Root Cause
No graph traversal/query endpoint exists. The knowledge graph is stored but not queryable by relationship path.

## Fix

### File: `src/api/routers/knowledge.py`
Add pathfinding endpoints:

```python
@router.get("/knowledge-graph/traverse")
async def traverse_graph(
    start_name: str,
    relation_type: Optional[str] = None,
    max_depth: int = 3,
    direction: str = "outgoing",  # outgoing, incoming, both
    db: AsyncSession = Depends(get_db),
):
    """BFS traversal from a starting entity, following relations."""
    # Find start entity
    start = await db.execute(
        select(KnowledgeEntity).where(KnowledgeEntity.name == start_name)
    )
    start_entity = start.scalar_one_or_none()
    if not start_entity:
        raise HTTPException(404, f"Entity '{start_name}' not found")
    
    # BFS traversal
    visited = {str(start_entity.id)}
    queue = [(start_entity, 0)]
    result_nodes = [start_entity.to_dict()]
    result_edges = []
    
    while queue:
        current, depth = queue.pop(0)
        if depth >= max_depth:
            continue
        
        # Get relations
        if direction in ("outgoing", "both"):
            rels = await db.execute(
                select(KnowledgeRelation, KnowledgeEntity)
                .join(KnowledgeEntity, KnowledgeRelation.to_entity == KnowledgeEntity.id)
                .where(KnowledgeRelation.from_entity == current.id)
                .where(KnowledgeRelation.relation_type == relation_type if relation_type else True)
            )
            for rel, target in rels.all():
                result_edges.append({**rel.to_dict(), "direction": "outgoing"})
                if str(target.id) not in visited:
                    visited.add(str(target.id))
                    result_nodes.append(target.to_dict())
                    queue.append((target, depth + 1))
        
        if direction in ("incoming", "both"):
            rels = await db.execute(
                select(KnowledgeRelation, KnowledgeEntity)
                .join(KnowledgeEntity, KnowledgeRelation.from_entity == KnowledgeEntity.id)
                .where(KnowledgeRelation.to_entity == current.id)
                .where(KnowledgeRelation.relation_type == relation_type if relation_type else True)
            )
            for rel, source in rels.all():
                result_edges.append({**rel.to_dict(), "direction": "incoming"})
                if str(source.id) not in visited:
                    visited.add(str(source.id))
                    result_nodes.append(source.to_dict())
                    queue.append((source, depth + 1))
    
    return {
        "start": start_name,
        "nodes": result_nodes,
        "edges": result_edges,
        "node_count": len(result_nodes),
        "edge_count": len(result_edges),
    }


@router.get("/knowledge-graph/search")
async def search_graph(
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Search entities by name (ILIKE) with optional type filter."""
    stmt = select(KnowledgeEntity).where(
        KnowledgeEntity.name.ilike(f"%{query}%")
    )
    if entity_type:
        stmt = stmt.where(KnowledgeEntity.type == entity_type)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    entities = result.scalars().all()
    return {"entities": [e.to_dict() for e in entities], "count": len(entities)}


@router.get("/knowledge-graph/skill-for-task")
async def skill_for_task(
    task: str,
    db: AsyncSession = Depends(get_db),
):
    """Find the best skill for a given task description.
    
    Searches tool descriptions, skill descriptions, and focus mode affinities.
    Returns a ranked list of candidate skills.
    """
    # Search tools by description
    tool_matches = await db.execute(
        select(KnowledgeEntity).where(
            KnowledgeEntity.type == "tool",
            KnowledgeEntity.properties["description"].astext.ilike(f"%{task}%")
        ).limit(5)
    )
    
    # Search skills by description
    skill_matches = await db.execute(
        select(KnowledgeEntity).where(
            KnowledgeEntity.type == "skill",
            KnowledgeEntity.properties["description"].astext.ilike(f"%{task}%")
        ).limit(5)
    )
    
    candidates = []
    for entity in tool_matches.scalars():
        skill_name = entity.properties.get("skill", "unknown")
        candidates.append({
            "skill": skill_name,
            "matched_tool": entity.name,
            "match_type": "tool_description",
            "description": entity.properties.get("description", ""),
        })
    
    for entity in skill_matches.scalars():
        candidates.append({
            "skill": entity.name,
            "match_type": "skill_description",
            "description": entity.properties.get("description", ""),
            "layer": entity.properties.get("layer", 3),
        })
    
    return {"task": task, "candidates": candidates, "count": len(candidates)}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | API layer (correct) |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test locally |
| 5 | aria_memories | ❌ | DB reads |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S4-01** should complete first (graph populated with skill data).

## Verification
```bash
# 1. Traverse from api_client:
curl -s 'http://localhost:8000/api/knowledge-graph/traverse?start_name=api_client&relation_type=depends_on&direction=incoming' | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Skills depending on api_client: {d[\"node_count\"]}')"
# EXPECTED: 10+ nodes

# 2. Search for skills:
curl -s 'http://localhost:8000/api/knowledge-graph/search?query=social&entity_type=skill'
# EXPECTED: skills matching "social"

# 3. Find skill for task:
curl -s 'http://localhost:8000/api/knowledge-graph/skill-for-task?task=send+telegram+message'
# EXPECTED: telegram skill in candidates
```

## Prompt for Agent
```
Create graph traversal and search endpoints for the Aria knowledge graph.

FILES TO READ FIRST:
- src/api/routers/knowledge.py (existing endpoints)
- src/api/db/models.py (KnowledgeEntity, KnowledgeRelation)

STEPS:
1. Add /knowledge-graph/traverse (BFS with depth limit)
2. Add /knowledge-graph/search (ILIKE text search)
3. Add /knowledge-graph/skill-for-task (semantic skill discovery)
4. Run verification

CONSTRAINTS: API layer. No external dependencies (no embedding models). ILIKE search is good enough.
```
