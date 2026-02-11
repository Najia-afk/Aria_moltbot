# S3-05: Update AriaAPIClient with Sprint Board Methods
**Epic:** E5 — Sprint Board | **Priority:** P1 | **Points:** 2 | **Phase:** 2

## Problem
`aria_skills/api_client/__init__.py` doesn't have methods for the new sprint board endpoints created in S3-02:
- `/goals/board`
- `/goals/archive`
- `/goals/{id}/move`
- `/goals/sprint-summary`
- `/goals/history`

## Root Cause
New endpoints were added in S3-02 but the API client wasn't updated to expose them.

## Fix

### File: `aria_skills/api_client/__init__.py`
Add methods after the existing goals section:

```python
    # ========================================
    # Sprint Board (S3-05)
    # ========================================
    async def get_goal_board(self, sprint: str = "current") -> SkillResult:
        """Get goals organized by board column."""
        return await self.get(f"/goals/board?sprint={sprint}")

    async def get_goal_archive(self, page: int = 1, limit: int = 25) -> SkillResult:
        """Get completed/cancelled goals archive."""
        return await self.get(f"/goals/archive?page={page}&limit={limit}")

    async def move_goal(self, goal_id: str, board_column: str, position: int = 0) -> SkillResult:
        """Move goal to a different board column."""
        return await self.patch(f"/goals/{goal_id}/move", data={
            "board_column": board_column,
            "position": position,
        })

    async def get_sprint_summary(self, sprint: str = "current") -> SkillResult:
        """Get lightweight sprint summary (token-efficient)."""
        return await self.get(f"/goals/sprint-summary?sprint={sprint}")

    async def get_goal_history(self, days: int = 14) -> SkillResult:
        """Get goal status distribution by day for charts."""
        return await self.get(f"/goals/history?days={days}")
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer | ✅ | api_client is Layer 4 (correct) |
| 2 | .env secrets | ❌ | No secrets |
| 3 | models.yaml | ❌ | No model names |
| 4 | Docker-first | ✅ | Test in Docker |
| 5 | aria_memories | ❌ | No file writes |
| 6 | No soul mod | ❌ | No soul files |

## Dependencies
- **S3-02** (board API endpoints) must complete first.

## Verification
```bash
# 1. Methods exist:
grep -n 'def get_goal_board\|def get_goal_archive\|def move_goal\|def get_sprint_summary\|def get_goal_history' aria_skills/api_client/__init__.py
# EXPECTED: 5 method definitions

# 2. Import test:
python3 -c "from aria_skills.api_client import AriaAPIClient; print([m for m in dir(AriaAPIClient) if 'board' in m or 'sprint' in m or 'archive' in m or 'history' in m])"
# EXPECTED: ['get_goal_archive', 'get_goal_board', 'get_goal_history', 'get_sprint_summary', 'move_goal']
```

## Prompt for Agent
```
You are adding sprint board methods to the Aria API client.

FILES TO READ FIRST:
- aria_skills/api_client/__init__.py (existing client — add after goals section)
- src/api/routers/goals.py (S3-02 endpoints to wrap)

STEPS:
1. Read api_client/__init__.py
2. Add 5 new methods after the Hourly Goals section
3. Use existing self.get() and self.patch() helpers
4. Run verification commands

CONSTRAINTS: api_client layer only. Use existing HTTP helpers.
```
