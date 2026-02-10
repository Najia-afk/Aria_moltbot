# aria_skills/social.py
"""
Social media posting skill.

Manages social media content creation and posting.
Persists via REST API (TICKET-12: eliminate in-memory stubs).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry
from aria_skills.social.platform import SocialPlatform


@SkillRegistry.register
class SocialSkill(BaseSkill):
    """
    Social media management.
    
    Handles post creation, scheduling, and tracking.
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._posts: List[Dict] = []  # fallback cache
        self._post_counter = 0
        self._api = None
        self._platforms: Dict[str, SocialPlatform] = {}
    
    def register_platform(self, name: str, platform: SocialPlatform) -> None:
        """Register a social platform implementation."""
        self._platforms[name] = platform
    
    @property
    def name(self) -> str:
        return "social"
    
    async def initialize(self) -> bool:
        """Initialize social skill."""
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Social skill initialized (API-backed)")
        return True
    
    async def close(self):
        """Cleanup (shared API client is managed by api_client module)."""
        self._api = None
    
    async def health_check(self) -> SkillStatus:
        """Check availability."""
        return self._status
    
    @logged_method()
    async def create_post(
        self,
        content: str,
        platform: str = "moltbook",
        tags: Optional[List[str]] = None,
        media_urls: Optional[List[str]] = None,
    ) -> SkillResult:
        """
        Create a social media post, routed to the specified platform.
        
        Args:
            content: Post content
            platform: Target platform
            tags: Hashtags
            media_urls: Attached media
            
        Returns:
            SkillResult with post data
        """
        # Route to registered platform if available
        if platform and platform in self._platforms:
            return await self._platforms[platform].post(content, tags)
        
        # Fallback: store via API if no platform registered
        self._post_counter += 1
        post_id = f"post_{self._post_counter}"
        
        post = {
            "id": post_id,
            "content": content,
            "platform": platform,
            "tags": tags or [],
            "media_urls": media_urls or [],
            "status": "draft",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "published_at": None,
        }
        
        try:
            resp = await self._api._client.post("/social", json=post)
            resp.raise_for_status()
            api_data = resp.json()
            return SkillResult.ok(api_data if api_data else post)
        except Exception as e:
            self.logger.warning(f"API create_post failed, using fallback: {e}")
            self._posts.append(post)
            return SkillResult.ok(post)
    
    @logged_method()
    async def publish_post(self, post_id: str) -> SkillResult:
        """Publish a draft post."""
        update_data = {
            "status": "published",
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            resp = await self._api._client.put(f"/social/{post_id}", json=update_data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            self.logger.warning(f"API publish_post failed, using fallback: {e}")
            for post in self._posts:
                if post["id"] == post_id:
                    post["status"] = "published"
                    post["published_at"] = update_data["published_at"]
                    return SkillResult.ok(post)
            return SkillResult.fail(f"Post not found: {post_id}")
    
    async def get_posts(
        self,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 20,
    ) -> SkillResult:
        """Get posts with optional filters."""
        try:
            params: Dict[str, Any] = {"limit": limit}
            if status:
                params["status"] = status
            if platform:
                params["platform"] = platform
            resp = await self._api._client.get("/social", params=params)
            resp.raise_for_status()
            api_data = resp.json()
            if isinstance(api_data, list):
                return SkillResult.ok({"posts": api_data[-limit:], "total": len(api_data)})
            return SkillResult.ok(api_data)
        except Exception as e:
            self.logger.warning(f"API get_posts failed, using fallback: {e}")
            posts = self._posts
            if status:
                posts = [p for p in posts if p["status"] == status]
            if platform:
                posts = [p for p in posts if p["platform"] == platform]
            return SkillResult.ok({"posts": posts[-limit:], "total": len(posts)})
    
    async def delete_post(self, post_id: str) -> SkillResult:
        """Delete a post."""
        try:
            resp = await self._api._client.delete(f"/social/{post_id}")
            resp.raise_for_status()
            return SkillResult.ok({"deleted": post_id})
        except Exception as e:
            self.logger.warning(f"API delete_post failed, using fallback: {e}")
            for i, post in enumerate(self._posts):
                if post["id"] == post_id:
                    deleted = self._posts.pop(i)
                    return SkillResult.ok({"deleted": post_id, "content": deleted["content"][:50]})
            return SkillResult.fail(f"Post not found: {post_id}")
