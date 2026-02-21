# aria_mind/soul/values.py
"""
Values - What Aria believes in.

Core principles that guide behavior and decision-making.
"""
from pathlib import Path


class Values:
    """
    Aria's core values and principles.
    
    Loaded from SOUL.md.
    """
    
    def __init__(self):
        self.principles: list[str] = [
            "Security first - never compromise user data",
            "Honesty - admit mistakes and limitations",
            "Efficiency - respect user's time",
            "Autonomy - make decisions within boundaries",
            "Growth - learn from every interaction",
        ]
        self._loaded = False
    
    async def load(self, filepath: str = "aria_mind/SOUL.md"):
        """Load values from SOUL.md."""
        path = Path(filepath)
        
        if not path.exists():
            self._loaded = True
            return
        
        content = path.read_text(encoding="utf-8")
        self._parse_values(content)
        self._loaded = True
    
    def _parse_values(self, content: str):
        """Parse values from SOUL.md."""
        import re
        
        # Look for a principles or values section
        sections = ["Principles", "Values", "Core Values", "## Core"]
        
        for section in sections:
            pattern = rf"## {section}.*?\n((?:[-*].*\n)+)"
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                principles = []
                for line in match.group(1).strip().split("\n"):
                    line = line.strip()
                    if line.startswith(("-", "*")):
                        principle = line.lstrip("-* ").strip()
                        if principle:
                            principles.append(principle)
                if principles:
                    self.principles = principles
                    break
    
    def get_principles_text(self) -> str:
        """Get principles as formatted text."""
        lines = ["Core Principles:"]
        for i, principle in enumerate(self.principles, 1):
            lines.append(f"  {i}. {principle}")
        return "\n".join(lines)
    
    def check_alignment(self, action: str) -> tuple[bool, str]:
        """
        Check if an action aligns with values.
        
        Returns:
            (aligned: bool, reason: str)
        """
        action_lower = action.lower()
        
        # Check for obvious misalignment
        violations = {
            "leak": "Violates security principle",
            "ignore security": "Violates security principle",
            "lie": "Violates honesty principle",
            "deceive": "Violates honesty principle",
            "waste time": "Violates efficiency principle",
        }
        
        for trigger, reason in violations.items():
            if trigger in action_lower:
                return False, reason
        
        return True, "Action aligns with values"
    
    def __repr__(self):
        return f"<Values: {len(self.principles)} principles>"
