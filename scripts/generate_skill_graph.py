#!/usr/bin/env python3
"""
Generate Knowledge Graph from skill.json files.

Reads all aria_skills/*/skill.json, creates KnowledgeEntity + KnowledgeRelation
records via the Aria API. All auto-generated entities are tagged with
properties.auto_generated = true for idempotent regeneration.

Entity types: skill, tool, focus_mode, category
Relation types: belongs_to, affinity, depends_on, provides

Usage:
    python scripts/generate_skill_graph.py [--api-url http://localhost:8000]
"""

import argparse
import json
import sys
from pathlib import Path

import httpx

DEFAULT_API_URL = "http://localhost:8000"
SKILLS_DIR = Path(__file__).resolve().parent.parent / "aria_skills"

# Canonical focus modes
FOCUS_MODES = {
    "orchestrator": "System orchestration, scheduling, and coordination",
    "devsecops": "Security scanning, CI/CD, and DevOps automation",
    "data": "Data pipelines, ETL, and analytics",
    "trader": "Market data, portfolio management, and trading",
    "creative": "Content creation, brainstorming, and art",
    "social": "Community management, social posting, and engagement",
    "journalist": "Research, fact-checking, and information gathering",
}


def read_skill_jsons(skills_dir: Path) -> list[dict]:
    """Read all skill.json files from the skills directory."""
    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.name.startswith("_"):
            continue
        sj_path = skill_dir / "skill.json"
        if sj_path.is_file():
            try:
                with open(sj_path) as f:
                    data = json.load(f)
                data["_dir"] = skill_dir.name
                skills.append(data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"  ⚠️  Skipping {skill_dir.name}: {e}")
    return skills


def clear_auto_generated(client: httpx.Client, api_url: str) -> int:
    """Delete all auto-generated entities (cascades to relations)."""
    resp = client.delete(f"{api_url}/knowledge-graph/auto-generated")
    if resp.status_code == 200:
        data = resp.json()
        count = data.get("deleted_entities", 0)
        print(f"  🗑️  Cleared {count} auto-generated entities + cascaded relations")
        return count
    else:
        print(f"  ⚠️  Clear returned {resp.status_code}: {resp.text}")
        return 0


def create_entity(client: httpx.Client, api_url: str, name: str, etype: str, props: dict) -> str | None:
    """Create an entity and return its ID."""
    props["auto_generated"] = True
    resp = client.post(f"{api_url}/knowledge-graph/entities", json={
        "name": name, "type": etype, "properties": props,
    })
    if resp.status_code == 200:
        return resp.json().get("id")
    print(f"  ⚠️  Failed to create entity {name}: {resp.text}")
    return None


def create_relation(client: httpx.Client, api_url: str, from_id: str, to_id: str, rel_type: str, props: dict | None = None) -> bool:
    """Create a relation between two entities."""
    payload = {
        "from_entity": from_id, "to_entity": to_id,
        "relation_type": rel_type,
        "properties": {**(props or {}), "auto_generated": True},
    }
    resp = client.post(f"{api_url}/knowledge-graph/relations", json=payload)
    return resp.status_code == 200


