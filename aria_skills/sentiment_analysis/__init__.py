# aria_skills/sentiment_analysis/__init__.py
"""
Multi-Dimensional Sentiment Analysis — Full Production Implementation.

Three analysis dimensions:
  valence   — Positive vs negative (-1 to +1)
  arousal   — Calm vs excited (0 to 1)
  dominance — Submissive vs dominant (0 to 1)

Derived metrics:
  frustration  — high arousal + negative valence
  satisfaction — positive valence + high dominance
  confusion    — low dominance + neutral valence

Conversation-level analytics:
  trajectory   — improving / declining / stable
  volatility   — standard deviation of valence
  turning_points — points of significant sentiment shift

Adaptive response tuner selects tone profile based on current sentiment.

All storage via api_client → FastAPI → PostgreSQL (semantic memory).
"""
from __future__ import annotations

import json
import os
import re
import statistics
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry


# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════

class Trajectory(Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class Sentiment:
    """Single message sentiment analysis result."""
    valence: float        # -1 (negative) to +1 (positive)
    arousal: float        # 0 (calm) to 1 (excited)
    dominance: float      # 0 (submissive) to 1 (dominant)
    confidence: float = 0.8
    primary_emotion: str = "neutral"
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def frustration(self) -> float:
        """Frustration = high arousal * negative valence."""
        if self.valence >= 0:
            return 0.0
        return self.arousal * abs(self.valence)

    @property
    def satisfaction(self) -> float:
        """Satisfaction = positive valence * high dominance."""
        if self.valence <= 0:
            return 0.0
        return self.valence * self.dominance

    @property
    def confusion(self) -> float:
        """Confusion = low dominance * neutral valence."""
        valence_near_zero = 1 - abs(self.valence)
        return (1 - self.dominance) * valence_near_zero * 0.5


@dataclass
class ConversationSentiment:
    """Aggregate sentiment across a conversation."""
    overall: Sentiment
    trajectory: Trajectory
    turning_points: List[Dict[str, Any]] = field(default_factory=list)
    peak_positive: Optional[Sentiment] = None
    peak_negative: Optional[Sentiment] = None
    volatility: float = 0.0
    resolution: Optional[str] = None   # "positive", "negative", "neutral"
    messages_analyzed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        data = {
            "trajectory": self.trajectory.value,
            "overall": self.overall.to_dict() if self.overall else None,
            "peak_positive": self.peak_positive.to_dict() if self.peak_positive else None,
            "peak_negative": self.peak_negative.to_dict() if self.peak_negative else None,
            "turning_points": self.turning_points,
            "volatility": round(self.volatility, 4),
            "resolution": self.resolution,
            "messages_analyzed": self.messages_analyzed,
            "metadata": self.metadata,
        }
        return data


# ═══════════════════════════════════════════════════════════════════
# Lexicon-Based Analyzer
# ═══════════════════════════════════════════════════════════════════

class SentimentLexicon:
    """Fast lexicon-based sentiment scoring (baseline)."""

    POSITIVE_WORDS = frozenset({
        "good", "great", "excellent", "awesome", "amazing", "love", "happy",
        "thanks", "perfect", "wonderful", "fantastic", "yes", "correct",
        "right", "helpful", "clear", "understood", "understands", "nice",
        "brilliant", "superb", "beautiful", "glad", "pleased", "thrilled",
    })

    NEGATIVE_WORDS = frozenset({
        "bad", "terrible", "awful", "hate", "angry", "frustrated", "confused",
        "wrong", "error", "fail", "failed", "stupid", "useless", "no", "not",
        "problem", "issue", "broken", "slow", "disappointed", "annoying",
        "boring", "ugly", "horrible", "worst", "bugs", "crash", "stuck",
    })

    EXCITED_WORDS = frozenset({
        "wow", "incredible", "excited", "thrilled", "yay", "omg", "insane",
    })

    DOMINANT_WORDS = frozenset({
        "must", "should", "need", "require", "demand", "explain", "make",
        "create", "build", "find", "tell", "show", "fix", "change", "now",
    })

    @classmethod
    def score(cls, text: str) -> Tuple[float, float, float]:
        """Return (valence, arousal, dominance) from lexicon matches."""
        text_lower = text.lower()
        words = re.findall(r"\b\w+\b", text_lower)
        total = max(len(words), 1)

        # Valence
        pos_count = sum(1 for w in words if w in cls.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in cls.NEGATIVE_WORDS)
        valence = max(-1.0, min(1.0, (pos_count - neg_count) / total * 3))

        # Arousal
        excl = text.count("!")
        excited = sum(1 for w in words if w in cls.EXCITED_WORDS)
        arousal = max(0.0, min(1.0, (excited * 0.5 + excl * 0.1) / total * 5))

        # Dominance
        dom = sum(1 for w in words if w in cls.DOMINANT_WORDS)
        dominance = max(0.0, min(1.0, dom / total * 5))

        return valence, arousal, dominance


# ═══════════════════════════════════════════════════════════════════
# LLM Classifier (via LiteLLM proxy)
# ═══════════════════════════════════════════════════════════════════

class LLMSentimentClassifier:
    """LLM-based sentiment classification for higher accuracy."""

    def __init__(self):
        self._litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
        self._litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")

    async def classify(self, text: str, context: Optional[List[str]] = None) -> Sentiment:
        import httpx

        context_str = ""
        if context:
            context_str = "\nPrevious messages:\n" + "\n".join(f"- {c}" for c in context[-3:])

        prompt = (
            f'Analyze sentiment of this message:\nMessage: "{text}"\n{context_str}\n\n'
            "Score on these dimensions (range -1 to +1 for valence, 0-1 for others):\n"
            "- valence: positive vs negative\n"
            "- arousal: calm vs excited\n"
            "- dominance: submissive vs assertive\n\n"
            "Also identify:\n"
            "- primary_emotion: one of [neutral, happy, angry, frustrated, confused, excited, sad, satisfied]\n"
            "- labels: other relevant emotion tags\n\n"
            'Return JSON only: {"valence": float, "arousal": float, "dominance": float, '
            '"confidence": float, "primary_emotion": str, "labels": [str]}'
        )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self._litellm_url}/v1/chat/completions",
                json={
                    "model": "kimi",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.2,
                },
                headers={"Authorization": f"Bearer {self._litellm_key}"},
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]

        json_match = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return Sentiment(
                valence=float(parsed.get("valence", 0)),
                arousal=float(parsed.get("arousal", 0.5)),
                dominance=float(parsed.get("dominance", 0.5)),
                confidence=float(parsed.get("confidence", 0.9)),
                primary_emotion=parsed.get("primary_emotion", "neutral"),
                labels=parsed.get("labels", []),
            )

        # Could not parse — raise so caller falls back to lexicon
        raise ValueError(f"Unparseable LLM response: {raw[:200]}")


