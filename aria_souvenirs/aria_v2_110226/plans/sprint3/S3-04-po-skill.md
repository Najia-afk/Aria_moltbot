# S3-04: Create PO (Product Owner) Skill for Aria
**Epic:** E6 — Aria Skills | **Priority:** P1 | **Points:** 5 | **Phase:** 2

## Problem
Aria has no PO/sprint management capability. She can create/update goals, but cannot:
- Plan sprints (select goals for a sprint)
- Prioritize and reorder goals
- Track sprint progress and velocity
- Generate sprint reports
- Move goals between columns intelligently

## Root Cause
No sprint management skill exists. Goals are currently managed ad-hoc.

## Fix

### Step 1: Create skill directory and skill.json
**File: `aria_skills/sprint_manager/skill.json`** (NEW)
```json
{
  "name": "sprint_manager",
  "canonical": "aria-sprint-manager",
  "version": "1.0.0",
  "layer": 3,
  "category": "orchestrator",
  "description": "Sprint planning and goal management as Product Owner",
  "focus_affinity": ["orchestrator"],
  "dependencies": ["api_client"],
  "tools": [
    {"name": "sprint_plan", "description": "Plan a new sprint by selecting goals from backlog"},
    {"name": "sprint_status", "description": "Get compact sprint status (token-efficient)"},
    {"name": "sprint_move_goal", "description": "Move a goal to a different board column"},
    {"name": "sprint_report", "description": "Generate sprint progress report"},
    {"name": "sprint_prioritize", "description": "Reorder goals by priority within a column"}
  ]
}
```

### Step 2: Create skill implementation
**File: `aria_skills/sprint_manager/__init__.py`** (NEW)
```python
"""Sprint Manager Skill — Aria as Product Owner."""
from typing import Optional, Dict, Any
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class SprintManagerSkill(BaseSkill):
    """Manages sprints and goal board as Product Owner."""
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api = None

    @property
    def name(self) -> str:
        return "sprint_manager"

    async def initialize(self) -> bool:
        from aria_skills.api_client import get_api_client
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        if self._api:
            self._status = SkillStatus.AVAILABLE
        return self._status

    async def sprint_status(self, sprint: str = "current") -> SkillResult:
        """Get compact sprint status — optimized for minimal tokens."""
        result = await self._api.get(f"/goals/sprint-summary?sprint={sprint}")
        return result

    async def sprint_plan(self, sprint_name: str, goal_ids: list[str]) -> SkillResult:
        """Assign goals to a sprint."""
        results = []
        for gid in goal_ids:
            r = await self._api.patch(f"/goals/{gid}", data={
                "sprint": sprint_name,
                "board_column": "todo"
            })
            results.append({"goal_id": gid, "success": r.success})
        return SkillResult.ok({"sprint": sprint_name, "assigned": results})

    async def sprint_move_goal(self, goal_id: str, column: str, position: int = 0) -> SkillResult:
        """Move a goal to a different board column."""
        return await self._api.patch(f"/goals/{goal_id}/move", data={
            "board_column": column,
            "position": position,
        })

    async def sprint_report(self, sprint: str = "current") -> SkillResult:
        """Generate sprint progress report."""
        board = await self._api.get(f"/goals/board?sprint={sprint}")
        if not board.success:
            return board
        
        columns = board.data.get("columns", {})
        total = sum(len(v) for v in columns.values())
        done = len(columns.get("done", []))
        
        report = {
            "sprint": sprint,
            "total_goals": total,
            "done": done,
            "in_progress": len(columns.get("doing", [])),
            "todo": len(columns.get("todo", [])),
            "blocked": len(columns.get("on_hold", [])),
            "velocity": f"{done}/{total}" if total > 0 else "0/0",
            "completion_pct": round(done / total * 100, 1) if total > 0 else 0,
        }
        return SkillResult.ok(report)

    async def sprint_prioritize(self, column: str, goal_ids_ordered: list[str]) -> SkillResult:
        """Reorder goals within a column by position."""
        results = []
        for pos, gid in enumerate(goal_ids_ordered):
            r = await self._api.patch(f"/goals/{gid}/move", data={
                "board_column": column,
                "position": pos,
            })
            results.append({"goal_id": gid, "position": pos, "success": r.success})
        return SkillResult.ok({"column": column, "reordered": results})
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | Skill accesses DB through api_client only |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ❌ | No file writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S3-01** (Goal model fields) and **S3-02** (board API) must complete first.

## Verification
```bash
# 1. Skill files exist:
ls aria_skills/sprint_manager/skill.json aria_skills/sprint_manager/__init__.py
# EXPECTED: both files exist

# 2. Skill registers:
python3 -c "from aria_skills.sprint_manager import SprintManagerSkill; print('OK')"
# EXPECTED: OK

# 3. Skill appears in catalog:
python3 -c "from aria_skills.catalog import generate_catalog; c=generate_catalog(); print([s['name'] for s in c['skills'] if 'sprint' in s['name']])"
# EXPECTED: ['sprint_manager']

# 4. sprint_status returns compact data:
# (requires running API)
curl -s http://localhost:8000/api/goals/sprint-summary
# EXPECTED: compact JSON with status_counts and top_active
```

## Prompt for Agent
```
You are creating a Sprint Manager skill for Aria.

FILES TO READ FIRST:
- aria_skills/base.py (BaseSkill class, SkillConfig, SkillResult)
- aria_skills/registry.py (SkillRegistry.register decorator)
- aria_skills/api_client/__init__.py (AriaAPIClient methods)
- aria_skills/goals/ or similar (reference skill structure)
- A few other skill directories for skill.json format reference

STEPS:
1. Create aria_skills/sprint_manager/skill.json
2. Create aria_skills/sprint_manager/__init__.py with SprintManagerSkill
3. Implement: sprint_status, sprint_plan, sprint_move_goal, sprint_report, sprint_prioritize
4. All methods go through api_client (5-layer rule)
5. Run verification commands

CONSTRAINTS: 5-layer architecture — MUST use api_client for all DB access. No direct imports of SQLAlchemy.
```
