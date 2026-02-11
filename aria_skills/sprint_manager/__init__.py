"""Sprint Manager Skill — Aria as Product Owner."""
from typing import Optional
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
        try:
            resp = await self._api._client.get(f"/goals/sprint-summary?sprint={sprint}")
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to get sprint status: {e}")

    async def sprint_plan(self, sprint_name: str, goal_ids: list[str]) -> SkillResult:
        """Assign goals to a sprint."""
        results = []
        for gid in goal_ids:
            try:
                resp = await self._api._client.patch(f"/goals/{gid}", json={
                    "sprint": sprint_name,
                    "board_column": "todo",
                })
                resp.raise_for_status()
                results.append({"goal_id": gid, "success": True})
            except Exception as e:
                results.append({"goal_id": gid, "success": False, "error": str(e)})
        return SkillResult.ok({"sprint": sprint_name, "assigned": results})

    async def sprint_move_goal(self, goal_id: str, column: str, position: int = 0) -> SkillResult:
        """Move a goal to a different board column."""
        try:
            resp = await self._api._client.patch(f"/goals/{goal_id}/move", json={
                "board_column": column,
                "position": position,
            })
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to move goal: {e}")

    async def sprint_report(self, sprint: str = "current") -> SkillResult:
        """Generate sprint progress report."""
        try:
            resp = await self._api._client.get(f"/goals/board?sprint={sprint}")
            resp.raise_for_status()
            board = resp.json()
        except Exception as e:
            return SkillResult.fail(f"Failed to get board: {e}")

        columns = board.get("columns", {})
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
            try:
                resp = await self._api._client.patch(f"/goals/{gid}/move", json={
                    "board_column": column,
                    "position": pos,
                })
                resp.raise_for_status()
                results.append({"goal_id": gid, "position": pos, "success": True})
            except Exception as e:
                results.append({"goal_id": gid, "position": pos, "success": False, "error": str(e)})
        return SkillResult.ok({"column": column, "reordered": results})
