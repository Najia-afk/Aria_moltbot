"""
Sentiment Analysis Prototype
Multi-dimensional sentiment tracking for conversations.

Dimensions:
- Valence: Positive vs negative (-1 to +1)
- Arousal: Calm vs excited (0 to 1)
- Dominance: Submissive vs dominant (0 to 1)

Derived metrics:
- Frustration (high arousal + negative valence)
- Satisfaction (positive valence + high dominance)
- Confusion (low dominance + neutral valence)
"""

from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import re


# ===========================
# Data Models
# ===========================

class Trajectory(Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass
class Sentiment:
    """Single message sentiment analysis."""
    valence: float  # -1 (negative) to +1 (positive)
    arousal: float  # 0 (calm) to 1 (excited)
    dominance: float  # 0 (submissive) to 1 (dominant)
    confidence: float = 0.8
    primary_emotion: str = "neutral"
    labels: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @property
    def frustration(self) -> float:
        """Frustration = high arousal + negative valence."""
        if self.valence >= 0:
            return 0.0
        return self.arousal * abs(self.valence)

    @property
    def satisfaction(self) -> float:
        """Satisfaction = positive valence + high dominance."""
        if self.valence <= 0:
            return 0.0
        return self.valence * self.dominance

    @property
    def confusion(self) -> float:
        """Confusion = low dominance + neutral valence."""
        valence_near_zero = 1 - abs(self.valence)  # Closer to zero = higher
        return (1 - self.dominance) * valence_near_zero * 0.5


@dataclass
class ConversationSentiment:
    """Aggregate sentiment across a conversation."""
    overall: Sentiment
    trajectory: Trajectory
    turning_points: list[dict[str, Any]] = field(default_factory=list)
    peak_positive: Sentiment | None = None
    peak_negative: Sentiment | None = None
    volatility: float = 0.0  # Standard deviation of valence
    resolution: str | None = None  # "positive", "negative", "neutral"
    messages_analyzed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data["trajectory"] = self.trajectory.value
        if self.overall:
            data["overall"] = self.overall.to_dict()
        if self.peak_positive:
            data["peak_positive"] = self.peak_positive.to_dict()
        if self.peak_negative:
            data["peak_negative"] = self.peak_negative.to_dict()
        return data


@dataclass
class SentimentTrend:
    """Trend analysis over time."""
    direction: str  # "up", "down", "flat"
    slope: float
    confidence: float
    window_messages: int
    start_valence: float
    end_valence: float


# ===========================
# Lexicon-Based Analyzer
# ===========================

class SentimentLexicon:
    """Simple lexicon for quick sentiment scoring."""

    POSITIVE_WORDS = {
        "good", "great", "excellent", "awesome", "amazing", "love", "happy",
        "thanks", "thank you", "perfect", "wonderful", "fantastic", "yes",
        "correct", "right", "helpful", "clear", "understood", "understands"
    }

    NEGATIVE_WORDS = {
        "bad", "terrible", "awful", "hate", "angry", "frustrated", "confused",
        "wrong", "error", "fail", "failed", "stupid", "useless", "no", "not",
        "problem", "issue", "broken", "slow", "useless", "disappointed"
    }

    EXCITED_WORDS = {
        "wow", "amazing!", "incredible!", "excited", " thrilled", "yay",
        "!!", "!!!", "?", "?!!!"
    }

    DOMINANT_WORDS = {
        "must", "should", "need", "require", "demand", "tell me", "explain",
        "make", "create", "build", "do this", "find out"
    }

    @classmethod
    def score(cls, text: str) -> tuple[float, float, float]:
        """
        Quick lexicon-based sentiment scoring.

        Returns: (valence, arousal, dominance)
        """
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        # Valence
        pos_count = sum(1 for w in words if w in cls.POSITIVE_WORDS)
        neg_count = sum(1 for w in words if w in cls.NEGATIVE_WORDS)
        total = len(words) if words else 1
        valence = (pos_count - neg_count) / max(total, 1)
        valence = max(-1, min(1, valence * 3))  # Scale and clamp

        # Arousal (exclamation marks + excited words)
        exclamation_count = text.count('!')
        excited_count = sum(1 for w in words if w in cls.EXCITED_WORDS)
        arousal = (excited_count * 0.5 + exclamation_count * 0.1) / max(total, 1)
        arousal = max(0, min(1, arousal * 5))

        # Dominance (command words, assertions)
        dominant_count = sum(1 for w in words if w in cls.DOMINANT_WORDS)
        dominance = dominant_count / max(total, 1)
        dominance = max(0, min(1, dominance * 5))

        return valence, arousal, dominance


# ===========================
# LLM Classifier (Optional)
# ===========================

class LLMSentimentClassifier:
    """LLM-based sentiment classification for higher accuracy."""

    def __init__(self, llm_skill=None):
        self.llm = llm_skill

    async def classify(
        self,
        text: str,
        context: list[str] = None
    ) -> Sentiment:
        """
        Classify sentiment using LLM.

        Returns Sentiment object with dimensions.
        """
        if not self.llm:
            raise ValueError("No LLM skill provided")

        prompt = self._build_prompt(text, context)

        try:
            result = await self.llm.generate(prompt)
            parsed = json.loads(result)

            return Sentiment(
                valence=float(parsed.get("valence", 0)),
                arousal=float(parsed.get("arousal", 0.5)),
                dominance=float(parsed.get("dominance", 0.5)),
                confidence=float(parsed.get("confidence", 0.9)),
                primary_emotion=parsed.get("primary_emotion", "neutral"),
                labels=parsed.get("labels", [])
            )
        except Exception as e:
            # Fallback to lexicon
            valence, arousal, dominance = SentimentLexicon.score(text)
            return Sentiment(
                valence=valence,
                arousal=arousal,
                dominance=dominance,
                confidence=0.6
            )

    def _build_prompt(self, text: str, context: list[str] = None) -> str:
        """Build prompt for LLM sentiment analysis."""
        context_str = ""
        if context:
            context_str = "\nPrevious messages:\n" + "\n".join(f"- {c}" for c in context[-3:])

        prompt = f"""Analyze sentiment of this message:

Message: "{text}"

{context_str}

Score on these dimensions (range -1 to +1 for valence, 0-1 for others):
- valence: positive vs negative
- arousal: calm vs excited
- dominance: submissive vs assertive

Also identify:
- primary_emotion: one of [neutral, happy, angry, frustrated, confused, excited, sad, satisfied]
- labels: other relevant emotion tags

Return as JSON only:
{{"valence": float, "arousal": float, "dominance": float, "confidence": float, "primary_emotion": str, "labels": [str]}}
"""
        return prompt


# ===========================
# Sentiment Analyzer
# ===========================

class SentimentAnalyzer:
    """
    Main sentiment analysis engine with multi-strategy approach.
    """

    def __init__(
        self,
        llm_classifier: LLMSentimentClassifier | None = None,
        lexicon_weight: float = 0.3,
        llm_weight: float = 0.7,
        use_llm_threshold: float = 0.6  # Use LLM if lexicon confidence < threshold
    ):
        self.llm_classifier = llm_classifier
        self.lexicon_weight = lexicon_weight
        self.llm_weight = llm_weight
        self.use_llm_threshold = use_llm_threshold
        self.conversation_history: deque = deque(maxlen=50)

    async def analyze(
        self,
        text: str,
        context: list[str] = None
    ) -> Sentiment:
        """
        Analyze sentiment of a single message.

        Strategy:
        1. Fast lexicon scoring (baseline)
        2. If lexicon score is ambiguous (valence near 0), use LLM
        3. Blend both scores
        """
        # Lexicon scoring
        l_valence, l_arousal, l_dominance = SentimentLexicon.score(text)

        # Estimate lexicon confidence (based on word matches)
        lexicon_matches = sum(
            1 for w in re.findall(r'\b\w+\b', text.lower())
            if w in SentimentLexicon.POSITIVE_WORDS
            or w in SentimentLexicon.NEGATIVE_WORDS
        )
        lexicon_confidence = min(1.0, lexicon_matches / 5)

        # Determine if LLM should be used
        should_use_llm = (
            self.llm_classifier and
            (lexicon_confidence < self.use_llm_threshold or
             abs(l_valence) < 0.3)  # Ambiguous valence
        )

        if should_use_llm:
            try:
                llm_sentiment = await self.llm_classifier.classify(text, context)
                # Blend lexicon + LLM
                blended = self._blend(
                    (l_valence, l_arousal, l_dominance, lexicon_confidence),
                    llm_sentiment,
                    self.lexicon_weight,
                    self.llm_weight
                )
                return blended
            except Exception as e:
                # LLM failed, use lexicon only
                return Sentiment(
                    valence=l_valence,
                    arousal=l_arousal,
                    dominance=l_dominance,
                    confidence=lexicon_confidence
                )
        else:
            # Use lexicon only
            return Sentiment(
                valence=l_valence,
                arousal=l_arousal,
                dominance=l_dominance,
                confidence=lexicon_confidence
            )

    def _blend(
        self,
        lexicon_scores: tuple[float, float, float, float],
        llm_sentiment: Sentiment,
        w_lex: float,
        w_llm: float
    ) -> Sentiment:
        """Blend lexicon and LLM scores."""
        l_val, l_aro, l_dom, l_conf = lexicon_scores

        blended_val = (l_val * w_lex + llm_sentiment.valence * w_llm)
        blended_aro = (l_aro * w_lex + llm_sentiment.arousal * w_llm)
        blended_dom = (l_dom * w_lex + llm_sentiment.dominance * w_llm)

        return Sentiment(
            valence=blended_val,
            arousal=blended_aro,
            dominance=blended_dom,
            confidence=max(l_conf, llm_sentiment.confidence),
            primary_emotion=llm_sentiment.primary_emotion,
            labels=llm_sentiment.labels
        )


# ===========================
# Conversation Analyzer
# ===========================

class ConversationAnalyzer:
    """
    Analyze sentiment trajectory across a full conversation.
    """

    def __init__(self, sentiment_analyzer: SentimentAnalyzer):
        self.analyzer = sentiment_analyzer
        self.sentiment_history: list[Sentiment] = []

    async def analyze_conversation(
        self,
        messages: list[dict[str, Any]],
        window_size: int = 10
    ) -> ConversationSentiment:
        """
        Analyze sentiment trajectory of a conversation.

        Args:
            messages: List of {"content": str, "timestamp": datetime, ...}
            window_size: Rolling window for trend analysis

        Returns:
            ConversationSentiment with overall metrics and trajectory
        """
        if not messages:
            return ConversationSentiment(
                overall=Sentiment(valence=0, arousal=0, dominance=0),
                trajectory=Trajectory.INSUFFICIENT_DATA
            )

        # Analyze each message
        sentiments = []
        for msg in messages:
            context = [m["content"] for m in messages[-3:] if m != msg]
            sentiment = await self.analyzer.analyze(msg["content"], context)
            sentiments.append(sentiment)

        self.sentiment_history.extend(sentiments)

        # Calculate overall (weighted average, recent messages weighted more)
        weights = [0.5 ** (len(sentiments) - i - 1) for i in range(len(sentiments))]
        total_weight = sum(weights)

        overall_valence = sum(s.valence * w for s, w in zip(sentiments, weights)) / total_weight
        overall_arousal = sum(s.arousal * w for s, w in zip(sentiments, weights)) / total_weight
        overall_dominance = sum(s.dominance * w for s, w in zip(sentiments, weights)) / total_weight

        overall = Sentiment(
            valence=overall_valence,
            arousal=overall_arousal,
            dominance=overall_dominance,
            confidence=min(1.0, len(sentiments) / 5)
        )

        # Trajectory (sliding window comparison)
        trajectory = self._compute_trajectory(sentiments, window_size)

        # Volatility
        import statistics
        valence_values = [s.valence for s in sentiments]
        volatility = statistics.stdev(valence_values) if len(valence_values) > 1 else 0.0

        # Peaks
        peak_positive = max(sentiments, key=lambda s: s.valence)
        peak_negative = min(sentiments, key=lambda s: s.valence)

        # Turning points (significant shifts)
        turning_points = self._find_turning_points(sentiments)

        # Resolution (conversation ending tone)
        if len(sentiments) >= 3:
            last_three_valence = sum(s.valence for s in sentiments[-3:]) / 3
            if last_three_valence > 0.3:
                resolution = "positive"
            elif last_three_valence < -0.3:
                resolution = "negative"
            else:
                resolution = "neutral"
        else:
            resolution = None

        return ConversationSentiment(
            overall=overall,
            trajectory=trajectory,
            turning_points=turning_points,
            peak_positive=peak_positive,
            peak_negative=peak_negative,
            volatility=volatility,
            resolution=resolution,
            messages_analyzed=len(mentions)
        )

    def _compute_trajectory(
        self,
        sentiments: list[Sentiment],
        window: int = 10
    ) -> Trajectory:
        """Determine if conversation sentiment is improving, declining, or stable."""
        if len(sentiments) < 4:
            return Trajectory.INSUFFICIENT_DATA

        # Compare first half to second half
        mid = len(sentiments) // 2
        first_half = sentiments[:mid]
        second_half = sentiments[mid:]

        first_avg = sum(s.valence for s in first_half) / len(first_half)
        second_avg = sum(s.valence for s in second_half) / len(second_half)

        diff = second_avg - first_avg

        if diff > 0.3:
            return Trajectory.IMPROVING
        elif diff < -0.3:
            return Trajectory.DECLINING
        else:
            return Trajectory.STABLE

    def _find_turning_points(
        self,
        sentiments: list[Sentiment],
        threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        """Find points where sentiment changed significantly."""
        turning_points = []

        if len(sentiments) < 3:
            return turning_points

        for i in range(1, len(sentiments) - 1):
            prev = sentiments[i - 1].valence
            curr = sentiments[i].valence
            next_v = sentiments[i + 1].valence

            # Check for significant reversal
            if abs(curr - prev) > threshold and abs(curr - next_v) > threshold:
                direction = "up" if curr > prev else "down"
                turning_points.append({
                    "index": i,
                    "valence": curr,
                    "direction": direction,
                    "change_magnitude": abs(curr - prev)
                })

        return turning_points


# ===========================
# Adaptive Response Tuner
# ===========================

class ResponseTuner:
    """
    Adjust response style based on sentiment analysis.
    """

    def __init__(self):
        self.tone_profiles = {
            "empathetic_supportive": {
                "conditions": {"frustration": 0.7, "valence": -0.5},
                "tone": "warm, validating, solution-oriented",
                "strategies": ["acknowledge_emotion", "apologize_if_needed", "offer_clear_steps"]
            },
            "clear_step_by_step": {
                "conditions": {"confusion": 0.6, "arousal": 0.3},
                "tone": "methodical, explicit, examples",
                "strategies": ["break_down_steps", "use_examples", "check_for_understanding"]
            },
            "friendly_celebratory": {
                "conditions": {"satisfaction": 0.8, "valence": 0.6},
                "tone": "enthusiastic, congratulatory",
                "strategies": ["positive_reinforcement", "celebrate_success", "offer_next_steps"]
            },
            "neutral_professional": {
                "conditions": {},
                "tone": "balanced, efficient",
                "strategies": ["direct_response", "brief_context", "offer_help"]
            }
        }

    def select_tone(
        self,
        sentiment: Sentiment,
        conversation_sentiment: ConversationSentiment | None = None
    ) -> dict[str, Any]:
        """
        Select response tone based on sentiment.

        Returns:
            Tone profile with instructions
        """
        scores = {}

        for tone_name, profile in self.tone_profiles.items():
            if not profile["conditions"]:
                scores[tone_name] = 0.5  # Neutral default
                continue

            score = 0.0
            conditions = profile["conditions"]

            if "frustration" in conditions and sentiment.frustration >= conditions["frustration"]:
                score += 0.4
            if "confusion" in conditions and sentiment.confusion >= conditions["confusion"]:
                score += 0.4
            if "satisfaction" in conditions and sentiment.satisfaction >= conditions["satisfaction"]:
                score += 0.4
            if "valence" in conditions:
                if conditions["valence"] > 0 and sentiment.valence > conditions["valence"]:
                    score += 0.3
                elif conditions["valence"] < 0 and sentiment.valence < conditions["valence"]:
                    score += 0.3

            scores[tone_name] = score

        # Select highest scoring tone
        best_tone = max(scores, key=scores.get) if scores else "neutral_professional"

        return self.tone_profiles[best_tone].copy()


# ===========================
# Utility Functions
# ===========================

async def analyze_sentiment_workflow(
    messages: list[dict[str, Any]],
    config: dict[str, Any] = None
) -> dict[str, Any]:
    """
    Complete sentiment analysis workflow.

    Usage:
        result = await analyze_sentiment_workflow(
            messages=[{"content": "Hello!"}, ...],
            config={"use_llm": True}
        )
    """
    config = config or {}
    use_llm = config.get("use_llm", False)

    llm_classifier = None
    if use_llm:
        # Initialize LLM classifier (requires llm skill)
        # from skills.llm import LLMSkill
        # llm = LLMSkill(config)
        # await llm.initialize()
        # llm_classifier = LLMSentimentClassifier(llm)
        pass

    analyzer = SentimentAnalyzer(llm_classifier=llm_classifier)
    conv_analyzer = ConversationAnalyzer(analyzer)

    result = await conv_analyzer.analyze_conversation(messages)

    return {
        "success": True,
        "overall_sentiment": result.overall.to_dict(),
        "trajectory": result.trajectory.value,
        "resolution": result.resolution,
        "volatility": result.volatility,
        "peak_positive": result.peak_positive.to_dict() if result.peak_positive else None,
        "peak_negative": result.peak_negative.to_dict() if result.peak_negative else None,
        "turning_points": result.turning_points,
        "messages_analyzed": result.messages_analyzed,
        "tone_recommendation": ResponseTuner().select_tone(result.overall, result)
    }


# ===========================
# Example Usage
# ===========================

if __name__ == "__main__":
    # Example messages
    messages = [
        {"content": "I'm really frustrated with this system!", "timestamp": datetime.now(timezone.utc)},
        {"content": "Okay, that makes sense. Thanks!", "timestamp": datetime.now(timezone.utc)},
    ]

    result = asyncio.run(analyze_sentiment_workflow(messages))
    print(json.dumps(result, indent=2, default=str))
