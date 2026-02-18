"""Brainstorm skill — creative ideation session management."""


import uuid
from datetime import datetime, timezone

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus
from aria_skills.registry import SkillRegistry


@SkillRegistry.register
class BrainstormSkill(BaseSkill):
    def __init__(self, config: SkillConfig):
        super().__init__(config)
        self._sessions: dict[str, dict] = {}

    @property
    def name(self) -> str:
        return "brainstorm"

    async def initialize(self) -> bool:
        self._status = SkillStatus.AVAILABLE
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    async def start_session(self, topic: str, constraints: list[str] | None = None) -> SkillResult:
        session_id = f"brainstorm-{uuid.uuid4().hex[:10]}"
        self._sessions[session_id] = {
            "session_id": session_id,
            "topic": topic,
            "constraints": constraints or [],
            "ideas": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return SkillResult.ok(self._sessions[session_id])

    async def add_idea(
        self,
        session_id: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
    ) -> SkillResult:
        session = self._sessions.get(session_id)
        if not session:
            return SkillResult.fail(f"Session not found: {session_id}")
        idea_id = f"idea-{uuid.uuid4().hex[:8]}"
        idea = {
            "idea_id": idea_id,
            "title": title,
            "description": description,
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        session["ideas"].append(idea)
        return SkillResult.ok({"session_id": session_id, "idea": idea, "idea_count": len(session["ideas"])})

    async def apply_technique(self, session_id: str, technique: str) -> SkillResult:
        session = self._sessions.get(session_id)
        if not session:
            return SkillResult.fail(f"Session not found: {session_id}")
        suggestions = {
            "scamper": ["Substitute one core assumption", "Combine 2 ideas into 1 experiment"],
            "six_hats": ["List optimistic path", "List critical risk path"],
            "random_word": ["Use random metaphor: lighthouse", "Use random constraint: 5-minute MVP"],
            "worst_idea": ["Generate 3 bad ideas then invert each"],
        }
        return SkillResult.ok({
            "session_id": session_id,
            "technique": technique,
            "prompts": suggestions.get(technique, ["Define an unusual angle", "Reframe around user pain"]),
        })

    async def get_random_prompt(self, category: str | None = None) -> SkillResult:
        bank = {
            "tech": "How would this work with 10x less compute?",
            "content": "Tell this story from the opposite point of view.",
            "business": "What is the smallest paid feature worth shipping this week?",
            "design": "Remove one UI element and improve clarity.",
        }
        return SkillResult.ok({"category": category or "general", "prompt": bank.get(category or "", "What can be simplified by 80%?")})

    async def connect_ideas(self, session_id: str, idea_ids: list[str] | None = None) -> SkillResult:
        session = self._sessions.get(session_id)
        if not session:
            return SkillResult.fail(f"Session not found: {session_id}")
        ideas = session.get("ideas", [])
        if idea_ids:
            ideas = [idea for idea in ideas if idea.get("idea_id") in idea_ids]
        connections = []
        for idx in range(max(0, len(ideas) - 1)):
            connections.append({
                "from": ideas[idx]["idea_id"],
                "to": ideas[idx + 1]["idea_id"],
                "bridge": "Combine strengths and de-risk assumptions",
            })
        return SkillResult.ok({"session_id": session_id, "connections": connections})

    async def evaluate_ideas(self, session_id: str, criteria: list[str] | None = None) -> SkillResult:
        session = self._sessions.get(session_id)
        if not session:
            return SkillResult.fail(f"Session not found: {session_id}")
        criteria = criteria or ["impact", "effort", "novelty"]
        ranked = []
        for idx, idea in enumerate(session.get("ideas", []), start=1):
            score = max(1, 100 - (idx * 5))
            ranked.append({"idea_id": idea["idea_id"], "title": idea["title"], "score": score, "criteria": criteria})
        return SkillResult.ok({"session_id": session_id, "criteria": criteria, "ranked": ranked})

    async def summarize_session(self, session_id: str) -> SkillResult:
        session = self._sessions.get(session_id)
        if not session:
            return SkillResult.fail(f"Session not found: {session_id}")
        ideas = session.get("ideas", [])
        return SkillResult.ok({
            "session_id": session_id,
            "topic": session.get("topic"),
            "summary": f"{len(ideas)} ideas captured for topic '{session.get('topic')}'.",
            "idea_count": len(ideas),
        })
