"""Sprint Manager Skill — Aria as Product Owner."""
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
            result = await self._api.get(f"/goals/sprint-summary?sprint={sprint}")
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            return SkillResult.fail(f"Failed to get sprint status: {e}")

    async def sprint_plan(self, sprint_name: str, goal_ids: list[str]) -> SkillResult:
        """Assign goals to a sprint."""
        results = []
        for gid in goal_ids:
            try:
                result = await self._api.patch(f"/goals/{gid}", data={
                    "sprint": sprint_name,
                    "board_column": "todo",
                })
                if not result:
                    raise Exception(result.error)
                results.append({"goal_id": gid, "success": True})
            except Exception as e:
                results.append({"goal_id": gid, "success": False, "error": str(e)})
        return SkillResult.ok({"sprint": sprint_name, "assigned": results})

    async def sprint_move_goal(self, goal_id: str, column: str, position: int = 0) -> SkillResult:
        """Move a goal to a different board column."""
        try:
            result = await self._api.patch(f"/goals/{goal_id}/move", data={
                "board_column": column,
                "position": position,
            })
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            return SkillResult.fail(f"Failed to move goal: {e}")

    async def sprint_report(self, sprint: str = "current") -> SkillResult:
        """Generate sprint progress report."""
        try:
            result = await self._api.get(f"/goals/board?sprint={sprint}")
            if not result:
                raise Exception(result.error)
            board = result.data
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
                result = await self._api.patch(f"/goals/{gid}/move", data={
                    "board_column": column,
                    "position": pos,
                })
                if not result:
                    raise Exception(result.error)
                results.append({"goal_id": gid, "position": pos, "success": True})
            except Exception as e:
                results.append({"goal_id": gid, "position": pos, "success": False, "error": str(e)})
        return SkillResult.ok({"column": column, "reordered": results})

    async def sprint_create(
        self,
        sprint_name: str,
        start_date: str = "",
        end_date: str = "",
        capacity: int = 0,
    ) -> SkillResult:
        """Create a new sprint with optional dates and capacity."""
        try:
            payload: dict = {"name": sprint_name}
            if start_date:
                payload["start_date"] = start_date
            if end_date:
                payload["end_date"] = end_date
            if capacity > 0:
                payload["capacity"] = capacity
            result = await self._api.post("/goals/sprints", data=payload)
            if not result:
                raise Exception(result.error)
            return SkillResult.ok(result.data)
        except Exception as e:
            return SkillResult.fail(f"Failed to create sprint: {e}")

    async def sprint_review(self, sprint: str = "current") -> SkillResult:
        """Generate a full retrospective review for a sprint."""
        try:
            result = await self._api.get(f"/goals/board?sprint={sprint}")
            if not result:
                raise Exception(result.error)
            board = result.data
        except Exception as e:
            return SkillResult.fail(f"Failed to get board for review: {e}")

        columns = board.get("columns", {})
        done_goals = columns.get("done", [])
        on_hold_goals = columns.get("on_hold", [])
        todo_goals = columns.get("todo", [])
        doing_goals = columns.get("doing", [])

        total = sum(len(v) for v in columns.values())
        done = len(done_goals)
        incomplete = len(todo_goals) + len(doing_goals)
        completion_pct = round(done / total * 100, 1) if total > 0 else 0

        review = {
            "sprint": sprint,
            "summary": {
                "total_goals": total,
                "completed": done,
                "incomplete": incomplete,
                "completion_pct": completion_pct,
            },
            "completed_goals": done_goals,
            "carried_over": todo_goals + doing_goals,
            "blocked": on_hold_goals,
            "retrospective": {
                "went_well": (
                    f"Completed {done} of {total} goals ({completion_pct}%)"
                    if total > 0
                    else "No goals tracked this sprint"
                ),
                "needs_improvement": (
                    f"{incomplete} goals were not completed"
                    if incomplete > 0
                    else "All goals completed"
                ),
                "action_items": (
                    [f"Carry over {incomplete} incomplete goals to next sprint"]
                    if incomplete > 0
                    else ["Plan next sprint goals"]
                ),
            },
        }
        return SkillResult.ok(review)