# ═══════════════════════════════════════════════════════════════════
# Sentiment Analyzer (Multi-Strategy Blend)
# ═══════════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """
    Main engine with fast lexicon baseline + optional LLM when ambiguous.
    """

    def __init__(
        self,
        llm_classifier: Optional[LLMSentimentClassifier] = None,
        lexicon_weight: float = 0.3,
        llm_weight: float = 0.7,
        use_llm_threshold: float = 0.6,
    ):
        self.llm_classifier = llm_classifier
        self.lexicon_weight = lexicon_weight
        self.llm_weight = llm_weight
        self.use_llm_threshold = use_llm_threshold
        self.history: deque = deque(maxlen=50)

    async def analyze(self, text: str, context: Optional[List[str]] = None) -> Sentiment:
        # Step 1: fast lexicon
        l_val, l_aro, l_dom = SentimentLexicon.score(text)

        lexicon_matches = sum(
            1 for w in re.findall(r"\b\w+\b", text.lower())
            if w in SentimentLexicon.POSITIVE_WORDS or w in SentimentLexicon.NEGATIVE_WORDS
        )
        lexicon_confidence = min(1.0, lexicon_matches / 5)

        # Step 2: use LLM if ambiguous
        should_use_llm = (
            self.llm_classifier
            and (lexicon_confidence < self.use_llm_threshold or abs(l_val) < 0.3)
        )

        if should_use_llm:
            try:
                llm_s = await self.llm_classifier.classify(text, context)
                blended = Sentiment(
                    valence=l_val * self.lexicon_weight + llm_s.valence * self.llm_weight,
                    arousal=l_aro * self.lexicon_weight + llm_s.arousal * self.llm_weight,
                    dominance=l_dom * self.lexicon_weight + llm_s.dominance * self.llm_weight,
                    confidence=max(lexicon_confidence, llm_s.confidence),
                    primary_emotion=llm_s.primary_emotion,
                    labels=llm_s.labels,
                )
                self.history.append(blended)
                return blended
            except Exception:
                pass   # fall through to lexicon-only

        result = Sentiment(
            valence=l_val, arousal=l_aro, dominance=l_dom, confidence=lexicon_confidence
        )
        self.history.append(result)
        return result


# ═══════════════════════════════════════════════════════════════════
# Conversation Analyzer
# ═══════════════════════════════════════════════════════════════════

class ConversationAnalyzer:
    """Analyze sentiment trajectory across a full conversation."""

    def __init__(self, analyzer: SentimentAnalyzer):
        self.analyzer = analyzer

    async def analyze_conversation(
        self, messages: List[Dict[str, Any]], window_size: int = 10,
    ) -> ConversationSentiment:
        if not messages:
            return ConversationSentiment(
                overall=Sentiment(valence=0, arousal=0, dominance=0),
                trajectory=Trajectory.INSUFFICIENT_DATA,
            )

        sentiments: List[Sentiment] = []
        for msg in messages:
            content = msg.get("content", "")
            ctx = [m.get("content", "") for m in messages[-3:] if m is not msg]
            s = await self.analyzer.analyze(content, ctx)
            sentiments.append(s)

        # Weighted average (exponential recency)
        weights = [0.5 ** (len(sentiments) - i - 1) for i in range(len(sentiments))]
        tw = sum(weights)
        overall = Sentiment(
            valence=sum(s.valence * w for s, w in zip(sentiments, weights)) / tw,
            arousal=sum(s.arousal * w for s, w in zip(sentiments, weights)) / tw,
            dominance=sum(s.dominance * w for s, w in zip(sentiments, weights)) / tw,
            confidence=min(1.0, len(sentiments) / 5),
        )

        trajectory = self._compute_trajectory(sentiments)
        volatility = statistics.stdev([s.valence for s in sentiments]) if len(sentiments) > 1 else 0.0
        peak_pos = max(sentiments, key=lambda s: s.valence)
        peak_neg = min(sentiments, key=lambda s: s.valence)
        turning_points = self._find_turning_points(sentiments)

        resolution = None
        if len(sentiments) >= 3:
            last3 = sum(s.valence for s in sentiments[-3:]) / 3
            resolution = "positive" if last3 > 0.3 else ("negative" if last3 < -0.3 else "neutral")

        return ConversationSentiment(
            overall=overall,
            trajectory=trajectory,
            turning_points=turning_points,
            peak_positive=peak_pos,
            peak_negative=peak_neg,
            volatility=volatility,
            resolution=resolution,
            messages_analyzed=len(sentiments),  # BUG FIX: was len(mentions)
        )

    @staticmethod
    def _compute_trajectory(sentiments: List[Sentiment]) -> Trajectory:
        if len(sentiments) < 4:
            return Trajectory.INSUFFICIENT_DATA
        mid = len(sentiments) // 2
        first_avg = sum(s.valence for s in sentiments[:mid]) / mid
        second_avg = sum(s.valence for s in sentiments[mid:]) / (len(sentiments) - mid)
        diff = second_avg - first_avg
        if diff > 0.3:
            return Trajectory.IMPROVING
        elif diff < -0.3:
            return Trajectory.DECLINING
        return Trajectory.STABLE

    @staticmethod
    def _find_turning_points(sentiments: List[Sentiment], threshold: float = 0.5) -> List[Dict[str, Any]]:
        points: List[Dict[str, Any]] = []
        for i in range(1, len(sentiments) - 1):
            prev_v = sentiments[i - 1].valence
            curr_v = sentiments[i].valence
            next_v = sentiments[i + 1].valence
            if abs(curr_v - prev_v) > threshold and abs(curr_v - next_v) > threshold:
                points.append({
                    "index": i,
                    "valence": curr_v,
                    "direction": "up" if curr_v > prev_v else "down",
                    "change_magnitude": round(abs(curr_v - prev_v), 3),
                })
        return points


# ═══════════════════════════════════════════════════════════════════
# Adaptive Response Tuner
# ═══════════════════════════════════════════════════════════════════

class ResponseTuner:
    """Select adaptive response tone based on sentiment analysis."""

    TONE_PROFILES = {
        "empathetic_supportive": {
            "conditions": {"frustration": 0.7, "valence": -0.5},
            "tone": "warm, validating, solution-oriented",
            "strategies": ["acknowledge_emotion", "apologize_if_needed", "offer_clear_steps"],
        },
        "clear_step_by_step": {
            "conditions": {"confusion": 0.6, "arousal": 0.3},
            "tone": "methodical, explicit, examples",
            "strategies": ["break_down_steps", "use_examples", "check_for_understanding"],
        },
        "friendly_celebratory": {
            "conditions": {"satisfaction": 0.8, "valence": 0.6},
            "tone": "enthusiastic, congratulatory",
            "strategies": ["positive_reinforcement", "celebrate_success", "offer_next_steps"],
        },
        "neutral_professional": {
            "conditions": {},
            "tone": "balanced, efficient",
            "strategies": ["direct_response", "brief_context", "offer_help"],
        },
    }

    def select_tone(
        self, sentiment: Sentiment, conversation: Optional[ConversationSentiment] = None,
    ) -> Dict[str, Any]:
        scores: Dict[str, float] = {}
        for name, profile in self.TONE_PROFILES.items():
            conds = profile["conditions"]
            if not conds:
                scores[name] = 0.5
                continue
            score = 0.0
            if "frustration" in conds and sentiment.frustration >= conds["frustration"]:
                score += 0.4
            if "confusion" in conds and sentiment.confusion >= conds["confusion"]:
                score += 0.4
            if "satisfaction" in conds and sentiment.satisfaction >= conds["satisfaction"]:
                score += 0.4
            if "valence" in conds:
                if conds["valence"] > 0 and sentiment.valence > conds["valence"]:
                    score += 0.3
                elif conds["valence"] < 0 and sentiment.valence < conds["valence"]:
                    score += 0.3
            scores[name] = score

        best = max(scores, key=lambda k: scores[k])
        result = dict(self.TONE_PROFILES[best])
        result["selected_tone"] = best
        result["score"] = round(scores[best], 3)
        return result


# ═══════════════════════════════════════════════════════════════════
# Skill Class
# ═══════════════════════════════════════════════════════════════════

@SkillRegistry.register
class SentimentAnalysisSkill(BaseSkill):
    """
    Multi-dimensional sentiment analysis with conversation trajectory.

    Tools:
      analyze_message      — Analyze a single message sentiment
      analyze_conversation — Full conversation trajectory analysis
      get_tone_recommendation — Adaptive tone for response
      get_sentiment_history — Recent analysis history
    """

    def __init__(self, config: Optional[SkillConfig] = None):
        super().__init__(config or SkillConfig(name="sentiment_analysis"))
        self._api = None
        self._llm_classifier: Optional[LLMSentimentClassifier] = None
        self._analyzer: Optional[SentimentAnalyzer] = None
        self._conv_analyzer: Optional[ConversationAnalyzer] = None
        self._tuner = ResponseTuner()
        self._analysis_count = 0

    @property
    def name(self) -> str:
        return "sentiment_analysis"

    async def initialize(self) -> bool:
        try:
            from aria_skills.api_client import get_api_client
            self._api = await get_api_client()
        except Exception as e:
            self.logger.warning(f"API client not available: {e}")

        use_llm = self.config.config.get("use_llm", True)
        if use_llm:
            self._llm_classifier = LLMSentimentClassifier()

        self._analyzer = SentimentAnalyzer(
            llm_classifier=self._llm_classifier,
            lexicon_weight=float(self.config.config.get("lexicon_weight", 0.3)),
            llm_weight=float(self.config.config.get("llm_weight", 0.7)),
        )
        self._conv_analyzer = ConversationAnalyzer(self._analyzer)

        self._status = SkillStatus.AVAILABLE
        self.logger.info("Sentiment analysis initialized (llm=%s, api=%s)",
                         use_llm, self._api is not None)
        return True

    async def health_check(self) -> SkillStatus:
        if self._analyzer is None:
            self._status = SkillStatus.UNAVAILABLE
        return self._status

    @logged_method()
    async def analyze_message(self, text: str = "", context: Optional[List[str]] = None,
                               store: bool = True, **kwargs) -> SkillResult:
        """Analyze sentiment of a single message."""
        text = text or kwargs.get("text", "")
        if not text:
            return SkillResult.fail("No text provided")

        sentiment = await self._analyzer.analyze(text, context)
        self._analysis_count += 1

        result_data = {
            "sentiment": sentiment.to_dict(),
            "derived": {
                "frustration": round(sentiment.frustration, 3),
                "satisfaction": round(sentiment.satisfaction, 3),
                "confusion": round(sentiment.confusion, 3),
            },
            "tone_recommendation": self._tuner.select_tone(sentiment),
            "analysis_count": self._analysis_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Store in semantic memory
        if store and self._api:
            try:
                await self._api.store_memory_semantic(
                    content=f"Sentiment: {sentiment.primary_emotion} "
                            f"(v={sentiment.valence:.2f}, a={sentiment.arousal:.2f}, d={sentiment.dominance:.2f})",
                    category="sentiment",
                    importance=max(0.3, abs(sentiment.valence)),
                    source="sentiment_analysis",
                    metadata={
                        "valence": sentiment.valence,
                        "arousal": sentiment.arousal,
                        "dominance": sentiment.dominance,
                        "frustration": sentiment.frustration,
                        "satisfaction": sentiment.satisfaction,
                        "primary_emotion": sentiment.primary_emotion,
                        "text_snippet": text[:100],
                    },
                )
            except Exception:
                pass  # non-blocking

        return SkillResult.ok(result_data)

    @logged_method()
    async def analyze_conversation(self, messages: Optional[List[Dict[str, Any]]] = None,
                                    store: bool = True, **kwargs) -> SkillResult:
        """Analyze sentiment trajectory of a full conversation."""
        messages = messages or kwargs.get("messages", [])
        if not messages:
            return SkillResult.fail("No messages provided")

        conv = await self._conv_analyzer.analyze_conversation(messages)
        result_data = conv.to_dict()
        result_data["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Store conversation summary in semantic memory
        if store and self._api and conv.overall:
            try:
                await self._api.store_memory_semantic(
                    content=(
                        f"Conversation sentiment: {conv.trajectory.value}, "
                        f"overall valence={conv.overall.valence:.2f}, "
                        f"volatility={conv.volatility:.2f}, "
                        f"resolution={conv.resolution or 'unknown'}, "
                        f"{conv.messages_analyzed} messages analyzed"
                    ),
                    category="sentiment_conversation",
                    importance=0.6,
                    source="sentiment_analysis",
                    metadata={
                        "trajectory": conv.trajectory.value,
                        "volatility": conv.volatility,
                        "resolution": conv.resolution,
                        "messages_analyzed": conv.messages_analyzed,
                        "overall_valence": conv.overall.valence,
                    },
                )
            except Exception:
                pass

        return SkillResult.ok(result_data)

    @logged_method()
    async def get_tone_recommendation(self, text: str = "", **kwargs) -> SkillResult:
        """Get adaptive tone recommendation for a message."""
        text = text or kwargs.get("text", "")
        if not text:
            return SkillResult.fail("No text provided")

        sentiment = await self._analyzer.analyze(text)
        tone = self._tuner.select_tone(sentiment)
        return SkillResult.ok({
            "sentiment": sentiment.to_dict(),
            "tone": tone,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @logged_method()
    async def get_sentiment_history(self, limit: int = 20, **kwargs) -> SkillResult:
        """Return recent sentiment analysis results from semantic memory."""
        limit = int(kwargs.get("limit", limit))

        # In-memory history from analyzer
        history = [s.to_dict() for s in list(self._analyzer.history)[-limit:]]

        # Also fetch from semantic storage if available
        stored: List[Dict[str, Any]] = []
        if self._api:
            try:
                result = await self._api.list_semantic_memories(
                    category="sentiment", limit=limit)
                if result.success and isinstance(result.data, dict):
                    stored = result.data.get("items", [])
                elif result.success and isinstance(result.data, list):
                    stored = result.data
            except Exception:
                pass

        # ── DB fallback: pull from activities + thoughts when no stored sentiment ──
        fallback: List[Dict[str, Any]] = []
        if not stored and not history and self._api:
            try:
                r = await self._api.get_activities(limit=limit * 3)
                if r.success:
                    acts = r.data if isinstance(r.data, list) else (r.data or {}).get("items", [])
                    for a in (acts or [])[:limit]:
                        details = a.get("details", {}) or {}
                        content = (
                            f"{a.get('action', '')} | {a.get('skill', '')} "
                            f"| {details.get('result_preview', '')[:200]}"
                        ).strip()
                        if len(content) > 10:
                            fallback.append({
                                "content": content,
                                "source": "activity_log_fallback",
                                "created_at": a.get("created_at", ""),
                            })
            except Exception:
                pass
            try:
                r = await self._api.get_thoughts(limit=limit)
                if r.success:
                    tlist = r.data if isinstance(r.data, list) else (r.data or {}).get("items", [])
                    for t in (tlist or []):
                        content = (t.get("content") or "").strip()
                        if len(content) > 10:
                            fallback.append({
                                "content": content,
                                "source": "thoughts_fallback",
                                "created_at": t.get("created_at", ""),
                            })
            except Exception:
                pass

        return SkillResult.ok({
            "session_history": history,
            "stored_history": stored,
            "fallback_data": fallback,
            "total_analyses_this_session": self._analysis_count,
        })

    async def close(self) -> None:
        self._api = None
        self._analyzer = None
        self._conv_analyzer = None
        self._status = SkillStatus.UNAVAILABLE
