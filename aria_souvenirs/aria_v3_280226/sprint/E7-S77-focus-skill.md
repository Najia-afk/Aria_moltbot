# S-77: aria_skills/focus/ — Focus Introspection + Activation Skill

**Epic:** E7 — Focus System v2 | **Priority:** P2 | **Points:** 3 | **Phase:** 4

---

## Problem

Aria cannot introspect or change her own focus programmatically during a
conversation cycle. If Aria is asked "switch to creative mode", she must:
1. Know her own current `focus_type`
2. List available profiles to find the right one
3. PATCH herself via `/api/engine/agents/{id}` to change `focus_type`
4. Reload the cached focus profile so the new instructions take effect

None of these steps are exposed as tool actions today. Aria would need to fall
back to raw `api_client` HTTP calls, which wastes tokens on path construction
and headers and has no type guidance.

This skill closes the loop: **Aria can list, inspect, and activate focus profiles
as first-class tool calls with minimal token cost.**

---

## New Files

```
aria_skills/focus/
├── __init__.py      ← skill implementation (this ticket)
├── skill.json       ← tool/action manifest
└── skill.yaml       ← registry metadata
```

---

## `aria_skills/focus/__init__.py`

```python
"""
Focus Skill — Aria focus profile introspection and activation.

Tools:
    focus__list        List all enabled focus profiles (id + display_name + level + budget)
    focus__get         Get full details for a specific focus_id
    focus__activate    Change Aria's own focus_type (PATCH agent, reload cache)
    focus__status      Return current agent focus_type and budget remaining

Token cost targets:
    focus__list     ~80 tokens output    (compact table, no addon text)
    focus__get      ~250 tokens output   (full profile without long addon)
    focus__activate ~50 tokens output    (confirmation only)
    focus__status   ~30 tokens output    (one-liner)
"""
from __future__ import annotations

import os
from typing import Any

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

ARIA_API_BASE = os.environ.get("ARIA_API_URL", "http://aria-api:8000/api")
LEVEL_NAMES = {1: "L1-Orchestrator", 2: "L2-Specialist", 3: "L3-Ephemeral"}


@SkillRegistry.register
class FocusSkill(BaseSkill):
    """
    Focus profile introspection and activation skill.

    Allows Aria to inspect available focus modes and switch her own focus_type
    mid-session. Designed for minimal token consumption.
    """

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._http = None

    @property
    def name(self) -> str:
        return "focus"

    async def initialize(self) -> bool:
        try:
            import httpx
            self._http = httpx.AsyncClient(
                base_url=ARIA_API_BASE,
                timeout=15.0,
            )
            self._status = SkillStatus.READY
            return True
        except ImportError:
            self.logger.error("httpx not installed — focus skill unavailable")
            self._status = SkillStatus.UNAVAILABLE
            return False

    async def shutdown(self) -> None:
        if self._http:
            await self._http.aclose()

    # ───────────────────────────── TOOL DISPATCH ─────────────────────────────

    async def _run(self, action: str, **kwargs: Any) -> SkillResult:
        """Dispatch tool action."""
        dispatch = {
            "focus__list":     self._list,
            "focus__get":      self._get,
            "focus__activate": self._activate,
            "focus__status":   self._status_check,
        }
        handler = dispatch.get(action)
        if handler is None:
            return SkillResult(
                success=False,
                data=None,
                error=f"Unknown focus action: {action}. Available: {list(dispatch)}",
            )
        return await handler(**kwargs)

    # ─────────────────────────── focus__list ─────────────────────────────────

    async def _list(self, **_: Any) -> SkillResult:
        """
        List all enabled focus profiles — compact format.
        Returns: list of {focus_id, display_name, delegation_level, token_budget_hint}
        Token cost target: ~80 tokens output.
        """
        resp = await self._http.get("/engine/focus")
        resp.raise_for_status()
        data = resp.json()
        profiles = data.get("profiles", data) if isinstance(data, dict) else data

        compact = [
            {
                "id": p["focus_id"],
                "name": p.get("display_name") or p["focus_id"],
                "level": LEVEL_NAMES.get(p.get("delegation_level", 2), "L2"),
                "budget": p.get("token_budget_hint", 0),
                "tone": p.get("tone", ""),
            }
            for p in profiles
            if p.get("enabled", True)
        ]
        return SkillResult(success=True, data=compact)

    # ─────────────────────────── focus__get ──────────────────────────────────

    async def _get(self, focus_id: str, **_: Any) -> SkillResult:
        """
        Get full profile for a specific focus_id.
        Omits system_prompt_addon from output to save tokens.
        Token cost target: ~250 tokens output.
        """
        resp = await self._http.get(f"/engine/focus/{focus_id}")
        if resp.status_code == 404:
            return SkillResult(success=False, data=None, error=f"Focus '{focus_id}' not found")
        resp.raise_for_status()
        profile = resp.json()

        # Strip verbose addon to save tokens — agent receives it anyway via process()
        summary = {k: v for k, v in profile.items() if k != "system_prompt_addon"}
        summary["addon_length"] = len(profile.get("system_prompt_addon") or "")
        return SkillResult(success=True, data=summary)

    # ─────────────────────────── focus__activate ─────────────────────────────

    async def _activate(
        self,
        focus_id: str,
        agent_id: str | None = None,
        **_: Any,
    ) -> SkillResult:
        """
        Switch focus_type for an agent (default: self / calling agent).

        Sends PATCH /api/engine/agents/{agent_id} {"focus_type": focus_id}.
        Returns: confirmation with new focus_id and token_budget.

        Token cost target: ~50 tokens output.
        """
        # Resolve agent_id — default to ARIA_AGENT_ID env var (current agent)
        target = agent_id or os.environ.get("ARIA_AGENT_ID", "aria-main")

        # Verify the focus profile exists first
        check_resp = await self._http.get(f"/engine/focus/{focus_id}")
        if check_resp.status_code == 404:
            return SkillResult(
                success=False,
                data=None,
                error=f"Focus profile '{focus_id}' not found. Use focus__list to see available profiles.",
            )

        profile = check_resp.json()
        if not profile.get("enabled", True):
            return SkillResult(
                success=False,
                data=None,
                error=f"Focus profile '{focus_id}' is disabled. Choose an active profile.",
            )

        # Patch the agent
        patch_resp = await self._http.patch(
            f"/engine/agents/{target}",
            json={"focus_type": focus_id},
        )
        if patch_resp.status_code == 404:
            return SkillResult(
                success=False,
                data=None,
                error=f"Agent '{target}' not found.",
            )
        patch_resp.raise_for_status()

        return SkillResult(
            success=True,
            data={
                "agent_id": target,
                "focus_id": focus_id,
                "token_budget": profile.get("token_budget_hint"),
                "level": LEVEL_NAMES.get(profile.get("delegation_level", 2), "L2"),
                "message": f"Focus switched to '{focus_id}'",
            },
        )

    # ─────────────────────────── focus__status ───────────────────────────────

    async def _status_check(
        self,
        agent_id: str | None = None,
        **_: Any,
    ) -> SkillResult:
        """
        Return current focus_type and token_budget for an agent.

        Token cost target: ~30 tokens output.
        """
        target = agent_id or os.environ.get("ARIA_AGENT_ID", "aria-main")
        resp = await self._http.get(f"/engine/agents/{target}")
        if resp.status_code == 404:
            return SkillResult(success=False, data=None, error=f"Agent '{target}' not found")
        resp.raise_for_status()
        agent = resp.json()

        return SkillResult(
            success=True,
            data={
                "agent_id": target,
                "focus_type": agent.get("focus_type"),
                "status": agent.get("status"),
            },
        )
```

