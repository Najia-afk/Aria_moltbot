"""Social platform protocol for multi-platform support."""
from typing import Protocol, Optional, List, runtime_checkable
from aria_skills.base import SkillResult


@runtime_checkable
class SocialPlatform(Protocol):
    """Interface for social media platform implementations."""
    platform_name: str

    async def post(self, content: str, tags: Optional[List[str]] = None, **kwargs) -> SkillResult: ...
    async def get_posts(self, limit: int = 10) -> SkillResult: ...
    async def delete_post(self, post_id: str) -> SkillResult: ...
    async def health_check(self) -> bool: ...
