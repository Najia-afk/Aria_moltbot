# aria_skills/community/__init__.py
"""
Community management and growth skill.

Tracks community members, engagement, and generates growth strategies
for Aria's Social Architect persona.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

GROWTH_STRATEGIES = [
    {"name": "Content-first", "description": "Create valuable content that attracts and retains members", "actions": ["Create a content calendar", "Share unique insights weekly", "Invite guest contributors"]},
    {"name": "Ambassador program", "description": "Empower top members to recruit and mentor", "actions": ["Identify top 5 contributors", "Create ambassador roles", "Provide exclusive perks"]},
    {"name": "Event-driven", "description": "Host regular events to build engagement", "actions": ["Weekly AMA sessions", "Monthly workshops", "Quarterly hackathons"]},
    {"name": "Cross-pollination", "description": "Partner with adjacent communities", "actions": ["Identify 3 complementary communities", "Propose joint events", "Share audiences"]},
    {"name": "Onboarding funnel", "description": "Create a smooth path from newcomer to contributor", "actions": ["Welcome message automation", "Starter tasks for new members", "Mentorship pairing"]},
]


@SkillRegistry.register
class CommunitySkill(BaseSkill):
    """Community management and growth tracking."""

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="community"))
        self._members: dict[str, dict] = {}
        self._engagements: list[dict] = []
        self._campaigns: dict[str, dict] = {}
        self._api = None

    @property
    def name(self) -> str:
        return "community"

    async def initialize(self) -> bool:
        try:
            self._api = await get_api_client()
        except Exception as e:
            self.logger.info(f"API unavailable, using in-memory cache only: {e}")
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Community skill initialized")
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    @logged_method()
    async def track_member(
        self, member_id: str = "", name: str = "", platform: str = "discord",
        role: str = "member", **kwargs
    ) -> SkillResult:
        """Track a community member."""
        member_id = member_id or kwargs.get("member_id", str(uuid.uuid4())[:8])
        name = name or kwargs.get("name", "Anonymous")
        member_data = {
            "id": member_id,
            "name": name,
            "platform": platform,
            "role": role,
            "engagement_count": 0,
            "joined_at": datetime.now(timezone.utc).isoformat(),
        }
        self._members[member_id] = member_data

        await self._persist_activity("community_member_tracked", {
            "member": member_data,
        })

        return SkillResult.ok({
            "member": self._members[member_id],
            "total_members": len(self._members),
        })

    @logged_method()
    async def record_engagement(
        self, member_id: str = "", action: str = "message",
        content: str = "", platform: str = "discord", **kwargs
    ) -> SkillResult:
        """Record a community engagement event."""
        member_id = member_id or kwargs.get("member_id", "")
        action = action or kwargs.get("action", "message")
        entry = {
            "member_id": member_id,
            "action": action,
            "content": content[:200] if content else "",
            "platform": platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._engagements.append(entry)
        if member_id in self._members:
            self._members[member_id]["engagement_count"] += 1

        await self._persist_activity("community_engagement_recorded", {
            "engagement": entry,
        })

        return SkillResult.ok({
            "engagement": entry,
            "total_engagements": len(self._engagements),
        })

    @logged_method()
    async def get_community_health(self, **kwargs) -> SkillResult:
        """Get community health metrics."""
        total = len(self._members)
        active = sum(1 for m in self._members.values() if m["engagement_count"] > 0)
        return SkillResult.ok({
            "total_members": total,
            "active_members": active,
            "engagement_rate": round(active / max(total, 1), 2),
            "total_engagements": len(self._engagements),
            "campaigns_active": sum(1 for c in self._campaigns.values() if c.get("status") == "active"),
            "health_score": round(min(active / max(total * 0.3, 1), 1.0), 2),
        })

    @logged_method()
    async def identify_champions(self, top_n: int = 5, **kwargs) -> SkillResult:
        """Identify top community champions by engagement."""
        top_n = top_n or kwargs.get("top_n", 5)
        sorted_members = sorted(
            self._members.values(),
            key=lambda m: m["engagement_count"],
            reverse=True,
        )[:top_n]
        return SkillResult.ok({
            "champions": sorted_members,
            "total_members": len(self._members),
            "criteria": "engagement_count",
        })

    @logged_method()
    async def create_campaign(
        self, name: str = "", description: str = "", goal: str = "",
        target_metric: str = "engagement", **kwargs
    ) -> SkillResult:
        """Create a community growth campaign."""
        name = name or kwargs.get("name", "Growth Campaign")
        campaign_id = str(uuid.uuid4())[:8]
        campaign_data = {
            "id": campaign_id,
            "name": name,
            "description": description or kwargs.get("description", ""),
            "goal": goal or kwargs.get("goal", ""),
            "target_metric": target_metric,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._campaigns[campaign_id] = campaign_data

        await self._persist_activity("community_campaign_created", {
            "campaign": campaign_data,
        })

        return SkillResult.ok({
            "campaign": self._campaigns[campaign_id],
            "total_campaigns": len(self._campaigns),
        })

    @logged_method()
    async def get_growth_strategies(self, focus: str = "", **kwargs) -> SkillResult:
        """Get community growth strategies."""
        strategies = GROWTH_STRATEGIES
        focus = focus or kwargs.get("focus", "")
        if focus:
            strategies = [s for s in strategies if focus.lower() in s["name"].lower() or focus.lower() in s["description"].lower()] or strategies
        return SkillResult.ok({
            "strategies": strategies,
            "current_members": len(self._members),
            "recommendation": strategies[0]["name"] if strategies else "Content-first",
        })

    @logged_method()
    async def generate_content_calendar(
        self, weeks: int = 4, platform: str = "discord", **kwargs
    ) -> SkillResult:
        """Generate a content calendar for community engagement."""
        weeks = weeks or kwargs.get("weeks", 4)
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        content_types = [
            "Discussion prompt", "Tutorial/How-to", "Community spotlight",
            "Poll/Survey", "Resource share", "AMA/Q&A", "Weekly roundup",
        ]
        calendar = []
        for week in range(1, weeks + 1):
            week_plan = {"week": week, "posts": []}
            for i, day in enumerate(days):
                week_plan["posts"].append({
                    "day": day,
                    "content_type": content_types[(week * 5 + i) % len(content_types)],
                    "platform": platform,
                })
            calendar.append(week_plan)
        return SkillResult.ok({
            "calendar": calendar,
            "weeks": weeks,
            "platform": platform,
            "posts_per_week": len(days),
        })

    # === API Persistence ===

    async def _persist_activity(self, action: str, details: dict) -> None:
        """Best-effort API persistence. Disables on failure to avoid slowdowns."""
        if not self._api:
            return
        try:
            import asyncio
            await asyncio.wait_for(
                self._api.post("/activities", data={
                    "action": action,
                    "skill": self.name,
                    "details": details,
                    "success": True,
                }),
                timeout=5.0,
            )
        except Exception:
            self.logger.debug("API persistence disabled (API unreachable)")
            self._api = None