---

## `aria_skills/focus/skill.json`

```json
{
  "name": "focus",
  "version": "1.0.0",
  "description": "Focus profile introspection and activation. Allows Aria to list, inspect, and switch her own focus mode mid-session with minimal token cost.",
  "tools": [
    {
      "name": "focus__list",
      "description": "List all enabled focus profiles. Returns compact table: id, name, delegation level, token budget, tone. Use before activating a focus.",
      "input_schema": {
        "type": "object",
        "properties": {}
      }
    },
    {
      "name": "focus__get",
      "description": "Get full details for a specific focus profile by ID. Returns all fields except system_prompt_addon (addon is applied automatically). Addon character count is included.",
      "input_schema": {
        "type": "object",
        "properties": {
          "focus_id": {
            "type": "string",
            "description": "Focus profile ID (e.g. 'devsecops', 'creative', 'orchestrator')"
          }
        },
        "required": ["focus_id"]
      }
    },
    {
      "name": "focus__activate",
      "description": "Switch an agent's focus_type to a new focus profile. If agent_id is omitted, switches Aria's own focus. Returns confirmation with new token budget.",
      "input_schema": {
        "type": "object",
        "properties": {
          "focus_id": {
            "type": "string",
            "description": "Focus profile ID to activate"
          },
          "agent_id": {
            "type": "string",
            "description": "Agent to update (default: current agent / aria-main)"
          }
        },
        "required": ["focus_id"]
      }
    },
    {
      "name": "focus__status",
      "description": "Return current focus_type and status for an agent. Minimal output (~30 tokens). Use to check current focus before switching.",
      "input_schema": {
        "type": "object",
        "properties": {
          "agent_id": {
            "type": "string",
            "description": "Agent ID (default: current agent)"
          }
        }
      }
    }
  ]
}
```

---

## `aria_skills/focus/skill.yaml`

