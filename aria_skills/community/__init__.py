# aria_skills/community.py
"""
🌐 Community Management Skill - Social Architect Focus

Provides community management and engagement for Aria's Social persona.
Handles community metrics, engagement tracking, and growth strategies.
"""
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import warnings

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@dataclass
class CommunityMember:
    """A community member profile."""
    id: str
    username: str
    joined_at: datetime
    engagement_score: float = 0.5
    posts: int = 0
    comments: int = 0
    reactions: int = 0
    tags: list[str] = field(default_factory=list)


@dataclass
class Campaign:
    """A community campaign or initiative."""
    id: str
    name: str
    goal: str
    start_date: datetime
    end_date: Optional[datetime] = None
    metrics: dict = field(default_factory=dict)
    status: str = "planned"  # planned, active, completed


@SkillRegistry.register
class CommunitySkill(BaseSkill):
    """
    Community management and growth.
    
    Capabilities:
    - Community health metrics
    - Member engagement tracking
    - Campaign management
    - Growth strategies
    - Content calendar
    """
    
    # Engagement types and weights
    ENGAGEMENT_WEIGHTS = {
        "post": 3.0,
        "comment": 1.5,
        "reaction": 0.5,
        "share": 2.0,
        "mention": 1.0,
    }
    
    @property
    def name(self) -> str:
        return "community"
    
    async def initialize(self) -> bool:
        """Initialize community skill."""
        warnings.warn(
            "community skill is deprecated, use social skill instead",
            DeprecationWarning,
            stacklevel=2,
        )
        self._members: dict[str, CommunityMember] = {}
        self._campaigns: dict[str, Campaign] = {}
        self._events: list[dict] = []
        self._status = SkillStatus.AVAILABLE
        self.logger.info("🌐 Community skill initialized")
        return True
    
    async def health_check(self) -> SkillStatus:
        """Check community skill availability."""
        return self._status
    
    async def track_member(
        self,
        username: str,
        tags: Optional[list[str]] = None
    ) -> SkillResult:
        """
        Add or update a community member.
        
        Args:
            username: Member username
            tags: Optional member tags (contributor, vip, etc.)
            
        Returns:
            SkillResult with member profile
        """
        try:
            member_id = f"mem_{username.lower().replace(' ', '_')}"
            
            if member_id in self._members:
                member = self._members[member_id]
                if tags:
                    member.tags = list(set(member.tags + tags))
            else:
                member = CommunityMember(
                    id=member_id,
                    username=username,
                    joined_at=datetime.now(timezone.utc),
                    tags=tags or []
                )
                self._members[member_id] = member
            
            return SkillResult.ok({
                "member_id": member_id,
                "username": member.username,
                "tags": member.tags,
                "engagement_score": round(member.engagement_score, 2),
                "activity": {
                    "posts": member.posts,
                    "comments": member.comments,
                    "reactions": member.reactions
                },
                "member_since": member.joined_at.isoformat()
            })
            
        except Exception as e:
            return SkillResult.fail(f"Member tracking failed: {str(e)}")
    
    async def record_engagement(
        self,
        username: str,
        engagement_type: str,
        content_id: Optional[str] = None
    ) -> SkillResult:
        """
        Record member engagement activity.
        
        Args:
            username: Member username
            engagement_type: Type (post, comment, reaction, share, mention)
            content_id: Optional related content ID
            
        Returns:
            SkillResult confirming engagement recorded
        """
        try:
            member_id = f"mem_{username.lower().replace(' ', '_')}"
            
            if member_id not in self._members:
                # Auto-create member
                await self.track_member(username)
            
            member = self._members[member_id]
            
            # Update counts
            if engagement_type == "post":
                member.posts += 1
            elif engagement_type == "comment":
                member.comments += 1
            elif engagement_type in ["reaction", "share", "mention"]:
                member.reactions += 1
            
            # Update engagement score
            weight = self.ENGAGEMENT_WEIGHTS.get(engagement_type, 1.0)
            member.engagement_score = min(member.engagement_score + weight * 0.1, 10.0)
            
            # Record event
            self._events.append({
                "type": engagement_type,
                "member": username,
                "content_id": content_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return SkillResult.ok({
                "member": username,
                "engagement_type": engagement_type,
                "new_engagement_score": round(member.engagement_score, 2),
                "total_engagements": member.posts + member.comments + member.reactions
            })
            
        except Exception as e:
            return SkillResult.fail(f"Engagement recording failed: {str(e)}")
    
    async def get_community_health(self) -> SkillResult:
        """
        Get overall community health metrics.
        
        Returns:
            SkillResult with health metrics
        """
        try:
            if not self._members:
                return SkillResult.ok({
                    "message": "No members tracked yet",
                    "recommendation": "Start tracking community members"
                })
            
            total_members = len(self._members)
            
            # Activity metrics
            total_posts = sum(m.posts for m in self._members.values())
            total_comments = sum(m.comments for m in self._members.values())
            total_reactions = sum(m.reactions for m in self._members.values())
            
            # Engagement distribution
            engagement_scores = [m.engagement_score for m in self._members.values()]
            avg_engagement = sum(engagement_scores) / len(engagement_scores)
            
            # Categorize members
            highly_engaged = len([m for m in self._members.values() if m.engagement_score > 5])
            moderately_engaged = len([m for m in self._members.values() if 2 <= m.engagement_score <= 5])
            low_engaged = len([m for m in self._members.values() if m.engagement_score < 2])
            
            # Calculate health score (0-100)
            health_score = min(
                (avg_engagement * 10) +
                (highly_engaged / total_members * 30) +
                (total_posts / total_members * 10),
                100
            )
            
            return SkillResult.ok({
                "total_members": total_members,
                "health_score": round(health_score, 1),
                "health_label": self._get_health_label(health_score),
                "activity_metrics": {
                    "total_posts": total_posts,
                    "total_comments": total_comments,
                    "total_reactions": total_reactions,
                    "posts_per_member": round(total_posts / total_members, 2)
                },
                "engagement_distribution": {
                    "highly_engaged": highly_engaged,
                    "moderately_engaged": moderately_engaged,
                    "low_engaged": low_engaged
                },
                "average_engagement_score": round(avg_engagement, 2),
                "recommendations": self._get_health_recommendations(health_score, total_members)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Health check failed: {str(e)}")
    
    async def identify_champions(self, limit: int = 10) -> SkillResult:
        """
        Identify top community champions.
        
        Args:
            limit: Number of champions to return
            
        Returns:
            SkillResult with champion list
        """
        try:
            if not self._members:
                return SkillResult.fail("No members to analyze")
            
            # Sort by engagement score
            sorted_members = sorted(
                self._members.values(),
                key=lambda m: m.engagement_score,
                reverse=True
            )[:limit]
            
            champions = [
                {
                    "username": m.username,
                    "engagement_score": round(m.engagement_score, 2),
                    "activity": {
                        "posts": m.posts,
                        "comments": m.comments,
                        "reactions": m.reactions
                    },
                    "tags": m.tags,
                    "member_since": m.joined_at.isoformat()
                }
                for m in sorted_members
            ]
            
            return SkillResult.ok({
                "champions": champions,
                "total_analyzed": len(self._members),
                "recommendation": "Consider rewarding and featuring these community champions"
            })
            
        except Exception as e:
            return SkillResult.fail(f"Champion identification failed: {str(e)}")
    
    async def create_campaign(
        self,
        name: str,
        goal: str,
        duration_days: int = 30
    ) -> SkillResult:
        """
        Create a community campaign.
        
        Args:
            name: Campaign name
            goal: Campaign goal description
            duration_days: Campaign duration
            
        Returns:
            SkillResult with campaign details
        """
        try:
            campaign_id = f"camp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            campaign = Campaign(
                id=campaign_id,
                name=name,
                goal=goal,
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc) + timedelta(days=duration_days),
                status="active"
            )
            
            self._campaigns[campaign_id] = campaign
            
            return SkillResult.ok({
                "campaign_id": campaign_id,
                "name": name,
                "goal": goal,
                "start_date": campaign.start_date.isoformat(),
                "end_date": campaign.end_date.isoformat(),
                "duration_days": duration_days,
                "status": campaign.status,
                "suggested_tactics": self._suggest_campaign_tactics(goal)
            })
            
        except Exception as e:
            return SkillResult.fail(f"Campaign creation failed: {str(e)}")
    
    async def get_growth_strategies(self, current_size: int = 0) -> SkillResult:
        """
        Get community growth strategies.
        
        Args:
            current_size: Current community size (or from tracked members)
            
        Returns:
            SkillResult with growth strategies
        """
        try:
            size = current_size or len(self._members)
            
            # Stage-appropriate strategies
            if size < 100:
                stage = "seed"
                strategies = [
                    {"tactic": "Personal outreach", "effort": "high", "impact": "high"},
                    {"tactic": "Founder-led engagement", "effort": "high", "impact": "high"},
                    {"tactic": "Quality over quantity content", "effort": "medium", "impact": "high"},
                    {"tactic": "Partner with complementary communities", "effort": "medium", "impact": "medium"},
                ]
            elif size < 1000:
                stage = "growth"
                strategies = [
                    {"tactic": "Ambassador program", "effort": "medium", "impact": "high"},
                    {"tactic": "Regular events/AMAs", "effort": "medium", "impact": "high"},
                    {"tactic": "User-generated content initiatives", "effort": "low", "impact": "high"},
                    {"tactic": "Newsletter/digest", "effort": "medium", "impact": "medium"},
                ]
            else:
                stage = "scale"
                strategies = [
                    {"tactic": "Sub-community creation", "effort": "high", "impact": "high"},
                    {"tactic": "Automated onboarding", "effort": "high", "impact": "high"},
                    {"tactic": "Moderator/leader program", "effort": "medium", "impact": "high"},
                    {"tactic": "Cross-platform presence", "effort": "medium", "impact": "medium"},
                ]
            
            return SkillResult.ok({
                "current_size": size,
                "growth_stage": stage,
                "strategies": strategies,
                "focus_areas": self._get_focus_areas(stage),
                "metrics_to_track": [
                    "Member growth rate",
                    "Active member percentage",
                    "Content creation rate",
                    "Retention rate"
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Strategy generation failed: {str(e)}")
    
    async def generate_content_calendar(
        self,
        days: int = 7,
        posts_per_day: int = 2
    ) -> SkillResult:
        """
        Generate a content calendar.
        
        Args:
            days: Number of days to plan
            posts_per_day: Target posts per day
            
        Returns:
            SkillResult with content calendar
        """
        try:
            content_types = [
                {"type": "educational", "emoji": "📚", "examples": ["Tutorial", "How-to", "Explainer"]},
                {"type": "engagement", "emoji": "💬", "examples": ["Poll", "Question", "Discussion"]},
                {"type": "showcase", "emoji": "✨", "examples": ["Member spotlight", "Project showcase", "Win celebration"]},
                {"type": "news", "emoji": "📰", "examples": ["Update", "Announcement", "Industry news"]},
                {"type": "entertainment", "emoji": "🎉", "examples": ["Meme", "Fun fact", "Behind the scenes"]},
            ]
            
            calendar = []
            start_date = datetime.now(timezone.utc)
            
            for day in range(days):
                date = start_date + timedelta(days=day)
                day_posts = []
                
                for post_num in range(posts_per_day):
                    content_type = random.choice(content_types)
                    day_posts.append({
                        "time_slot": "morning" if post_num == 0 else "evening",
                        "type": content_type["type"],
                        "emoji": content_type["emoji"],
                        "suggestion": random.choice(content_type["examples"])
                    })
                
                calendar.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "day_of_week": date.strftime("%A"),
                    "posts": day_posts
                })
            
            return SkillResult.ok({
                "calendar": calendar,
                "total_days": days,
                "posts_planned": days * posts_per_day,
                "content_mix": {ct["type"]: ct["emoji"] for ct in content_types},
                "tips": [
                    "Mix content types for variety",
                    "Post consistently at optimal times",
                    "Engage with comments promptly",
                    "Track which content performs best"
                ]
            })
            
        except Exception as e:
            return SkillResult.fail(f"Calendar generation failed: {str(e)}")
    
    # === Private Helper Methods ===
    
    def _get_health_label(self, score: float) -> str:
        """Get health label from score."""
        if score >= 80:
            return "Thriving 🌟"
        elif score >= 60:
            return "Healthy 💚"
        elif score >= 40:
            return "Growing 🌱"
        elif score >= 20:
            return "Needs Attention ⚠️"
        else:
            return "Critical 🚨"
    
    def _get_health_recommendations(self, score: float, size: int) -> list[str]:
        """Get recommendations based on health score."""
        recommendations = []
        
        if score < 40:
            recommendations.append("Increase engagement activities urgently")
            recommendations.append("Reach out to inactive members personally")
        
        if score < 60:
            recommendations.append("Launch an engagement campaign")
            recommendations.append("Identify and nurture potential champions")
        
        if size < 50:
            recommendations.append("Focus on quality members over quantity")
        
        if not recommendations:
            recommendations.append("Maintain current momentum")
            recommendations.append("Consider expanding to new platforms")
        
        return recommendations
    
    def _suggest_campaign_tactics(self, goal: str) -> list[str]:
        """Suggest tactics based on campaign goal."""
        goal_lower = goal.lower()
        
        if "grow" in goal_lower or "member" in goal_lower:
            return ["Referral incentives", "Cross-promotion", "Content marketing"]
        elif "engage" in goal_lower or "active" in goal_lower:
            return ["Daily challenges", "Discussion prompts", "Live events"]
        elif "retain" in goal_lower or "churn" in goal_lower:
            return ["Win-back campaigns", "Exclusive benefits", "Feedback collection"]
        else:
            return ["Define clear milestones", "Create shareable moments", "Celebrate progress"]
    
    def _get_focus_areas(self, stage: str) -> list[str]:
        """Get focus areas by growth stage."""
        areas = {
            "seed": ["Finding your first 10 passionate members", "Defining community values", "Building personal connections"],
            "growth": ["Scaling engagement", "Building traditions", "Identifying leaders"],
            "scale": ["Maintaining culture", "Delegating leadership", "Automating where appropriate"],
        }
        return areas.get(stage, areas["seed"])


# Skill instance factory
def create_skill(config: SkillConfig) -> CommunitySkill:
    """Create a community skill instance."""
    return CommunitySkill(config)
