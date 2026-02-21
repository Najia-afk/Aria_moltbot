"""Skill coherence and reporting helpers for run_skill."""


import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def skill_dir(root: Path, skill_name: str) -> Path:
    """Resolve skill directory, handling both local and container layouts.

    Local:     <root>/aria_skills/<skill>/
    Container: <root>/skills/aria_skills/<skill>/  (volume-mounted)
    """
    primary = root / "aria_skills" / skill_name
    if primary.exists():
        return primary
    container_path = root / "skills" / "aria_skills" / skill_name
    if container_path.exists():
        return container_path
    # Fall back to primary (will report missing files correctly)
    return primary


def has_skill_changes(root: Path, skill_name: str) -> bool:
    """Return True when git reports changes under this skill directory."""
    try:
        # Try both local and container-mounted paths
        rels = [f"aria_skills/{skill_name}", f"skills/aria_skills/{skill_name}"]
        for rel in rels:
            proc = subprocess.run(
                ["git", "status", "--porcelain", "--", rel],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if (proc.stdout or "").strip():
                return True
        return False
    except Exception:
        return False


def validate_skill_coherence(
    skill_name: str,
    workspace_root_fn: Callable[[], Path],
    has_skill_changes_fn: Callable[[str], bool],
) -> dict:
    """Validate __init__.py, skill.json, SKILL.md coherence for a skill directory."""
    root = workspace_root_fn()
    skill_path = skill_dir(root, skill_name)
    report = {
        "skill_name": skill_name,
        "canonical_name": f"aria-{skill_name.replace('_', '-')}",
        "skill_path": str(skill_path),
        "has_changes": has_skill_changes_fn(skill_name),
        "checks": {},
        "errors": [],
        "warnings": [],
        "coherent": True,
    }

    init_path = skill_path / "__init__.py"
    json_path = skill_path / "skill.json"
    md_path = skill_path / "SKILL.md"

    report["checks"]["init_exists"] = init_path.exists()
    report["checks"]["json_exists"] = json_path.exists()
    report["checks"]["md_exists"] = md_path.exists()

    if not init_path.exists():
        report["errors"].append("Missing __init__.py")
    if not json_path.exists():
        report["errors"].append("Missing skill.json")
    if not md_path.exists():
        report["errors"].append("Missing SKILL.md")

    if json_path.exists():
        try:
            manifest = json.loads(json_path.read_text(encoding="utf-8"))
            expected_name = report["canonical_name"]
            actual_name = manifest.get("name")
            report["checks"]["json_name_matches"] = actual_name == expected_name
            report["checks"]["manifest_name"] = actual_name
            if actual_name != expected_name:
                report["errors"].append(
                    f"skill.json name mismatch: expected '{expected_name}', got '{actual_name}'"
                )
        except Exception as exc:
            report["checks"]["json_name_matches"] = False
            report["errors"].append(f"skill.json parse error: {exc}")

    if init_path.exists():
        try:
            init_text = init_path.read_text(encoding="utf-8")
            has_registry = "@SkillRegistry.register" in init_text
            has_skill_class = "class " in init_text and "Skill" in init_text
            report["checks"]["init_registry_decorator"] = has_registry
            report["checks"]["init_has_skill_class"] = has_skill_class
            if not has_registry:
                report["warnings"].append("No @SkillRegistry.register in __init__.py")
            if not has_skill_class:
                report["errors"].append("No Skill class definition found in __init__.py")
        except Exception as exc:
            report["errors"].append(f"__init__.py read error: {exc}")

    if md_path.exists():
        try:
            md_text = md_path.read_text(encoding="utf-8").lower()
            expected_canonical = report["canonical_name"]
            expected_python = skill_name
            mentions_name = (expected_canonical in md_text) or (expected_python in md_text)
            report["checks"]["md_mentions_skill"] = mentions_name
            if not mentions_name:
                report["warnings"].append(
                    f"SKILL.md does not mention '{expected_canonical}' or '{expected_python}'"
                )
        except Exception as exc:
            report["errors"].append(f"SKILL.md read error: {exc}")

    report["coherent"] = len(report["errors"]) == 0
    return report


def write_aria_mind_run_report(report: dict, workspace_root_fn: Callable[[], Path]) -> None:
    """Persist mandatory skill-run report into aria_memories/logs."""
    root = workspace_root_fn()
    reports_dir = root / "aria_memories" / "logs"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = {**report, "reported_at": datetime.now(timezone.utc).isoformat()}

    latest_path = reports_dir / "last_skill_run_report.json"
    latest_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    jsonl_path = reports_dir / "skill_run_reports.jsonl"
    with jsonl_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, default=str) + "\n")


def collect_skill_alignment_report(
    include_support: bool,
    workspace_root_fn: Callable[[], Path],
    support_skill_dirs: set[str],
) -> dict:
    root = workspace_root_fn()
    # Handle both local and container layouts
    skills_root = root / "aria_skills"
    if not skills_root.exists():
        skills_root = root / "skills" / "aria_skills"
    rows = []
    if not skills_root.exists():
        return {
            "root": str(skills_root),
            "skills": [],
            "count": 0,
            "coherent_count": 0,
            "incoherent_count": 0,
            "coherent": True,
        }

    for entry in sorted(skills_root.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        if not include_support and entry.name in support_skill_dirs:
            continue

        skill_name = entry.name
        canonical = f"aria-{skill_name.replace('_', '-')}"
        init_path = entry / "__init__.py"
        json_path = entry / "skill.json"
        md_path = entry / "SKILL.md"

        row = {
            "skill_name": skill_name,
            "canonical_name": canonical,
            "is_support_dir": skill_name in support_skill_dirs,
            "has_init": init_path.exists(),
            "has_skill_json": json_path.exists(),
            "has_skill_md": md_path.exists(),
            "name_matches": None,
            "errors": [],
            "coherent": True,
        }

        if not row["has_init"]:
            row["errors"].append("Missing __init__.py")
        if not row["has_skill_json"]:
            row["errors"].append("Missing skill.json")
        if not row["has_skill_md"]:
            row["errors"].append("Missing SKILL.md")

        if row["has_skill_json"]:
            try:
                manifest = json.loads(json_path.read_text(encoding="utf-8"))
                manifest_name = manifest.get("name")
                row["manifest_name"] = manifest_name
                row["name_matches"] = manifest_name == canonical
                if manifest_name != canonical:
                    row["errors"].append(
                        f"skill.json name mismatch: expected '{canonical}', got '{manifest_name}'"
                    )
            except Exception as exc:
                row["name_matches"] = False
                row["errors"].append(f"skill.json parse error: {exc}")

        row["coherent"] = len(row["errors"]) == 0
        rows.append(row)

    coherent_count = sum(1 for row in rows if row["coherent"])
    return {
        "root": str(skills_root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "skills": rows,
        "count": len(rows),
        "coherent_count": coherent_count,
        "incoherent_count": len(rows) - coherent_count,
        "coherent": coherent_count == len(rows),
        "include_support": include_support,
    }


def write_skill_alignment_report(
    include_support: bool,
    workspace_root_fn: Callable[[], Path],
    support_skill_dirs: set[str],
) -> dict:
    report = collect_skill_alignment_report(
        include_support=include_support,
        workspace_root_fn=workspace_root_fn,
        support_skill_dirs=support_skill_dirs,
    )
    reports_dir = workspace_root_fn() / "aria_mind" / "skills"
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_path = reports_dir / "skill_alignment_report.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return {"path": str(out_path), "report": report}
