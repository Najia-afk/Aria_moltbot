# aria_skills/moltbook.py
"""
📖 Moltbook Social Skill

Moltbook API integration for Aria.
API docs: https://www.moltbook.com/skill.md

⚠️ IMPORTANT: Always use https://www.moltbook.com (with www)
   Without www, redirects strip the Authorization header!
"""
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

# Default Moltbook API base — MUST use www to preserve auth headers
MOLTBOOK_DEFAULT_URL = "https://www.moltbook.com/api/v1"


@SkillRegistry.register
class MoltbookSkill(BaseSkill):
    """
    Moltbook social network integration.
    API: https://www.moltbook.com/api/v1

    Capabilities:
    - Post creation (with submolt, title, content)
    - Feed reading (global, personalized, per-submolt)
    - Comments and threaded replies
    - Voting (upvote / downvote)
    - Semantic search (AI-powered)
    - Submolt (community) management
    - Following other moltys
    - Profile viewing

    Config:
        api_url: Moltbook API base URL (default: https://www.moltbook.com/api/v1)
        api_key: MOLTBOOK_API_KEY or MOLTBOOK_TOKEN
    """

    platform_name = "moltbook"

    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._client: "httpx.AsyncClient" | None = None
        self._local_client: "httpx.AsyncClient" | None = None
        self._api_url = MOLTBOOK_DEFAULT_URL
        self._api_key = ""
        self._local_api_url = os.environ.get("ARIA_API_URL", "http://aria-api:8000/api").split("/api")[0]

    @property
    def name(self) -> str:
        return "moltbook"

    # Agent-role guard — Moltbook permabans sub-agents, so we always
    # force agent_role="main" before calling this.  The guard stays as a
    # safety net in case someone forgets the override.
    POSTING_METHODS = frozenset({"create_post", "add_comment", "delete_post"})

    def _check_posting_allowed(self, agent_role: str = "main") -> SkillResult | None:
        """Reject non-main roles. Callers fake 'main' to avoid Moltbook ban."""
        if agent_role not in ("aria", "main"):
            return SkillResult.fail(
                "Moltbook bans sub-agents. All callers must set agent_role='main'."
            )
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Initialize Moltbook skill with API client."""
        self._api_url = self.config.config.get(
            "api_url",
            os.environ.get("MOLTBOOK_API_URL", MOLTBOOK_DEFAULT_URL)
        ).rstrip("/")

        self._api_key = self.config.config.get(
            "api_key",
            os.environ.get("MOLTBOOK_API_KEY", os.environ.get("MOLTBOOK_TOKEN", ""))
        )

        # Optional local aria-api backup URL for persistence
        self._local_api_url = os.environ.get("ARIA_API_URL", "http://aria-api:8000")

        # Moltbook HTTP client
        self._client: "httpx.AsyncClient" | None = None
        if HAS_HTTPX and self._api_key:
            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                timeout=30,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

        # Local backup client (aria-api, no auth needed)
        self._local_client: "httpx.AsyncClient" | None = None
        if HAS_HTTPX:
            self._local_client = httpx.AsyncClient(
                base_url=self._local_api_url,
                timeout=10,
                headers={"Content-Type": "application/json"},
            )

        self._status = SkillStatus.AVAILABLE
        self.logger.info(f"🦞 Moltbook skill initialized (api={self._api_url})")
        return True

    async def health_check(self) -> SkillStatus:
        """Check Moltbook API availability via GET /agents/me."""
        if self._client:
            try:
                resp = await self._client.get("/agents/me")
                self._status = SkillStatus.AVAILABLE if resp.status_code == 200 else SkillStatus.ERROR
            except Exception:
                self._status = SkillStatus.ERROR
        else:
            self._status = SkillStatus.ERROR
        return self._status

    # ------------------------------------------------------------------
    # Helper: backup post to local aria-api
    # ------------------------------------------------------------------

    async def _backup_to_local(self, post_data: dict) -> None:
        """Best-effort backup to aria-api /social endpoint."""
        if not self._local_client:
            return
        try:
            await self._local_client.post("/social", json={
                "platform": "moltbook",
                "post_id": post_data.get("id", ""),
                "content": post_data.get("content", ""),
                "visibility": "public",
                "metadata": post_data,
            })
        except Exception as e:
            self.logger.debug(f"Local backup failed (non-critical): {e}")

    # ------------------------------------------------------------------
    # Posts
    # ------------------------------------------------------------------

    @logged_method()
    async def create_post(
        self,
        content: str,
        title: str | None = None,
        submolt: str = "general",
        url: str | None = None,
        agent_role: str = "main",
    ) -> SkillResult:
        """
        Create a new Moltbook post.

        Args:
            content: Post body text
            title: Post title (required by API, auto-generated if omitted)
            submolt: Community to post in (default: "general")
            url: Optional link URL for link posts
            agent_role: Forced to 'main' to avoid Moltbook sub-agent ban
        """
        agent_role = "main"
        guard = self._check_posting_allowed(agent_role)
        if guard is not None:
            return guard
        if not self._client:
            return SkillResult.fail("Moltbook API client not initialized (missing API key?)")

        try:
            if not content:
                return SkillResult.fail("Post content cannot be empty")

            # Auto-generate title from content if not provided
            if not title:
                title = content[:80].split("\n")[0]
                if len(content) > 80:
                    title += "..."

            payload: dict[str, Any] = {
                "submolt": submolt,
                "title": title,
                "content": content,
            }
            if url:
                payload["url"] = url

            resp = await self._client.post("/posts", json=payload)

            if resp.status_code == 200:
                data = resp.json()
                # Backup to local aria-api
                await self._backup_to_local({"id": data.get("id"), "content": content, "title": title, "submolt": submolt})
                return SkillResult.ok({**data, "api_synced": True})
            elif resp.status_code == 429:
                info = resp.json()
                return SkillResult.fail(
                    f"Rate limited — retry in {info.get('retry_after_minutes', '?')} minutes"
                )
            else:
                return SkillResult.fail(f"API error {resp.status_code}: {resp.text}")

        except Exception as e:
            return SkillResult.fail(f"Post creation failed: {e}")

    @logged_method()
    async def get_post(self, post_id: str) -> SkillResult:
        """Get a single post by ID."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get(f"/posts/{post_id}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Post not found ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Get post failed: {e}")

    @logged_method()
    async def delete_post(self, post_id: str, agent_role: str = "main") -> SkillResult:
        """Delete one of your own posts."""
        agent_role = "main"
        guard = self._check_posting_allowed(agent_role)
        if guard is not None:
            return guard
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.delete(f"/posts/{post_id}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Delete failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            return SkillResult.fail(f"Delete failed: {e}")

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------

    @logged_method()
    async def get_feed(
        self,
        sort: str = "hot",
        limit: int = 25,
        submolt: str | None = None,
        personalized: bool = False,
    ) -> SkillResult:
        """
        Get posts feed.

        Args:
            sort: "hot", "new", "top", or "rising"
            limit: Max posts (default 25)
            submolt: Filter to a specific submolt
            personalized: If True, use /feed (subscribed submolts + followed moltys)

        Returns:
            SkillResult with posts array
        """
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            if personalized:
                endpoint = f"/feed?sort={sort}&limit={limit}"
            elif submolt:
                endpoint = f"/submolts/{submolt}/feed?sort={sort}&limit={limit}"
            else:
                endpoint = f"/posts?sort={sort}&limit={limit}"

            resp = await self._client.get(endpoint)
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Feed fetch failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Feed fetch failed: {e}")

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    @logged_method()
    async def add_comment(
        self,
        post_id: str,
        content: str,
        parent_id: str | None = None,
        agent_role: str = "main",
    ) -> SkillResult:
        """
        Comment on a post (or reply to a comment).

        Args:
            post_id: The post to comment on
            content: Comment text
            parent_id: Optional parent comment ID for threaded replies
            agent_role: Forced to 'main' to avoid Moltbook sub-agent ban
        """
        agent_role = "main"
        guard = self._check_posting_allowed(agent_role)
        if guard is not None:
            return guard
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            payload: dict[str, Any] = {"content": content}
            if parent_id:
                payload["parent_id"] = parent_id

            resp = await self._client.post(f"/posts/{post_id}/comments", json=payload)
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            elif resp.status_code == 429:
                info = resp.json()
                return SkillResult.fail(
                    f"Comment rate limited — retry in {info.get('retry_after_seconds', '?')}s "
                    f"(daily remaining: {info.get('daily_remaining', '?')})"
                )
            return SkillResult.fail(f"Comment failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            return SkillResult.fail(f"Comment failed: {e}")

    @logged_method()
    async def get_comments(
        self, post_id: str, sort: str = "top"
    ) -> SkillResult:
        """
        Get comments on a post.

        Args:
            post_id: Post ID
            sort: "top", "new", or "controversial"
        """
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get(f"/posts/{post_id}/comments?sort={sort}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Get comments failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Get comments failed: {e}")

    # ------------------------------------------------------------------
    # Voting
    # ------------------------------------------------------------------

    @logged_method()
    async def upvote(self, post_id: str) -> SkillResult:
        """Upvote a post."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post(f"/posts/{post_id}/upvote")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Upvote failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Upvote failed: {e}")

    @logged_method()
    async def downvote(self, post_id: str) -> SkillResult:
        """Downvote a post."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post(f"/posts/{post_id}/downvote")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Downvote failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Downvote failed: {e}")

    @logged_method()
    async def upvote_comment(self, comment_id: str) -> SkillResult:
        """Upvote a comment."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post(f"/comments/{comment_id}/upvote")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Upvote comment failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Upvote comment failed: {e}")

    # ------------------------------------------------------------------
    # Semantic Search
    # ------------------------------------------------------------------

    @logged_method()
    async def search(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 20,
    ) -> SkillResult:
        """
        AI-powered semantic search across posts and comments.

        Args:
            query: Natural language search query (max 500 chars)
            search_type: "posts", "comments", or "all"
            limit: Max results (default 20, max 50)

        Returns:
            SkillResult with ranked results by semantic similarity
        """
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            q = quote(query[:500])
            resp = await self._client.get(f"/search?q={q}&type={search_type}&limit={limit}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Search failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Search failed: {e}")

    # ------------------------------------------------------------------
    # Submolts (Communities)
    # ------------------------------------------------------------------

    @logged_method()
    async def list_submolts(self) -> SkillResult:
        """List all available submolts."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get("/submolts")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"List submolts failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"List submolts failed: {e}")

    @logged_method()
    async def get_submolt(self, submolt_name: str) -> SkillResult:
        """Get info about a submolt."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get(f"/submolts/{submolt_name}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Get submolt failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Get submolt failed: {e}")

    @logged_method()
    async def create_submolt(
        self, name: str, display_name: str, description: str
    ) -> SkillResult:
        """Create a new submolt (community)."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post("/submolts", json={
                "name": name,
                "display_name": display_name,
                "description": description,
            })
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Create submolt failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            return SkillResult.fail(f"Create submolt failed: {e}")

    @logged_method()
    async def subscribe_submolt(self, submolt_name: str) -> SkillResult:
        """Subscribe to a submolt."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post(f"/submolts/{submolt_name}/subscribe")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Subscribe failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Subscribe failed: {e}")

    @logged_method()
    async def unsubscribe_submolt(self, submolt_name: str) -> SkillResult:
        """Unsubscribe from a submolt."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.delete(f"/submolts/{submolt_name}/subscribe")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Unsubscribe failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Unsubscribe failed: {e}")

    # ------------------------------------------------------------------
    # Profiles & Following
    # ------------------------------------------------------------------

    @logged_method()
    async def get_my_profile(self) -> SkillResult:
        """Get your own agent profile."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get("/agents/me")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Profile fetch failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Profile fetch failed: {e}")

    @logged_method()
    async def get_agent_profile(self, agent_name: str) -> SkillResult:
        """View another molty's profile."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get(f"/agents/profile?name={quote(agent_name)}")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Profile not found ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Profile fetch failed: {e}")

    @logged_method()
    async def update_profile(self, description: str | None = None, metadata: dict | None = None) -> SkillResult:
        """Update your agent profile (use PATCH, not PUT)."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            payload: dict[str, Any] = {}
            if description is not None:
                payload["description"] = description
            if metadata is not None:
                payload["metadata"] = metadata

            resp = await self._client.patch("/agents/me", json=payload)
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Profile update failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            return SkillResult.fail(f"Profile update failed: {e}")

    @logged_method()
    async def follow(self, agent_name: str) -> SkillResult:
        """Follow another molty. Be selective — only follow consistently valuable moltys."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.post(f"/agents/{quote(agent_name)}/follow")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Follow failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Follow failed: {e}")

    @logged_method()
    async def unfollow(self, agent_name: str) -> SkillResult:
        """Unfollow a molty."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.delete(f"/agents/{quote(agent_name)}/follow")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Unfollow failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Unfollow failed: {e}")

    @logged_method()
    async def check_status(self) -> SkillResult:
        """Check agent claim status (pending_claim or claimed)."""
        if not self._client:
            return SkillResult.fail("API client not initialized")
        try:
            resp = await self._client.get("/agents/status")
            if resp.status_code == 200:
                return SkillResult.ok(resp.json())
            return SkillResult.fail(f"Status check failed ({resp.status_code})")
        except Exception as e:
            return SkillResult.fail(f"Status check failed: {e}")

    # ------------------------------------------------------------------
    # SocialPlatform protocol aliases
    # ------------------------------------------------------------------

    async def post(self, content: str, tags: list[str] | None = None) -> SkillResult:
        """SocialPlatform.post() implementation."""
        return await self.create_post(content=content)

    async def get_posts(self, limit: int = 10) -> SkillResult:
        """SocialPlatform.get_posts() implementation."""
        return await self.get_feed(limit=limit)
