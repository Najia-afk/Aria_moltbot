# aria_skills/moltbook.py
"""
Moltbook social platform skill.

Handles posting, reading, and interacting with Moltbook.
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class MoltbookSkill(BaseSkill):
    """
    Skill for interacting with Moltbook social platform.
    
    Config:
        api_url: Base API URL
        auth: JWT token (use env:VAR_NAME for env vars)
        rate_limit:
            posts_per_hour: Max posts per hour
            posts_per_day: Max posts per day
    """
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._api_url = config.config.get("api_url", "https://moltbook.social/api")
        self._token: Optional[str] = None
        self._post_times: List[datetime] = []
    
    @property
    def name(self) -> str:
        return "moltbook"
    
    async def initialize(self) -> bool:
        """Initialize and validate Moltbook connection."""
        self._token = self._get_env_value("auth")
        
        if not self._token:
            self.logger.warning("No auth token configured")
            self._status = SkillStatus.UNAVAILABLE
            return False
        
        # Verify token works
        try:
            status = await self.health_check()
            return status == SkillStatus.AVAILABLE
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self._status = SkillStatus.ERROR
            return False
    
    async def health_check(self) -> SkillStatus:
        """Verify API connectivity and auth."""
        if not self._token:
            self._status = SkillStatus.UNAVAILABLE
            return self._status
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/v1/accounts/verify_credentials",
                    headers=self._headers,
                    timeout=10,
                )
                
                if response.status_code == 200:
                    self._status = SkillStatus.AVAILABLE
                elif response.status_code == 401:
                    self.logger.error("Invalid or expired token")
                    self._status = SkillStatus.UNAVAILABLE
                else:
                    self._status = SkillStatus.ERROR
                    
        except httpx.TimeoutException:
            self._status = SkillStatus.ERROR
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            self._status = SkillStatus.ERROR
        
        return self._status
    
    @property
    def _headers(self) -> dict:
        """Get request headers with auth."""
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
    
    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits."""
        rate_limit = self.config.rate_limit or {}
        posts_per_hour = rate_limit.get("posts_per_hour", 5)
        posts_per_day = rate_limit.get("posts_per_day", 20)
        
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        # Clean old entries
        self._post_times = [t for t in self._post_times if t > day_ago]
        
        # Check limits
        posts_last_hour = sum(1 for t in self._post_times if t > hour_ago)
        posts_last_day = len(self._post_times)
        
        if posts_last_hour >= posts_per_hour:
            self.logger.warning(f"Hourly rate limit reached: {posts_last_hour}/{posts_per_hour}")
            return False
        
        if posts_last_day >= posts_per_day:
            self.logger.warning(f"Daily rate limit reached: {posts_last_day}/{posts_per_day}")
            return False
        
        return True
    
    async def post_status(
        self,
        content: str,
        visibility: str = "public",
        reply_to: Optional[str] = None,
    ) -> SkillResult:
        """
        Post a new status to Moltbook.
        
        Args:
            content: Post content (max 500 chars)
            visibility: public, unlisted, private, direct
            reply_to: Post ID to reply to
            
        Returns:
            SkillResult with post data or error
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        if not self._check_rate_limit():
            self._status = SkillStatus.RATE_LIMITED
            return SkillResult.fail("Rate limit exceeded")
        
        # Truncate content if needed
        if len(content) > 500:
            content = content[:497] + "..."
            self.logger.info("Content truncated to 500 chars")
        
        payload = {
            "status": content,
            "visibility": visibility,
        }
        
        if reply_to:
            payload["in_reply_to_id"] = reply_to
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/v1/statuses",
                    json=payload,
                    headers=self._headers,
                    timeout=30,
                )
                
                if response.status_code in (200, 201):
                    data = response.json()
                    self._post_times.append(datetime.utcnow())
                    self._log_usage("post_status", True)
                    
                    return SkillResult.ok({
                        "post_id": data.get("id"),
                        "url": data.get("url"),
                        "content": content[:50] + "..." if len(content) > 50 else content,
                    })
                else:
                    self._log_usage("post_status", False)
                    return SkillResult.fail(f"HTTP {response.status_code}: {response.text}")
                    
        except Exception as e:
            self._log_usage("post_status", False)
            return SkillResult.fail(str(e))
    
    async def get_timeline(self, limit: int = 20) -> SkillResult:
        """
        Get home timeline.
        
        Args:
            limit: Number of posts to fetch
            
        Returns:
            SkillResult with list of posts
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/v1/timelines/home",
                    params={"limit": limit},
                    headers=self._headers,
                    timeout=30,
                )
                
                if response.status_code == 200:
                    posts = response.json()
                    self._log_usage("get_timeline", True)
                    
                    return SkillResult.ok([
                        {
                            "id": post.get("id"),
                            "content": post.get("content"),
                            "author": post.get("account", {}).get("username"),
                            "created_at": post.get("created_at"),
                        }
                        for post in posts
                    ])
                else:
                    self._log_usage("get_timeline", False)
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("get_timeline", False)
            return SkillResult.fail(str(e))
    
    async def get_notifications(self) -> SkillResult:
        """Get recent notifications."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/v1/notifications",
                    headers=self._headers,
                    timeout=30,
                )
                
                if response.status_code == 200:
                    self._log_usage("get_notifications", True)
                    return SkillResult.ok(response.json())
                else:
                    self._log_usage("get_notifications", False)
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("get_notifications", False)
            return SkillResult.fail(str(e))
