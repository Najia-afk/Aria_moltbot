"""Community skill — engagement tracking and growth orchestration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class CommunitySkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._members: dict[str, dict] = {}
        self._engagement: list[dict] = []
        self._campaigns: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "community"

    async def initialize(self) -> bool:
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    async def track_member(self, username: str, tags: list[str] | None = None) -> SkillResult:
        now = datetime.now(timezone.utc).isoformat()
        member = self._members.get(username, {"username": username, "created_at": now})
        member["tags"] = sorted(set((member.get("tags") or []) + (tags or [])))
        member["updated_at"] = now
        self._members[username] = member
        return SkillResult.ok(member)

    async def record_engagement(
        self,
        username: str,
        engagement_type: str,
        content_id: str | None = None,
    ) -> SkillResult:
        if username not in self._members:
            await self.track_member(username)
        event = {
            "event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "username": username,
            "engagement_type": engagement_type,
            "content_id": content_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._engagement.append(event)
        return SkillResult.ok(event)

    async def get_community_health(self) -> SkillResult:
        member_count = len(self._members)
        engagement_count = len(self._engagement)
        last_24h = [e for e in self._engagement][-200:]
        return SkillResult.ok({
            "members": member_count,
            "engagement_events": engagement_count,
            "recent_events": len(last_24h),
            "status": "healthy" if member_count or engagement_count else "idle",
        })

    async def identify_champions(self, limit: int = 10) -> SkillResult:
        scores: dict[str, int] = {}
        for e in self._engagement:
            scores[e["username"]] = scores.get(e["username"], 0) + 1
        champions = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        return SkillResult.ok({"champions": [{"username": name, "score": score} for name, score in champions]})

    async def create_campaign(self, name: str, goal: str, duration_days: int = 30) -> SkillResult:
        campaign_id = f"camp-{uuid.uuid4().hex[:8]}"
        campaign = {
            "campaign_id": campaign_id,
            "name": name,
            "goal": goal,
            "duration_days": duration_days,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._campaigns[campaign_id] = campaign
        return SkillResult.ok(campaign)

    async def get_growth_strategies(self, current_size: int | None = None) -> SkillResult:
        size = current_size or len(self._members)
        if size < 100:
            recs = ["Launch onboarding challenge", "Weekly founder AMA", "Shareable referral card"]
        elif size < 1000:
            recs = ["Community ambassadors", "Segmented content themes", "Monthly leaderboard"]
        else:
            recs = ["Chapter-based moderation", "Regional events", "Automated lifecycle messaging"]
        return SkillResult.ok({"current_size": size, "strategies": recs})

    async def generate_content_calendar(self, days: int = 7, posts_per_day: int = 2) -> SkillResult:
        plan = []
        for day in range(1, max(1, days) + 1):
            for slot in range(1, max(1, posts_per_day) + 1):
                plan.append({"day": day, "slot": slot, "theme": f"community-story-{(day + slot) % 5}"})
        return SkillResult.ok({"days": days, "posts_per_day": posts_per_day, "calendar": plan})
