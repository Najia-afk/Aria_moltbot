"""Lightweight skill catalog generator — reads skill.json v2 files."""
import json
import os
from pathlib import Path
from typing import Optional


def generate_catalog(skills_dir: str = "aria_skills") -> dict:
    """Generate lightweight skill catalog from skill.json files."""
    catalog = {"catalog_version": "1.0", "skills": []}
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return catalog
    for skill_dir in sorted(skills_path.iterdir()):
        sj_path = skill_dir / "skill.json"
        if sj_path.is_file():
            try:
                with open(sj_path) as f:
                    sj = json.load(f)
                catalog["skills"].append({
                    "name": sj.get("name", skill_dir.name),
                    "layer": sj.get("layer", 3),
                    "category": sj.get("category", "unknown"),
                    "description": sj.get("description", ""),
                    "tools": [t["name"] for t in sj.get("tools", [])],
                    "focus_affinity": sj.get("focus_affinity", []),
                    "dependencies": sj.get("dependencies", []),
                    "status": "active",
                })
            except (json.JSONDecodeError, KeyError) as e:
                catalog["skills"].append({
                    "name": skill_dir.name,
                    "status": "error",
                    "error": str(e),
                })
    return catalog


def save_catalog(path: str = "aria_memories/memory/skills.json") -> dict:
    """Save catalog to writable data directory."""
    catalog = generate_catalog()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(catalog, f, indent=2)
    return catalog
