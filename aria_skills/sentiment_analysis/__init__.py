# aria_skills/sentiment_analysis/__init__.py
"""
Lightweight sentiment detection — rule-based keyword matching.

Stores significant sentiment events to semantic memory via api_client.
No LLM dependency — fast, predictable, zero-cost.
"""
import re
from typing import Any, Dict, Optional

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

# ── Keyword patterns (covers ~80% of common expressions) ────────────

FRUSTRATION_SIGNALS = re.compile(
    r"\b(frustrated?|annoying|broken|stuck|wtf|ugh|damn|why won.t|doesn.t work|"
    r"still broken|again\?|not working|hate this|give up)\b", re.IGNORECASE
)
SATISFACTION_SIGNALS = re.compile(
    r"\b(thanks?|perfect|awesome|great|love it|works?|nice|excellent|beautiful|"
    r"amazing|finally|nailed it|well done)\b", re.IGNORECASE
)
CONFUSION_SIGNALS = re.compile(
    r"\b(confused?|don.t understand|what do you mean|unclear|lost|huh\??|"
    r"how does|why is|makes no sense)\b", re.IGNORECASE
)


def detect_sentiment(text: str) -> Dict[str, Any]:
    """Quick rule-based sentiment detection. Returns category + confidence."""
    text_lower = text.lower().strip()
    if not text_lower:
        return {"sentiment": "neutral", "confidence": 0.5, "signals": []}

    signals = []
    scores: Dict[str, float] = {"frustration": 0.0, "satisfaction": 0.0, "confusion": 0.0}

    for match in FRUSTRATION_SIGNALS.finditer(text):
        scores["frustration"] += 1.0
        signals.append(f"frustration:{match.group()}")
    for match in SATISFACTION_SIGNALS.finditer(text):
        scores["satisfaction"] += 1.0
        signals.append(f"satisfaction:{match.group()}")
    for match in CONFUSION_SIGNALS.finditer(text):
        scores["confusion"] += 1.0
        signals.append(f"confusion:{match.group()}")

    if not signals:
        return {"sentiment": "neutral", "confidence": 0.7, "signals": []}

    # Dominant sentiment
    dominant = max(scores, key=scores.get)  # type: ignore[arg-type]
    confidence = min(0.9, 0.5 + scores[dominant] * 0.15)

    sentiment_map = {
        "frustration": "negative",
        "satisfaction": "positive",
        "confusion": "uncertain",
    }

    return {
        "sentiment": sentiment_map[dominant],
        "dominant_emotion": dominant,
        "confidence": round(confidence, 2),
        "signals": signals,
        "scores": {k: round(v, 2) for k, v in scores.items() if v > 0},
    }


@SkillRegistry.register
class SentimentAnalysisSkill(BaseSkill):
    """Lightweight sentiment analysis — detect frustration/satisfaction/confusion."""

    def __init__(self, config: Optional[SkillConfig] = None):
        super().__init__(config or SkillConfig(name="sentiment_analysis"))
        self._api = None

    @property
    def name(self) -> str:
        return "sentiment_analysis"

    async def initialize(self) -> bool:
        """Initialize — optionally connect to api_client for semantic storage."""
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception:
            # Graceful: sentiment works without api_client, just can't store
            self._api = None
        self._status = SkillStatus.AVAILABLE
        self.logger.info("Sentiment analysis initialized (api_client=%s)", self._api is not None)
        return True

    async def health_check(self) -> SkillStatus:
        return self._status

    @logged_method()
    async def analyze_sentiment(self, text: str = "", **kwargs) -> SkillResult:
        """
        Analyze sentiment of a text message.

        Args:
            text: Text to analyze for sentiment.
        """
        text = text or kwargs.get("text", "")
        if not text:
            return SkillResult.fail("text is required")

        result = detect_sentiment(text)

        # Store significant sentiment to semantic memory
        if result["confidence"] >= 0.7 and result["sentiment"] != "neutral" and self._api:
            try:
                await self._api.store_memory_semantic(
                    content=f"User sentiment: {result['dominant_emotion']} — \"{text[:200]}\"",
                    category="sentiment",
                    importance=min(0.9, result["confidence"]),
                    metadata={"sentiment": result, "source": "sentiment_analysis"},
                )
            except Exception:
                pass  # Graceful degradation — sentiment still returned

        return SkillResult.ok(result)

    async def close(self) -> None:
        """Cleanup."""
        self._api = None
        self._status = SkillStatus.UNAVAILABLE
