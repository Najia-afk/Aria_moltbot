"""
Graph sync — auto-populate skill graph from skill.json files at startup.

ORM-based (no HTTP calls) for use inside the API container. Idempotent:
clears all skill_graph_* tables before regenerating.
"""

import json
import logging
import uuid as uuid_mod
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SkillGraphEntity, SkillGraphRelation
from db.session import AsyncSessionLocal

logger = logging.getLogger("aria.graph_sync")

# Skill directory — mounted inside the API container
SKILLS_DIR = Path("/aria_skills")
# Fallback for local dev
if not SKILLS_DIR.exists():
    SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "aria_skills"

FOCUS_MODES = {
    "orchestrator": "System orchestration, scheduling, and coordination",
    "devsecops": "Security scanning, CI/CD, and DevOps automation",
    "data": "Data pipelines, ETL, and analytics",
    "trader": "Market data, portfolio management, and trading",
    "creative": "Content creation, brainstorming, and art",
    "social": "Community management, social posting, and engagement",
    "journalist": "Research, fact-checking, and information gathering",
    "memory": "Memory compression, sentiment analysis, pattern recognition, and search",
}

STANDARD_CATEGORIES = [
    "orchestration", "devsecops", "data", "trading",
    "creative", "social", "cognitive", "utility",
]


def _read_skill_jsons() -> list[dict]:
    """Read all skill.json files."""
    skills = []
    if not SKILLS_DIR.exists():
        logger.warning("Skills directory not found: %s", SKILLS_DIR)
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.name.startswith("_"):
            continue
        sj_path = skill_dir / "skill.json"
        if sj_path.is_file():
            try:
                with open(sj_path, encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                data["_dir"] = skill_dir.name
                skills.append(data)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skipping %s: %s", skill_dir.name, e)
    return skills


async def _clear_skill_graph(db: AsyncSession) -> int:
    """Delete all skill graph entities and relations (dedicated tables)."""
    await db.execute(delete(SkillGraphRelation))
    result = await db.execute(delete(SkillGraphEntity))
    count = result.rowcount
    return count


def _make_entity(name: str, etype: str, props: dict) -> SkillGraphEntity:
    """Create a skill graph entity ORM instance."""
    return SkillGraphEntity(
        id=uuid_mod.uuid4(), name=name, type=etype, properties=props,
    )


def _make_relation(from_id, to_id, rel_type: str) -> SkillGraphRelation:
    """Create a skill graph relation ORM instance."""
    return SkillGraphRelation(
        id=uuid_mod.uuid4(), from_entity=from_id, to_entity=to_id,
        relation_type=rel_type, properties={},
    )


async def sync_skill_graph() -> dict:
    """
    Synchronize skill graph. Clears previous auto-generated data, then
    rebuilds from skill.json files. Returns stats dict.
    """
    skills = _read_skill_jsons()
    logger.info("Graph sync: found %d skill.json files", len(skills))

    stats = {"entities": 0, "relations": 0, "skills": 0, "tools": 0,
             "focus_modes": 0, "categories": 0, "cleared": 0}

    async with AsyncSessionLocal() as db:
        async with db.begin():
            # Clear existing skill graph
            cleared = await _clear_skill_graph(db)
            stats["cleared"] = cleared
            logger.info("Cleared %d skill graph entities", cleared)

            entity_map: dict[str, SkillGraphEntity] = {}  # key → entity

            # Focus modes
            for fm_name, fm_desc in FOCUS_MODES.items():
                fm_key = f"fm:{fm_name}"
                if fm_key in entity_map:
                    continue
                e = _make_entity(fm_name, "focus_mode", {"description": fm_desc})
                db.add(e)
                entity_map[fm_key] = e
                stats["focus_modes"] += 1
                stats["entities"] += 1

            # Categories
            categories: set[str] = set(STANDARD_CATEGORIES)
            for skill in skills:
                cat = skill.get("category", "")
                if cat and cat != "unknown":
                    categories.add(cat)
            for cat in sorted(categories):
                cat_key = f"cat:{cat}"
                if cat_key in entity_map:
                    continue
                e = _make_entity(cat, "category", {"description": f"Skill category: {cat}"})
                db.add(e)
                entity_map[cat_key] = e
                stats["categories"] += 1
                stats["entities"] += 1

            # Skills + tools + relations
            for skill in skills:
                skill_name = skill.get("name", skill["_dir"])
                skill_desc = skill.get("description", "")
                skill_layer = skill.get("layer", 3)
                skill_cat = skill.get("category", "unknown")
                focus_list = skill.get("focus_affinity", [])
                deps = skill.get("dependencies", [])
                tools = skill.get("tools", [])

                skill_key = f"skill:{skill_name}"
                if skill_key in entity_map:
                    logger.warning("Duplicate skill name detected, skipping: %s", skill_name)
                    continue

                se = _make_entity(skill_name, "skill", {
                    "description": skill_desc, "layer": skill_layer,
                    "category": skill_cat, "directory": skill["_dir"],
                    "tool_count": len(tools),
                })
                db.add(se)
                entity_map[skill_key] = se
                stats["skills"] += 1
                stats["entities"] += 1

                # Tools
                for tool in tools:
                    tool_name = tool.get("name", "") if isinstance(tool, dict) else str(tool)
                    tool_desc = tool.get("description", "") if isinstance(tool, dict) else ""
                    if not tool_name:
                        continue
                    # Use global tool key to avoid duplicates across skills
                    tool_key = f"tool:{tool_name}"
                    if tool_key not in entity_map:
                        te = _make_entity(tool_name, "tool", {
                            "description": tool_desc, "skill": skill_name,
                        })
                        db.add(te)
                        entity_map[tool_key] = te
                        stats["tools"] += 1
                        stats["entities"] += 1
                    # provides
                    db.add(_make_relation(se.id, entity_map[tool_key].id, "provides"))
                    stats["relations"] += 1

                # belongs_to
                cat_key = f"cat:{skill_cat}" if skill_cat != "unknown" else None
                if cat_key and cat_key in entity_map:
                    db.add(_make_relation(se.id, entity_map[cat_key].id, "belongs_to"))
                    stats["relations"] += 1

                # affinity
                for fm in focus_list:
                    fm_key = f"fm:{fm}"
                    if fm_key in entity_map:
                        db.add(_make_relation(se.id, entity_map[fm_key].id, "affinity"))
                        stats["relations"] += 1

                # depends_on
                for dep in deps:
                    dep_key = f"skill:{dep}"
                    if dep_key in entity_map:
                        db.add(_make_relation(se.id, entity_map[dep_key].id, "depends_on"))
                        stats["relations"] += 1

    logger.info(
        "Graph sync complete: %d entities (%d skills, %d tools, %d focus_modes, %d categories), %d relations",
        stats["entities"], stats["skills"], stats["tools"],
        stats["focus_modes"], stats["categories"], stats["relations"],
    )
    return stats
