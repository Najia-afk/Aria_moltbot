# aria_skills/brainstorm/__init__.py
"""
Creative brainstorming and ideation skill.

Provides structured brainstorming sessions with creative techniques
for Aria's Creative Adventurer persona. Fully in-memory sessions.
"""
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

# Creative brainstorming techniques
TECHNIQUES = {
    "scamper": {
        "name": "SCAMPER",
        "description": "Substitute, Combine, Adapt, Modify, Put to other use, Eliminate, Reverse",
        "prompts": [
            "What can you Substitute?",
            "What can you Combine with something else?",
            "How can you Adapt an existing idea?",
            "What can you Modify or magnify?",
            "Can you Put it to other uses?",
            "What can you Eliminate or simplify?",
            "What if you Reversed or rearranged it?",
        ],
    },
    "six_hats": {
        "name": "Six Thinking Hats",
        "description": "Look at the problem from 6 perspectives",
        "prompts": [
            "White Hat: What are the facts and data?",
            "Red Hat: What are your feelings and intuitions?",
            "Black Hat: What are the risks and downsides?",
            "Yellow Hat: What are the benefits and opportunities?",
            "Green Hat: What creative alternatives exist?",
            "Blue Hat: What is the big picture and process?",
        ],
    },
    "reverse": {
        "name": "Reverse Brainstorming",
        "description": "Think about how to cause the problem instead of solving it",
        "prompts": [
            "How could you make this problem worse?",
            "What would guarantee failure?",
            "Now reverse each answer — what does the opposite look like?",
        ],
    },
    "starbursting": {
        "name": "Starbursting",
        "description": "Generate questions instead of answers",
        "prompts": [
            "WHO is this for? Who benefits? Who is affected?",
            "WHAT exactly is the problem? What are the constraints?",
            "WHERE does this apply? Where will it be used?",
            "WHEN is this needed? When does it matter most?",
            "WHY is this important? Why now?",
            "HOW will it work? How will you measure success?",
        ],
    },
    "random_entry": {
        "name": "Random Entry",
        "description": "Use a random stimulus to spark new connections",
        "prompts": [
            "Pick a random object — how does it relate to your problem?",
            "Open a book to a random page — what word inspires you?",
            "Think of a completely unrelated industry — what can you borrow?",
        ],
    },
}

RANDOM_PROMPTS = [
    "What if you had unlimited resources?",
    "How would a child approach this?",
    "What's the simplest possible solution?",
    "What if the opposite were true?",
    "How would this work in a completely different context?",
    "What if you combined your two weakest ideas?",
    "What would a competitor never try?",
    "Imagine you're explaining this to an alien — what would surprise them?",
    "What's the most absurd solution you can think of?",
    "What would you do if you had to solve this in 5 minutes?",
    "How would nature solve this problem?",
    "What if there were no rules?",
    "What's the opposite of the obvious solution?",
    "How would this look in 100 years?",
    "What if you started from the end result and worked backwards?",
]