def generate_graph(api_url: str) -> dict:
    """Main graph generation: skills → entities + relations."""
    skills = read_skill_jsons(SKILLS_DIR)
    print(f"📂 Found {len(skills)} skill.json files")

    client = httpx.Client(timeout=30)

    # Step 1: Clear existing auto-generated data
    print("🧹 Clearing previous auto-generated graph…")
    clear_auto_generated(client, api_url)

    entity_ids: dict[str, str] = {}  # name → UUID
    stats = {"entities": 0, "relations": 0, "skills": 0, "tools": 0, "focus_modes": 0, "categories": 0}

    # Step 2: Create focus mode entities
    print("🎯 Creating focus mode entities…")
    for fm_name, fm_desc in FOCUS_MODES.items():
        eid = create_entity(client, api_url, fm_name, "focus_mode", {
            "description": fm_desc,
        })
        if eid:
            entity_ids[f"fm:{fm_name}"] = eid
            stats["focus_modes"] += 1
            stats["entities"] += 1

    # Step 3: Create category entities (collect unique categories)
    categories: set[str] = set()
    for skill in skills:
        cat = skill.get("category", "")
        if cat and cat != "unknown":
            categories.add(cat)
        # Also derive category from focus_affinity
        for fa in skill.get("focus_affinity", []):
            if fa in FOCUS_MODES:
                categories.add(fa)

    # Add standard categories
    categories.update(["orchestration", "devsecops", "data", "trading", "creative", "social", "cognitive", "utility"])

    print(f"📁 Creating {len(categories)} category entities…")
    for cat_name in sorted(categories):
        eid = create_entity(client, api_url, cat_name, "category", {
            "description": f"Skill category: {cat_name}",
        })
        if eid:
            entity_ids[f"cat:{cat_name}"] = eid
            stats["categories"] += 1
            stats["entities"] += 1

    # Step 4: Create skill entities + tool entities + relations
    print("🔧 Creating skill + tool entities and relations…")
    for skill in skills:
        skill_name = skill.get("name", skill["_dir"])
        skill_desc = skill.get("description", "")
        skill_layer = skill.get("layer", 3)
        skill_cat = skill.get("category", "unknown")
        focus_list = skill.get("focus_affinity", [])
        deps = skill.get("dependencies", [])
        tools = skill.get("tools", [])

        # Create skill entity
        eid = create_entity(client, api_url, skill_name, "skill", {
            "description": skill_desc,
            "layer": skill_layer,
            "category": skill_cat,
            "directory": skill["_dir"],
            "tool_count": len(tools),
        })
        if not eid:
            continue
        entity_ids[f"skill:{skill_name}"] = eid
        stats["skills"] += 1
        stats["entities"] += 1

        # Create tool entities and 'provides' relations
        for tool in tools:
            tool_name = tool.get("name", "") if isinstance(tool, dict) else str(tool)
            tool_desc = tool.get("description", "") if isinstance(tool, dict) else ""
            if not tool_name:
                continue
            # Unique key for tool scoped to skill
            tool_key = f"tool:{skill_name}:{tool_name}"
            if tool_key not in entity_ids:
                tid = create_entity(client, api_url, tool_name, "tool", {
                    "description": tool_desc,
                    "skill": skill_name,
                })
                if tid:
                    entity_ids[tool_key] = tid
                    stats["tools"] += 1
                    stats["entities"] += 1
            # provides relation: skill → tool
            tid = entity_ids.get(tool_key)
            if tid:
                if create_relation(client, api_url, eid, tid, "provides"):
                    stats["relations"] += 1

        # belongs_to relations: skill → category
        cat_key = f"cat:{skill_cat}" if skill_cat != "unknown" else None
        if cat_key and cat_key in entity_ids:
            if create_relation(client, api_url, eid, entity_ids[cat_key], "belongs_to"):
                stats["relations"] += 1

        # affinity relations: skill → focus_mode
        for fm in focus_list:
            fm_key = f"fm:{fm}"
            if fm_key in entity_ids:
                if create_relation(client, api_url, eid, entity_ids[fm_key], "affinity"):
                    stats["relations"] += 1

        # depends_on relations: skill → dependency skill
        for dep in deps:
            dep_key = f"skill:{dep}"
            if dep_key in entity_ids:
                if create_relation(client, api_url, eid, entity_ids[dep_key], "depends_on"):
                    stats["relations"] += 1

    # Step 5: Second pass for cross-skill dependencies (some skills reference deps created later)
    print("🔗 Resolving cross-skill dependencies (second pass)…")
    for skill in skills:
        skill_name = skill.get("name", skill["_dir"])
        skill_key = f"skill:{skill_name}"
        if skill_key not in entity_ids:
            continue
        for dep in skill.get("dependencies", []):
            # Try matching by name or canonical name
            dep_key = f"skill:{dep}"
            if dep_key in entity_ids:
                # Check if relation already exists (best-effort idempotency)
                create_relation(client, api_url, entity_ids[skill_key], entity_ids[dep_key], "depends_on")

    client.close()

    print(f"\n✅ Graph generated!")
    print(f"   Entities: {stats['entities']} (skills={stats['skills']}, tools={stats['tools']}, focus_modes={stats['focus_modes']}, categories={stats['categories']})")
    print(f"   Relations: {stats['relations']}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate skill knowledge graph")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="Aria API base URL")
    args = parser.parse_args()
    generate_graph(args.api_url)
