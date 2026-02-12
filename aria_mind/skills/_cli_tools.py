"""CLI utility handlers for run_skill."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from aria_mind.skills._skill_registry import SKILL_REGISTRY


def handle_list_skills() -> None:
    print(f"{'Name':<22} {'Canonical':<24} {'Module':<40} {'skill.json'}")
    print("-" * 100)
    for name, (mod, _cls, _cfg) in sorted(SKILL_REGISTRY.items()):
        canonical = f"aria-{name.replace('_', '-')}"
        has_json = Path(f"aria_skills/{name}/skill.json").exists()
        print(f"{name:<22} {canonical:<24} {mod:<40} {'YES' if has_json else 'no'}")
    sys.exit(0)


def handle_export_catalog() -> None:
    catalog = {"generated_at": datetime.now(timezone.utc).isoformat(), "skills": []}
    for name, (mod, cls_name, _cfg) in sorted(SKILL_REGISTRY.items()):
        try:
            module = importlib.import_module(mod)
            skill_cls = getattr(module, cls_name)
            methods = [
                m
                for m in dir(skill_cls)
                if not m.startswith("_")
                and callable(getattr(skill_cls, m, None))
                and m
                not in (
                    "initialize",
                    "health_check",
                    "name",
                    "canonical_name",
                    "close",
                    "is_available",
                    "status",
                )
            ]
            catalog["skills"].append(
                {
                    "name": name,
                    "canonical_name": f"aria-{name.replace('_', '-')}",
                    "module": mod,
                    "class": cls_name,
                    "methods": methods,
                }
            )
        except Exception as exc:
            catalog["skills"].append({"name": name, "module": mod, "error": str(exc)})

    Path("aria_memories/exports").mkdir(parents=True, exist_ok=True)
    Path("aria_memories/exports/skill_catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"Catalog written: {len(catalog['skills'])} skills -> aria_memories/exports/skill_catalog.json")
    sys.exit(0)


def handle_health_check_all() -> None:
    async def _check_all() -> None:
        for name, (mod, cls_name, config_fn) in sorted(SKILL_REGISTRY.items()):
            try:
                module = importlib.import_module(mod)
                skill_cls = getattr(module, cls_name)
                from aria_skills.base import SkillConfig

                config = SkillConfig(name=name, config=config_fn())
                skill = skill_cls(config=config)
                ok = await skill.initialize()
                status = (await skill.health_check()).value if ok else "INIT_FAILED"
                print(f"{name:<22} {status}")
            except Exception as exc:
                print(f"{name:<22} ERROR: {exc}")

    asyncio.run(_check_all())
    sys.exit(0)