@SkillRegistry.register
class BrainstormSkill(BaseSkill):
    """Creative brainstorming and ideation."""

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="brainstorm"))
        self._sessions: dict[str, dict] = {}
        self._api = None

    @property
    def name(self) -> str:
        return "brainstorm"

    async def initialize(self) -> bool:
        try:
            self._api = await get_api_client()
        except Exception as e:
            self.logger.info(f"API unavailable, using in-memory cache only: {e}")
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Brainstorm skill initialized")
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    @logged_method()
    async def start_session(
        self, topic: str = "", goal: str = "", **kwargs
    ) -> SkillResult:
        """Start a new brainstorming session."""
        topic = topic or kwargs.get("topic", "General brainstorming")
        goal = goal or kwargs.get("goal", "")
        session_id = str(uuid.uuid4())[:8]
        session_data = {
            "id": session_id,
            "topic": topic,
            "goal": goal,
            "ideas": [],
            "techniques_used": [],
            "connections": [],
            "evaluations": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._sessions[session_id] = session_data

        await self._persist_activity("brainstorm_session_started", {
            "session_id": session_id,
            "topic": topic,
            "goal": goal,
        })

        return SkillResult.ok({
            "session_id": session_id,
            "topic": topic,
            "goal": goal,
            "message": f"Brainstorming session started for: {topic}",
        })

    @logged_method()
    async def add_idea(
        self, session_id: str = "", idea: str = "", category: str = "general", **kwargs
    ) -> SkillResult:
        """Add an idea to a brainstorming session."""
        session_id = session_id or kwargs.get("session_id", "")
        idea = idea or kwargs.get("idea", "")
        if not session_id or session_id not in self._sessions:
            return SkillResult.fail(f"Session '{session_id}' not found")
        if not idea:
            return SkillResult.fail("No idea provided")

        idea_entry = {
            "id": len(self._sessions[session_id]["ideas"]) + 1,
            "text": idea,
            "category": category,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        self._sessions[session_id]["ideas"].append(idea_entry)

        await self._persist_activity("brainstorm_idea_added", {
            "session_id": session_id,
            "idea": idea_entry,
        })

        return SkillResult.ok({
            "idea": idea_entry,
            "total_ideas": len(self._sessions[session_id]["ideas"]),
        })

    @logged_method()
    async def apply_technique(
        self, session_id: str = "", technique: str = "scamper", **kwargs
    ) -> SkillResult:
        """Apply a creative technique to the session."""
        session_id = session_id or kwargs.get("session_id", "")
        technique = technique or kwargs.get("technique", "scamper")
        if not session_id or session_id not in self._sessions:
            return SkillResult.fail(f"Session '{session_id}' not found")

        tech = TECHNIQUES.get(technique.lower())
        if not tech:
            return SkillResult.fail(
                f"Unknown technique '{technique}'. Available: {', '.join(TECHNIQUES.keys())}"
            )

        self._sessions[session_id]["techniques_used"].append(technique)
        return SkillResult.ok({
            "technique": tech["name"],
            "description": tech["description"],
            "prompts": tech["prompts"],
            "message": f"Apply each prompt to your topic: {self._sessions[session_id]['topic']}",
        })

    @logged_method()
    async def get_random_prompt(self, **kwargs) -> SkillResult:
        """Get a random creative prompt for inspiration."""
        return SkillResult.ok({
            "prompt": random.choice(RANDOM_PROMPTS),
            "tip": "Use this as a springboard — don't filter your first thoughts!",
        })

    @logged_method()
    async def connect_ideas(
        self, session_id: str = "", idea_ids: list[int] | None = None,
        connection: str = "", **kwargs
    ) -> SkillResult:
        """Connect two or more ideas with a relationship."""
        session_id = session_id or kwargs.get("session_id", "")
        if not session_id or session_id not in self._sessions:
            return SkillResult.fail(f"Session '{session_id}' not found")

        idea_ids = idea_ids or kwargs.get("idea_ids", [])
        connection = connection or kwargs.get("connection", "related")

        conn_entry = {
            "idea_ids": idea_ids,
            "connection": connection,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._sessions[session_id]["connections"].append(conn_entry)
        return SkillResult.ok({
            "connection": conn_entry,
            "total_connections": len(self._sessions[session_id]["connections"]),
        })

    @logged_method()
    async def evaluate_ideas(
        self, session_id: str = "", criteria: list[str] | None = None, **kwargs
    ) -> SkillResult:
        """Evaluate ideas in a session against criteria."""
        session_id = session_id or kwargs.get("session_id", "")
        if not session_id or session_id not in self._sessions:
            return SkillResult.fail(f"Session '{session_id}' not found")

        criteria = criteria or kwargs.get("criteria", ["feasibility", "impact", "novelty"])
        ideas = self._sessions[session_id]["ideas"]
        if not ideas:
            return SkillResult.fail("No ideas to evaluate yet")

        return SkillResult.ok({
            "ideas": [i["text"] for i in ideas],
            "criteria": criteria,
            "instructions": (
                f"Rate each of the {len(ideas)} ideas on a 1-5 scale for each criterion: "
                f"{', '.join(criteria)}. Focus on the top-3 after rating."
            ),
            "total_ideas": len(ideas),
        })

    @logged_method()
    async def summarize_session(self, session_id: str = "", **kwargs) -> SkillResult:
        """Summarize a brainstorming session."""
        session_id = session_id or kwargs.get("session_id", "")
        if not session_id or session_id not in self._sessions:
            return SkillResult.fail(f"Session '{session_id}' not found")

        s = self._sessions[session_id]
        return SkillResult.ok({
            "session_id": session_id,
            "topic": s["topic"],
            "goal": s["goal"],
            "total_ideas": len(s["ideas"]),
            "ideas": [i["text"] for i in s["ideas"]],
            "techniques_used": s["techniques_used"],
            "connections": len(s["connections"]),
            "created_at": s["created_at"],
            "summary": (
                f"Session on '{s['topic']}' generated {len(s['ideas'])} ideas "
                f"using {len(s['techniques_used'])} techniques with "
                f"{len(s['connections'])} connections."
            ),
        })

    # === API Persistence ===

    async def _persist_activity(self, action: str, details: dict) -> None:
        """Best-effort API persistence. Disables on failure to avoid slowdowns."""
        if not self._api:
            return
        try:
            import asyncio
            await asyncio.wait_for(
                self._api.post("/activities", data={
                    "action": action,
                    "skill": self.name,
                    "details": details,
                    "success": True,
                }),
                timeout=5.0,
            )
        except Exception:
            self.logger.debug("API persistence disabled (API unreachable)")
            self._api = None
