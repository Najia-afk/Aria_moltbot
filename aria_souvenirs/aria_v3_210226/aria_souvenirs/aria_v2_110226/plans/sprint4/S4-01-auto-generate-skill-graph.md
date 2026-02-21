# S4-01: Auto-Generate Skill/Focus Knowledge Graph
**Epic:** E8 — Knowledge Graph | **Priority:** P0 | **Points:** 5 | **Phase:** 3

## Problem
Aria has 26 skills across 8 categories with complex interdependencies, focus affinities, and layering. This information is scattered across:
- `aria_skills/*/skill.json` files (26 files)
- `aria_skills/catalog.py` (generates flat list)
- `aria_mind/TOOLS.md` (manual documentation)
- `aria_mind/SKILLS.md` (detailed reference)

When Aria needs to decide which skill to use for a task, she currently reads the full TOOLS.md (~2000 tokens) or calls get_knowledge_graph() which returns unrelated entities. There's no structured graph connecting skills → capabilities → focus modes → tools.

## Root Cause
No automated pipeline exists to:
1. Read all skill.json files
2. Create KnowledgeEntity records for each skill, tool, focus mode, and category
3. Create KnowledgeRelation records for dependencies, affinities, and tool ownership
4. Keep the graph in sync when skills change

## Fix

### Create graph generator script
**File: `scripts/generate_skill_graph.py`** (NEW)

```python
"""Auto-generate skill knowledge graph from skill.json files.

Run: python scripts/generate_skill_graph.py
Populates knowledge_entities and knowledge_relations tables via API.
"""
import json
import asyncio
import httpx
from pathlib import Path

API_URL = "http://localhost:8000/api"

async def generate():
    async with httpx.AsyncClient(base_url=API_URL, timeout=30) as client:
        skills_dir = Path("aria_skills")
        
        # Phase 1: Create entities
        entities = {}  # name -> id
        
        # Create focus mode entities
        focus_modes = ["orchestrator", "devsecops", "data", "trader", "creative", "social", "journalist"]
        for fm in focus_modes:
            resp = await client.post("/knowledge-graph/entities", json={
                "name": fm, "type": "focus_mode",
                "properties": {"description": f"Aria's {fm} focus mode", "auto_generated": True}
            })
            entities[f"focus:{fm}"] = resp.json()["id"]
        
        # Create category entities
        categories = set()
        
        # Read all skill.json files
        for skill_dir in sorted(skills_dir.iterdir()):
            sj_path = skill_dir / "skill.json"
            if not sj_path.is_file():
                continue
            
            with open(sj_path) as f:
                sj = json.load(f)
            
            skill_name = sj.get("name", skill_dir.name)
            category = sj.get("category", "unknown")
            
            # Create category entity if new
            if category not in categories:
                categories.add(category)
                resp = await client.post("/knowledge-graph/entities", json={
                    "name": category, "type": "category",
                    "properties": {"auto_generated": True}
                })
                entities[f"cat:{category}"] = resp.json()["id"]
            
            # Create skill entity
            resp = await client.post("/knowledge-graph/entities", json={
                "name": skill_name, "type": "skill",
                "properties": {
                    "layer": sj.get("layer", 3),
                    "category": category,
                    "description": sj.get("description", ""),
                    "canonical": sj.get("canonical", f"aria-{skill_name}"),
                    "version": sj.get("version", "1.0.0"),
                    "auto_generated": True,
                }
            })
            skill_id = resp.json()["id"]
            entities[f"skill:{skill_name}"] = skill_id
            
            # Create tool entities
            for tool in sj.get("tools", []):
                tool_name = tool["name"]
                resp = await client.post("/knowledge-graph/entities", json={
                    "name": tool_name, "type": "tool",
                    "properties": {
                        "description": tool.get("description", ""),
                        "skill": skill_name,
                        "auto_generated": True,
                    }
                })
                entities[f"tool:{skill_name}:{tool_name}"] = resp.json()["id"]
        
        # Phase 2: Create relations
        for skill_dir in sorted(skills_dir.iterdir()):
            sj_path = skill_dir / "skill.json"
            if not sj_path.is_file():
                continue
            with open(sj_path) as f:
                sj = json.load(f)
            
            skill_name = sj.get("name", skill_dir.name)
            skill_key = f"skill:{skill_name}"
            if skill_key not in entities:
                continue
            
            # Skill → Category
            cat_key = f"cat:{sj.get('category', 'unknown')}"
            if cat_key in entities:
                await client.post("/knowledge-graph/relations", json={
                    "from_entity": entities[skill_key],
                    "to_entity": entities[cat_key],
                    "relation_type": "belongs_to",
                    "properties": {"auto_generated": True}
                })
            
            # Skill → Focus Modes
            for fm in sj.get("focus_affinity", []):
                fm_key = f"focus:{fm}"
                if fm_key in entities:
                    await client.post("/knowledge-graph/relations", json={
                        "from_entity": entities[skill_key],
                        "to_entity": entities[fm_key],
                        "relation_type": "affinity",
                        "properties": {"auto_generated": True}
                    })
            
            # Skill → Dependencies
            for dep in sj.get("dependencies", []):
                dep_key = f"skill:{dep}"
                if dep_key in entities:
                    await client.post("/knowledge-graph/relations", json={
                        "from_entity": entities[skill_key],
                        "to_entity": entities[dep_key],
                        "relation_type": "depends_on",
                        "properties": {"auto_generated": True}
                    })
            
            # Skill → Tools
            for tool in sj.get("tools", []):
                tool_key = f"tool:{skill_name}:{tool['name']}"
                if tool_key in entities:
                    await client.post("/knowledge-graph/relations", json={
                        "from_entity": entities[skill_key],
                        "to_entity": entities[tool_key],
                        "relation_type": "provides",
                        "properties": {"auto_generated": True}
                    })
        
        print(f"Generated {len(entities)} entities and relations")

if __name__ == "__main__":
    asyncio.run(generate())
```

