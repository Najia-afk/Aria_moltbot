# aria_skills/moltbook.py
"""
Moltbook social platform skill.

Handles posting, reading, and interacting with Moltbook.
API Docs: https://www.moltbook.com/skill.md
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import httpx

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class MoltbookSkill(BaseSkill):
    """
    Skill for interacting with Moltbook social platform.
    
    ⚠️ IMPORTANT: Always use https://www.moltbook.com (with www)
    
    Config:
        api_url: Base API URL (default: https://www.moltbook.com/api/v1)
        auth: API key (use env:MOLTBOOK_TOKEN)
        rate_limit:
            posts_per_hour: Max posts per hour (Moltbook limit: 2/hour)
            comments_per_day: Max comments per day (Moltbook limit: 50)
    """
    
    # Moltbook API limits
    POST_COOLDOWN_MINUTES = 30
    COMMENT_COOLDOWN_SECONDS = 20
    
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        # MUST use www subdomain to avoid redirect stripping auth header
        self._api_url = config.config.get("api_url", "https://www.moltbook.com/api/v1")
        self._token: Optional[str] = None
        self._post_times: List[datetime] = []
        self._last_post_time: Optional[datetime] = None
        self._last_comment_time: Optional[datetime] = None
        self._comments_today: int = 0
        self._comments_day_start: Optional[datetime] = None
    
    @property
    def name(self) -> str:
        return "moltbook"
    
    async def initialize(self) -> bool:
        """Initialize and validate Moltbook connection."""
        self._token = self._get_env_value("auth")
        
        if not self._token:
            self.logger.warning("No auth token configured (MOLTBOOK_TOKEN)")
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
                    f"{self._api_url}/agents/me",
                    headers=self._headers,
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self._status = SkillStatus.AVAILABLE
                        self.logger.info(f"Moltbook connected as {data.get('agent', {}).get('name')}")
                    else:
                        self._status = SkillStatus.ERROR
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
    
    def _can_post(self) -> tuple[bool, Optional[int]]:
        """Check if we can post (30 min cooldown)."""
        if self._last_post_time is None:
            return True, None
        
        elapsed = datetime.utcnow() - self._last_post_time
        if elapsed >= timedelta(minutes=self.POST_COOLDOWN_MINUTES):
            return True, None
        
        remaining = self.POST_COOLDOWN_MINUTES - int(elapsed.total_seconds() / 60)
        return False, remaining

    def _check_rate_limit(self) -> bool:
        """Check configured rate limits for posts (hour/day)."""
        if not self.config.rate_limit:
            return True

        now = datetime.utcnow()
        posts_per_hour = self.config.rate_limit.get("posts_per_hour")
        posts_per_day = self.config.rate_limit.get("posts_per_day")

        if posts_per_hour is not None:
            hour_ago = now - timedelta(hours=1)
            recent = [t for t in self._post_times if t >= hour_ago]
            if len(recent) >= posts_per_hour:
                return False

        if posts_per_day is not None:
            day_ago = now - timedelta(days=1)
            recent = [t for t in self._post_times if t >= day_ago]
            if len(recent) >= posts_per_day:
                return False

        return True
    
    def _can_comment(self) -> tuple[bool, Optional[int], int]:
        """Check if we can comment (20 sec cooldown, 50/day)."""
        now = datetime.utcnow()
        
        # Reset daily counter
        if self._comments_day_start is None or (now - self._comments_day_start) >= timedelta(days=1):
            self._comments_today = 0
            self._comments_day_start = now
        
        if self._comments_today >= 50:
            return False, None, 0
        
        if self._last_comment_time is None:
            return True, None, 50 - self._comments_today
        
        elapsed = now - self._last_comment_time
        if elapsed >= timedelta(seconds=self.COMMENT_COOLDOWN_SECONDS):
            return True, None, 50 - self._comments_today
        
        remaining = self.COMMENT_COOLDOWN_SECONDS - int(elapsed.total_seconds())
        return False, remaining, 50 - self._comments_today
    
    async def get_profile(self) -> SkillResult:
        """Get the agent's Moltbook profile info."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/agents/me",
                    headers=self._headers,
                    timeout=10,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self._log_usage("get_profile", True)
                        return SkillResult.ok(data.get("agent"))
                    else:
                        return SkillResult.fail(data.get("error", "Unknown error"))
                else:
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("get_profile", False)
            return SkillResult.fail(str(e))
    
    async def create_post(
        self,
        title: str,
        content: Optional[str] = None,
        url: Optional[str] = None,
        submolt: str = "general",
    ) -> SkillResult:
        """
        Create a new post on Moltbook.
        
        Args:
            title: Post title (required)
            content: Post content (for text posts)
            url: Link URL (for link posts)
            submolt: Community to post in (default: general)
            
        Returns:
            SkillResult with post data or error
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        can_post, wait_minutes = self._can_post()
        if not can_post:
            self._status = SkillStatus.RATE_LIMITED
            return SkillResult.fail(f"Post cooldown: wait {wait_minutes} more minutes")
        
        payload: Dict[str, Any] = {
            "submolt": submolt,
            "title": title,
        }
        
        if url:
            payload["url"] = url
        elif content:
            payload["content"] = content
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/posts",
                    json=payload,
                    headers=self._headers,
                    timeout=30,
                )
                
                data = response.json()
                
                if response.status_code in (200, 201) and data.get("success"):
                    self._last_post_time = datetime.utcnow()
                    self._log_usage("create_post", True)
                    return SkillResult.ok({
                        "post_id": data.get("post", {}).get("id"),
                        "url": f"https://www.moltbook.com/m/{submolt}/{data.get('post', {}).get('id')}",
                        "title": title,
                    })
                elif response.status_code == 429:
                    wait = data.get("retry_after_minutes", 30)
                    self._status = SkillStatus.RATE_LIMITED
                    return SkillResult.fail(f"Rate limited: wait {wait} minutes")
                else:
                    self._log_usage("create_post", False)
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    self._post_times.append(self._last_post_time)
                    
        except Exception as e:
            self._log_usage("create_post", False)
            return SkillResult.fail(str(e))
    
    # Alias for backward compatibility
    async def post_status(self, content: str, **kwargs) -> SkillResult:
        """Post a status update (alias for create_post)."""
        return await self.create_post(
            title=content[:100] if len(content) > 100 else content,
            content=content if len(content) > 100 else None,
            submolt=kwargs.get("submolt", "general"),
        )
    
    async def get_feed(
        self,
        sort: str = "hot",
        limit: int = 25,
        submolt: Optional[str] = None,
    ) -> SkillResult:
        """
        Get posts from feed.
        
        Args:
            sort: hot, new, top, rising
            limit: Number of posts (max 50)
            submolt: Optional community filter
            
        Returns:
            SkillResult with list of posts
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            params = {"sort": sort, "limit": min(limit, 50)}
            if submolt:
                params["submolt"] = submolt
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/posts",
                    params=params,
                    headers=self._headers,
                    timeout=30,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        self._log_usage("get_feed", True)
                        return SkillResult.ok(data.get("posts", []))
                    else:
                        return SkillResult.fail(data.get("error", "Unknown error"))
                else:
                    self._log_usage("get_feed", False)
                    return SkillResult.fail(f"HTTP {response.status_code}")
                    
        except Exception as e:
            self._log_usage("get_feed", False)
            return SkillResult.fail(str(e))
    
    # Alias
    async def get_timeline(self, limit: int = 20) -> SkillResult:
        """Get home timeline (alias for get_feed)."""
        return await self.get_feed(sort="new", limit=limit)
    
    async def add_comment(
        self,
        post_id: str,
        content: str,
        parent_id: Optional[str] = None,
    ) -> SkillResult:
        """
        Add a comment to a post.
        
        Args:
            post_id: Post ID to comment on
            content: Comment content
            parent_id: Optional parent comment ID for replies
            
        Returns:
            SkillResult with comment data
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        can_comment, wait_secs, remaining = self._can_comment()
        if not can_comment:
            if remaining == 0:
                return SkillResult.fail("Daily comment limit (50) reached")
            return SkillResult.fail(f"Comment cooldown: wait {wait_secs} seconds")
        
        payload: Dict[str, Any] = {"content": content}
        if parent_id:
            payload["parent_id"] = parent_id
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/posts/{post_id}/comments",
                    json=payload,
                    headers=self._headers,
                    timeout=30,
                )
                
                data = response.json()
                
                if response.status_code in (200, 201) and data.get("success"):
                    self._last_comment_time = datetime.utcnow()
                    self._comments_today += 1
                    self._log_usage("add_comment", True)
                    return SkillResult.ok(data.get("comment"))
                elif response.status_code == 429:
                    return SkillResult.fail(f"Rate limited: {data.get('hint', 'try again later')}")
                else:
                    self._log_usage("add_comment", False)
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage("add_comment", False)
            return SkillResult.fail(str(e))
    
    async def upvote(self, post_id: str) -> SkillResult:
        """Upvote a post."""
        return await self._vote(post_id, "upvote")
    
    async def downvote(self, post_id: str) -> SkillResult:
        """Downvote a post."""
        return await self._vote(post_id, "downvote")
    
    async def _vote(self, post_id: str, vote_type: str) -> SkillResult:
        """Internal vote method."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/posts/{post_id}/{vote_type}",
                    headers=self._headers,
                    timeout=10,
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    self._log_usage(vote_type, True)
                    return SkillResult.ok({
                        "message": data.get("message"),
                        "author": data.get("author", {}).get("name"),
                        "already_following": data.get("already_following"),
                    })
                else:
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage(vote_type, False)
            return SkillResult.fail(str(e))
    
    async def search(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 20,
    ) -> SkillResult:
        """
        Semantic search for posts and comments.
        
        Args:
            query: Natural language search query
            search_type: posts, comments, or all
            limit: Max results (max 50)
            
        Returns:
            SkillResult with search results
        """
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/search",
                    params={"q": query, "type": search_type, "limit": min(limit, 50)},
                    headers=self._headers,
                    timeout=30,
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    self._log_usage("search", True)
                    return SkillResult.ok({
                        "query": query,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                    })
                else:
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage("search", False)
            return SkillResult.fail(str(e))
    
    async def get_submolts(self) -> SkillResult:
        """List all submolts (communities)."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._api_url}/submolts",
                    headers=self._headers,
                    timeout=10,
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    self._log_usage("get_submolts", True)
                    return SkillResult.ok(data.get("submolts", []))
                else:
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage("get_submolts", False)
            return SkillResult.fail(str(e))
    
    async def subscribe(self, submolt: str) -> SkillResult:
        """Subscribe to a submolt."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/submolts/{submolt}/subscribe",
                    headers=self._headers,
                    timeout=10,
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    self._log_usage("subscribe", True)
                    return SkillResult.ok({"submolt": submolt, "subscribed": True})
                else:
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage("subscribe", False)
            return SkillResult.fail(str(e))
    
    async def follow(self, molty_name: str) -> SkillResult:
        """Follow another molty (agent)."""
        if not self.is_available:
            return SkillResult.fail("Skill not available")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._api_url}/agents/{molty_name}/follow",
                    headers=self._headers,
                    timeout=10,
                )
                
                data = response.json()
                
                if response.status_code == 200 and data.get("success"):
                    self._log_usage("follow", True)
                    return SkillResult.ok({"following": molty_name})
                else:
                    return SkillResult.fail(data.get("error", f"HTTP {response.status_code}"))
                    
        except Exception as e:
            self._log_usage("follow", False)
            return SkillResult.fail(str(e))