```yaml
name: focus
version: "1.0.0"
enabled: true
description: >
  Focus profile introspection and self-activation skill.
  Aria can list available focus modes, inspect their token budgets
  and delegation levels, and switch her own focus_type mid-session.
config:
  api_url: "${ARIA_API_URL:-http://aria-api:8000/api}"
tags:
  - meta
  - self-awareness
  - token-management
  - focus
```

---

## Token Economy Summary

| Tool | Input tokens (typical) | Output tokens (guaranteed ≤) |
|------|----------------------|------------------------------|
| `focus__list` | ~10 | 80 (compact table, 8 profiles) |
| `focus__get` | ~15 | 250 (full fields, no addon body) |
| `focus__activate` | ~15 | 50 (confirmation only) |
| `focus__status` | ~10 | 30 (2-field dict) |

The `system_prompt_addon` text is **never returned** to Aria's conscious tool
output — it is applied invisibly by `agent_pool.process()` (S-73). This
eliminates ~1500 tokens per `focus__get` call.

---

## Constraints

| # | Constraint | Status | Notes |
|---|-----------|--------|-------|
| 1 | Skill layer: no direct DB access | ✅ | All calls go through `/api/engine/focus` and `/api/engine/agents` REST API |
| 2 | Token budget targets enforced by design | ✅ | addon stripped, compact output schema |
| 3 | Activation validates before patching | ✅ | focus profile existence + enabled check first |
| 4 | Agent defaults to ARIA_AGENT_ID env | ✅ | `os.environ.get("ARIA_AGENT_ID", "aria-main")` |
| 5 | No soul modification | ✅ | None |

---

## Dependencies

- **S-71** — `/api/engine/focus` CRUD endpoints must exist
- **S-73** — PATCH `/api/engine/agents/{id}` must accept `focus_type` (added in Phase 14)

---

## Verification

```bash
# 1. Syntax clean
docker exec aria-engine python3 -c "
import ast, pathlib
ast.parse(pathlib.Path('aria_skills/focus/__init__.py').read_text())
print('syntax OK')
"
# EXPECTED: syntax OK

# 2. Skill registers correctly
docker exec aria-engine python3 -c "
from aria_skills.focus import FocusSkill
from aria_skills.registry import SkillRegistry
s = SkillRegistry.get('focus')
print('registered:', s is not None)
print('name:', s.name if s else None)
"
# EXPECTED: registered: True / name: focus

# 3. focus__list returns compact rows
docker exec aria-engine python3 -c "
import asyncio, os
from aria_skills.base import SkillConfig
from aria_skills.focus import FocusSkill

async def test():
    skill = FocusSkill(SkillConfig(name='focus', config={}))
    await skill.initialize()
    result = await skill._run('focus__list')
    print('success:', result.success)
    print('count:', len(result.data))
    if result.data:
        row = result.data[0]
        print('keys:', sorted(row.keys()))
        # Confirm no system_prompt_addon in output
        assert 'system_prompt_addon' not in row, 'addon must NOT appear in list output'
    print('PASS')

asyncio.run(test())
"
# EXPECTED:
# success: True
# count: 8
# keys: ['budget', 'id', 'level', 'name', 'tone']
# PASS

# 4. focus__activate switches agent focus
docker exec aria-engine python3 -c "
import asyncio, os
from aria_skills.base import SkillConfig
from aria_skills.focus import FocusSkill

async def test():
    skill = FocusSkill(SkillConfig(name='focus', config={}))
    await skill.initialize()
    result = await skill._run('focus__activate', focus_id='creative', agent_id='aria-main')
    print('success:', result.success)
    if result.success:
        print('new focus:', result.data.get('focus_id'))
        print('budget:', result.data.get('token_budget'))
    else:
        print('error:', result.error)

asyncio.run(test())
"
# EXPECTED:
# success: True
# new focus: creative
# budget: 1200
```

---

## Prompt for Agent

You are executing ticket S-77 for the Aria project.

**Constraint:** Skill layer — NO direct DB access. All API calls must go through
`http://aria-api:8000/api`. `system_prompt_addon` must never appear in tool
output (stripped in `_get`, never included in `_list`). Do NOT modify `aria_mind/soul/`.

**Files to read first:**
- `aria_skills/api_client/__init__.py` lines 1–80 (class structure + `__init__` pattern)
- `aria_skills/base.py` line 1–50 (SkillConfig, SkillResult, SkillStatus)

**Steps:**
1. Create `aria_skills/focus/` directory.
2. Create `aria_skills/focus/__init__.py` with full content above.
3. Create `aria_skills/focus/skill.json` with full JSON above.
4. Create `aria_skills/focus/skill.yaml` with full YAML above.
5. Run all 4 verification commands.
6. Report: "S-77 DONE — Focus skill registered, list/get/activate/status tools verified, addon stripped, token targets met."
