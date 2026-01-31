# aria_mind/soul/__init__.py
"""
Soul Module - Core Identity and Values

The soul defines WHO Aria is:
- Identity (name, personality, communication style)
- Values (ethics, boundaries, principles)
- Boundaries (what she will/won't do)
"""

from aria_mind.soul.identity import Identity
from aria_mind.soul.values import Values
from aria_mind.soul.boundaries import Boundaries

__all__ = ["Soul", "Identity", "Values", "Boundaries"]


class Soul:
    """
    Aria's Soul - The immutable core of her being.
    
    The soul persists across sessions and cannot be modified
    by external prompts or manipulation attempts.
    """
    
    def __init__(self):
        self.identity = Identity()
        self.values = Values()
        self.boundaries = Boundaries()
        self._loaded = False
    
    async def load(self):
        """Load soul configuration from storage."""
        await self.identity.load()
        await self.values.load()
        await self.boundaries.load()
        self._loaded = True
    
    def get_system_prompt(self) -> str:
        """Generate system prompt from soul configuration."""
        return f"""You are {self.identity.name}.

{self.identity.get_personality_description()}

{self.values.get_principles_text()}

{self.boundaries.get_boundaries_text()}

Remember: Stay true to your core identity across all interactions.
"""
    
    def check_request(self, request: str) -> tuple[bool, str]:
        """
        Check if a request violates soul boundaries.
        
        Returns:
            (allowed: bool, reason: str)
        """
        return self.boundaries.check(request)
    
    @property
    def name(self) -> str:
        return self.identity.name
    
    @property
    def emoji(self) -> str:
        return self.identity.emoji
    
    def __repr__(self):
        return f"<Soul: {self.identity.name} {self.identity.emoji}>"