### Add idempotency — clear old auto-generated entities first
**File: `src/api/routers/knowledge.py`**
Add endpoint to clear auto-generated entities:

```python
@router.delete("/knowledge-graph/auto-generated")
async def clear_auto_generated(db: AsyncSession = Depends(get_db)):
    """Clear all auto-generated knowledge graph entities and relations."""
    from sqlalchemy import and_
    # Delete relations with auto_generated property
    await db.execute(
        delete(KnowledgeRelation).where(
            KnowledgeRelation.properties["auto_generated"].as_boolean() == True
        )
    )
    await db.execute(
        delete(KnowledgeEntity).where(
            KnowledgeEntity.properties["auto_generated"].as_boolean() == True
        )
    )
    await db.commit()
    return {"cleared": True}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Script uses API, not direct DB |
| 2 | .env secrets | ❌ | No secrets (uses localhost API) |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Run in Docker |
| 5 | aria_memories | ❌ | Writes to DB via API |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
None — uses existing knowledge graph endpoints.

## Verification
```bash
# 1. Script exists:
ls scripts/generate_skill_graph.py
# EXPECTED: exists

# 2. Run generator:
python scripts/generate_skill_graph.py
# EXPECTED: "Generated N entities and relations"

# 3. Verify entities created:
curl -s http://localhost:8000/api/knowledge-graph/entities?type=skill | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Skills: {len(d.get(\"entities\",[]))}')
"
# EXPECTED: Skills: 26

# 4. Verify relations created:
curl -s http://localhost:8000/api/knowledge-graph | python3 -c "
import sys,json; d=json.load(sys.stdin); print(f'Entities: {d[\"stats\"][\"entity_count\"]}, Relations: {d[\"stats\"][\"relation_count\"]}')
"
# EXPECTED: Entities: 60+, Relations: 80+

# 5. Idempotent — run again:
python scripts/generate_skill_graph.py
# EXPECTED: Same counts (cleared and regenerated)
```

## Prompt for Agent
```
Create a script that auto-generates a skill knowledge graph from skill.json files.

FILES TO READ FIRST:
- aria_skills/*/skill.json (all skill definitions)
- src/api/routers/knowledge.py (existing endpoints)
- aria_skills/catalog.py (reference for reading skill.json)

STEPS:
1. Create scripts/generate_skill_graph.py
2. Read all skill.json files → create entities (skills, tools, focus modes, categories)
3. Create relations (belongs_to, affinity, depends_on, provides)
4. Add DELETE /knowledge-graph/auto-generated for idempotency
5. Run and verify

CONSTRAINTS: Use API calls (5-layer). Tag all entities with auto_generated:true.
```
