"""Kernel-friendly skill introspection utilities."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Callable


def _normalize_skill_name(skill_name: str) -> str:
    if skill_name.startswith("aria-"):
        return skill_name[5:].replace("-", "_")
    return skill_name


def collect_skill_info(
    skill_name: str,
    registry: dict,
    validate_skill_coherence_fn: Callable[[str], dict],
    workspace_root_fn: Callable[[], Path],
) -> dict:
    """Return merged runtime + manifest + docs + coherence metadata for a skill."""
    normalized = _normalize_skill_name(skill_name)
    root = workspace_root_fn()
    skill_path = root / "aria_skills" / normalized
    canonical_name = f"aria-{normalized.replace('_', '-')}"

    out: dict = {
        "requested_skill": skill_name,
        "skill_name": normalized,
        "canonical_name": canonical_name,
        "registered": normalized in registry,
        "paths": {
            "dir": str(skill_path),
            "manifest": str(skill_path / "skill.json"),
            "docs": str(skill_path / "SKILL.md"),
            "impl": str(skill_path / "__init__.py"),
        },
    }

    out["coherence"] = validate_skill_coherence_fn(normalized)

    if normalized in registry:
        module_name, class_name, _config_fn = registry[normalized]
        out["runtime"] = {"module": module_name, "class": class_name}
        try:
            module = importlib.import_module(module_name)
            skill_class = getattr(module, class_name)
            methods = [
                name
                for name in dir(skill_class)
                if not name.startswith("_")
                and callable(getattr(skill_class, name, None))
                and name
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
            out["runtime"]["methods"] = sorted(methods)
        except Exception as exc:
            out["runtime"]["introspection_error"] = str(exc)

    manifest_path = skill_path / "skill.json"
    if manifest_path.exists():
        try:
            out["manifest"] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            out["manifest_error"] = str(exc)

    docs_path = skill_path / "SKILL.md"
    if docs_path.exists():
        text = docs_path.read_text(encoding="utf-8")
        first_nonempty = next((line.strip() for line in text.splitlines() if line.strip()), "")
        out["docs"] = {
            "title_line": first_nonempty,
            "has_main_tools_section": "## Main Tools" in text,
            "has_purpose_section": "## Purpose" in text,
        }

    return out
