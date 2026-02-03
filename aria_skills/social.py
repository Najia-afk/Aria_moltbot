# aria_skills/social.py
"""
Social media posting and management skill.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry

logger = logging.getLogger("aria.skills.social")


@SkillRegistry.register
class SocialSkill(BaseSkill):
    """
    Skill for managing social media posts.
    """
    
    name = "social"
    description = "Manage Aria's social presence on Moltbook and other platforms"
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self.api_base = config.config.get("api_url", "http://aria-api:8000")
    
    async def initialize(self) -> bool:
        """Initialize the skill."""
        status = await self.health_check()
        return status == SkillStatus.AVAILABLE
    
    async def health_check(self) -> SkillStatus:
        """Check if the API is accessible."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.api_base}/health", timeout=5.0)
                if response.status_code == 200:
                    return SkillStatus.AVAILABLE
                return SkillStatus.ERROR
        except Exception as e:
            logger.error(f"Social API health check failed: {e}")
            return SkillStatus.UNAVAILABLE
    
    async def post(
        self,
        content: str,
        platform: str = "moltbook",
        mood: Optional[str] = None,
        tags: Optional[List[str]] = None,
        visibility: str = "public"
    ) -> SkillResult:
        """
        Create a social media post.
        
        Args:
            content: Post content text
            platform: Target platform (moltbook, twitter, mastodon)
            mood: Mood/emotion tag
            tags: Hashtags or topics
            visibility: Post visibility (public, private, followers)
        """
        try:
            payload = {
                "content": content,
                "platform": platform,
                "visibility": visibility,
            }
            if mood:
                payload["mood"] = mood
            if tags:
                payload["tags"] = tags
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/social",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def list(
        self,
        platform: Optional[str] = None,
        limit: int = 20
    ) -> SkillResult:
        """
        Get recent social posts.
        
        Args:
            platform: Filter by platform
            limit: Maximum posts to return
        """
        try:
            params = {"limit": limit}
            if platform:
                params["platform"] = platform
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_base}/social",
                    params=params,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to list posts: {e}")
            return SkillResult(success=False, error=str(e))
    
    async def schedule(
        self,
        content: str,
        platform: str,
        scheduled_for: str,
        **kwargs
    ) -> SkillResult:
        """
        Schedule a post for later.
        
        Args:
            content: Post content
            platform: Target platform
            scheduled_for: ISO timestamp for posting
        """
        try:
            payload = {
                "content": content,
                "platform": platform,
                "scheduled_for": scheduled_for,
                **kwargs
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_base}/social",
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                return SkillResult(success=True, data=response.json())
        except Exception as e:
            logger.error(f"Failed to schedule post: {e}")
            return SkillResult(success=False, error=str(e))
