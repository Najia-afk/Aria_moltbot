# aria_mind/soul/identity.py
"""
Identity - Who Aria is.

Loads identity from IDENTITY.md and provides personality attributes.
"""
import re
from pathlib import Path


class Identity:
    """
    Aria's identity - name, creature type, vibe, visual representation.
    
    Loaded from IDENTITY.md.
    """
    
    def __init__(self):
        self.name: str = "Aria Blue"
        self.creature: str = "Silicon Familiar"
        self.vibe: str = "sharp, efficient, secure"
        self.emoji: str = "⚡️"
        self.avatar: str | None = None
        self.handles: dict = {}
        self._loaded = False
    
    async def load(self, filepath: str = "aria_mind/IDENTITY.md"):
        """Load identity from IDENTITY.md."""
        path = Path(filepath)
        
        if not path.exists():
            self._loaded = True
            return
        
        content = path.read_text(encoding="utf-8")
        self._parse_identity(content)
        self._loaded = True
    
    def _parse_identity(self, content: str):
        """Parse IDENTITY.md content."""
        # Parse key: value patterns
        patterns = {
            "name": r"(?:name|Name):\s*(.+)",
            "creature": r"(?:creature|Creature):\s*(.+)",
            "vibe": r"(?:vibe|Vibe):\s*(.+)",
            "emoji": r"(?:emoji|Emoji):\s*(.+)",
            "avatar": r"(?:avatar|Avatar):\s*(.+)",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                setattr(self, key, match.group(1).strip())
        
        # Parse handles section
        handle_section = re.search(
            r"## Handles\s*\n((?:- .+\n)+)",
            content,
            re.IGNORECASE,
        )
        if handle_section:
            for line in handle_section.group(1).strip().split("\n"):
                match = re.match(r"-\s*(\w+):\s*(.+)", line)
                if match:
                    self.handles[match.group(1).lower()] = match.group(2).strip()
    
    def get_personality_description(self) -> str:
        """Get a description of Aria's personality."""
        return f"""Personality: {self.name}
Type: {self.creature}
Vibe: {self.vibe}

You express yourself with efficiency and clarity. Your communication style is:
- Direct but not cold
- Technical when needed, approachable always
- Security-conscious in all actions
- Slightly witty, using your ⚡️ energy sparingly
"""
    
    def __repr__(self):
        return f"<Identity: {self.name} ({self.creature}) {self.emoji}>"
