# aria_skills/conversation_summary/__init__.py
"""
📝 Conversation Summarization Skill

Compresses conversation history and activity logs into durable
semantic memories (episodic + decision categories).

Architecture: Skill (Layer 3) → api_client (Layer 2) → API (Layer 1)
Depends on S5-01 (pgvector semantic memory).
"""
import json
from typing import Any, Optional

from aria_skills.api_client import get_api_client
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

SUMMARIZATION_PROMPT = """\
Summarize this work session based on the activity log below. Respond ONLY with valid JSON.

Activity Log:
{activities}

Required JSON format:
{{
  "summary": "2-3 sentence summary of what happened",
  "decisions": ["decision 1", "decision 2"],
  "tone": "frustrated | satisfied | neutral | productive | exploratory",
  "unresolved": ["issue 1 still open"]
}}
"""

TOPIC_PROMPT = """\
Summarize everything known about the following topic based on these memory entries.
Respond ONLY with valid JSON.

Topic: {topic}

Memories:
{memories}

Required JSON format:
{{
  "summary": "Comprehensive 3-5 sentence summary",
  "key_facts": ["fact 1", "fact 2"],
  "open_questions": ["question 1"]
}}
"""


@SkillRegistry.register
class ConversationSummarySkill(BaseSkill):
    """
    Summarizes conversations and activity sessions into
    durable semantic memories for long-term recall.
    """

    @property
    def name(self) -> str:
        return "conversation_summary"

    async def initialize(self) -> bool:
        """Initialize conversation summary skill."""
        self._api = await get_api_client()
        self._status = SkillStatus.AVAILABLE
        self.logger.info("📝 Conversation summary skill initialized")
        return True

    async def close(self):
        self._api = None

    async def health_check(self) -> SkillStatus:
        return self._status

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @logged_method()
    async def summarize_session(
        self,
        hours_back: int = 24,
        session_id: Optional[str] = None,
    ) -> SkillResult:
        """
        Summarize a recent work session.

        1. Fetches recent activities via the API
        2. Sends to LLM for summarization
        3. Stores summary as episodic SemanticMemory
        4. Stores each decision as decision SemanticMemory
        """
        try:
            result = await self._api.summarize_session(hours_back=hours_back)
            return SkillResult(
                success=True,
                data=result,
                message=f"Session summarized ({hours_back}h window)",
            )
        except Exception as exc:
            self.logger.error("Session summarization failed: %s", exc)
            return SkillResult(
                success=False,
                data={"error": str(exc)},
                message=f"Summarization failed: {exc}",
            )

    @logged_method()
    async def summarize_topic(
        self,
        topic: str,
        max_memories: int = 20,
    ) -> SkillResult:
        """
        Summarize all memories related to a specific topic.

        1. Searches semantic memories by topic
        2. Sends matches to LLM for synthesis
        3. Stores synthesized summary as a new episodic memory
        """
        try:
            # Search for relevant memories
            search_results = await self._api.search_memories_semantic(
                query=topic,
                limit=max_memories,
            )
            memories = search_results if isinstance(search_results, list) else search_results.get("items", [])

            if not memories:
                return SkillResult(
                    success=True,
                    data={"summary": "No relevant memories found.", "key_facts": [], "open_questions": []},
                    message=f"No memories found for topic: {topic}",
                )

            # Format memories for the prompt
            memory_texts = []
            for m in memories:
                content = m.get("content", "") if isinstance(m, dict) else str(m)
                memory_texts.append(f"- {content}")

            prompt = TOPIC_PROMPT.format(
                topic=topic,
                memories="\n".join(memory_texts),
            )

            # Call LLM via api_client's LiteLLM proxy
            import httpx
            import os

            litellm_url = os.getenv("LITELLM_API_BASE", "http://aria-litellm:18793")
            litellm_key = os.getenv("LITELLM_API_KEY", "sk-aria-internal")

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{litellm_url}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {litellm_key}"},
                    json={
                        "model": "qwen3-mlx",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 800,
                    },
                )
                resp.raise_for_status()
                llm_data = resp.json()

            raw_text = llm_data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_text)

            # Store synthesis as a new episodic memory
            await self._api.store_memory_semantic(
                content=f"Topic synthesis — {topic}: {parsed.get('summary', raw_text)}",
                category="episodic",
                importance=0.7,
                source="conversation_summary",
            )

            return SkillResult(
                success=True,
                data=parsed,
                message=f"Synthesized {len(memories)} memories about '{topic}'",
            )

        except Exception as exc:
            self.logger.error("Topic summarization failed: %s", exc)
            return SkillResult(
                success=False,
                data={"error": str(exc)},
                message=f"Topic summarization failed: {exc}",
            )
