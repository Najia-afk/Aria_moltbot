"""Kernel-oriented skill routing helpers.

Primary route source: aria-api knowledge graph endpoints.
Fallback route source: local skill manifest overlap scoring.
"""


import os
import re
from pathlib import Path
from typing import Callable

from aria_mind.skills._skill_introspection import collect_skill_info

_API_BASE = os.environ.get("ARIA_API_URL", "http://aria-api:8000/api").rstrip("/")

try:
    import httpx  # type: ignore[import-not-found]

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False


_TOKEN_RE = re.compile(r"[a-z0-9_\-]+")


def _tokens(text: str) -> set[str]:
    return {tok for tok in _TOKEN_RE.findall((text or "").lower()) if len(tok) > 2}


def _normalize_skill_name(name: str) -> str:
    val = (name or "").strip()
    if val.startswith("aria-"):
        return val[5:].replace("-", "_")
    return val.replace("-", "_")


def _candidate_skill_name(candidate: dict) -> str:
    for key in ("skill_name", "name", "canonical_name"):
        value = candidate.get(key)
        if value:
            return _normalize_skill_name(str(value))
    return ""


def _load_manifest_text(skill_dir: Path) -> tuple[dict, str]:
    import json

    manifest_path = skill_dir / "skill.json"
    if not manifest_path.exists():
        return {}, ""

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, ""

    text_chunks = [
        str(manifest.get("name") or ""),
        str(manifest.get("description") or ""),
        " ".join(str(x) for x in manifest.get("focus_affinity") or []),
    ]
    for tool in manifest.get("tools") or []:
        text_chunks.append(str(tool.get("name") or ""))
        text_chunks.append(str(tool.get("description") or ""))

    return manifest, "\n".join(text_chunks)


def _local_manifest_route(task: str, limit: int, workspace_root_fn: Callable[[], Path]) -> list[dict]:
    root = workspace_root_fn() / "aria_skills"
    if not root.exists():
        # Container layout: skills/aria_skills/
        root = workspace_root_fn() / "skills" / "aria_skills"
    if not root.exists():
        return []

    query_tokens = _tokens(task)
    if not query_tokens:
        return []

    scored: list[tuple[int, dict]] = []
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if not entry.is_dir() or entry.name.startswith("_") or entry.name == "pipelines":
            continue

        manifest, text = _load_manifest_text(entry)
        if not manifest:
            continue

        doc_tokens = _tokens(text)
        overlap = sorted(query_tokens.intersection(doc_tokens))
        score = len(overlap)
        if score <= 0:
            continue

        canonical = f"aria-{entry.name.replace('_', '-')}"
        scored.append(
            (
                score,
                {
                    "skill_name": entry.name,
                    "name": canonical,
                    "canonical_name": canonical,
                    "match_type": "manifest_overlap",
                    "relevance": f"score:{score}",
                    "overlap": overlap,
                },
            )
        )

    scored.sort(key=lambda row: row[0], reverse=True)
    return [candidate for _, candidate in scored[: max(1, limit)]]


async def _api_route_candidates(task: str, limit: int) -> tuple[list[dict], str | None, list[dict]]:
    diagnostics: list[dict] = []
    if not _HAS_HTTPX:
        return [], "httpx_not_available", [{"type": "dependency", "reason": "httpx_not_available"}]

    endpoints = (
        "/knowledge-graph/skill-for-task-semantic",
        "/knowledge-graph/skill-for-task",
    )

    async with httpx.AsyncClient(timeout=8) as client:
        for endpoint in endpoints:
            try:
                response = await client.get(f"{_API_BASE}{endpoint}", params={"task": task, "limit": limit})
                if response.status_code >= 400:
                    diagnostics.append({
                        "type": "api_attempt",
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "accepted": False,
                    })
                    continue
                payload = response.json()
                candidates = payload.get("candidates") if isinstance(payload, dict) else None
                if isinstance(candidates, list):
                    diagnostics.append({
                        "type": "api_attempt",
                        "endpoint": endpoint,
                        "status_code": response.status_code,
                        "accepted": True,
                        "candidate_count": len(candidates),
                    })
                    return candidates, endpoint, diagnostics
                diagnostics.append({
                    "type": "api_attempt",
                    "endpoint": endpoint,
                    "status_code": response.status_code,
                    "accepted": False,
                    "reason": "missing_candidates_list",
                })
            except Exception as exc:
                diagnostics.append({
                    "type": "api_attempt",
                    "endpoint": endpoint,
                    "accepted": False,
                    "reason": str(exc),
                })
                continue

    if not diagnostics:
        diagnostics.append({"type": "api_attempt", "reason": "no_api_candidates"})
    return [], "no_api_candidates", diagnostics


async def auto_route_task_to_skills(
    task: str,
    limit: int,
    registry: dict,
    validate_skill_coherence_fn: Callable[[str], dict],
    workspace_root_fn: Callable[[], Path],
    include_info: bool = True,
) -> dict:
    """Auto-route a task to candidate skills using graph first, local manifests second."""
    requested_limit = max(1, limit)

    api_candidates, route_source, route_diagnostics = await _api_route_candidates(task, requested_limit)
    if api_candidates:
        source = f"api:{route_source}"
        candidates = api_candidates
    else:
        source = "local:manifest_overlap"
        candidates = _local_manifest_route(task, requested_limit, workspace_root_fn)
        route_diagnostics.append(
            {
                "type": "fallback",
                "source": source,
                "candidate_count": len(candidates),
                "reason": route_source,
            }
        )

    normalized_rows: list[dict] = []
    seen: set[str] = set()
    for candidate in candidates:
        skill_name = _candidate_skill_name(candidate)
        if not skill_name or skill_name in seen:
            continue
        seen.add(skill_name)

        row = {
            "skill_name": skill_name,
            "canonical_name": f"aria-{skill_name.replace('_', '-')}",
            "registered": skill_name in registry,
            "match": candidate,
        }

        if include_info:
            row["skill_info"] = collect_skill_info(
                skill_name=skill_name,
                registry=registry,
                validate_skill_coherence_fn=validate_skill_coherence_fn,
                workspace_root_fn=workspace_root_fn,
            )

        normalized_rows.append(row)
        if len(normalized_rows) >= requested_limit:
            break

    return {
        "task": task,
        "route_source": source,
        "route_diagnostics": route_diagnostics,
        "count": len(normalized_rows),
        "candidates": normalized_rows,
    }
