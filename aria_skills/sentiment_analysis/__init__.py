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
        "thanks", "thank", "perfect", "wonderful", "fantastic", "yes", "correct",
        "right", "helpful", "clear", "understood", "understands", "nice",
        "brilliant", "superb", "beautiful", "glad", "pleased", "thrilled",
        "better", "best", "clean", "cleaner", "improved", "enjoy", "enjoyed",
        "like", "liked", "smooth", "prefer", "comfortable", "easy", "easier",
        "fine", "well", "solid", "neat", "cool", "impressive", "reliable",
        "fast", "quick", "efficient", "elegant", "smart", "working", "works",
        "sweet", "okay", "ok", "satisfied", "safe", "stable", "ready",
        # S-47: everyday warm/casual words for real conversations
        "fun", "dear", "hope", "hoping", "welcome", "promise", "free",
        "hello", "hi", "hey", "please", "congrats", "bravo", "cheers",
        "gentle", "kind", "generous", "grateful", "proud", "warm",
        "exciting", "interesting", "useful", "valuable", "lovely",
        "progress", "success", "successful", "done", "complete", "completed",
        "agreed", "absolutely", "exactly", "indeed", "definitely",
        "appreciate", "appreciated", "recommended", "approved",
    })

    NEGATIVE_WORDS = frozenset({
        "bad", "terrible", "awful", "hate", "angry", "frustrated", "confused",
        "wrong", "error", "fail", "failed", "stupid", "useless", "no", "not",
        "problem", "issue", "broken", "slow", "disappointed", "annoying",
        "boring", "ugly", "horrible", "worst", "bugs", "crash", "stuck",
        "worse", "painful", "messy", "unclear", "hard", "difficult", "missing",
        "lost", "confusing", "annoyed", "tired", "worried", "afraid", "scary",
        "impossible", "unreliable", "unstable", "laggy", "complicated", "sucks",
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
# Embedding-Based Classifier (pgvector cosine similarity)
# ═══════════════════════════════════════════════════════════════════

class EmbeddingSentimentClassifier:
    """Semantic sentiment classification via pgvector cosine similarity.

    How it works:
      1. Generate 768-dim embedding of the input text (nomic-embed-text).
      2. Query ``semantic_memories`` for the top-K nearest reference sentences
         where ``category = 'sentiment_reference'``.
      3. Compute distance-weighted votes across the neighbours to produce
         valence / arousal / dominance / primary_emotion.

    Reference sentences are seeded via the
    ``POST /analysis/sentiment/seed-references`` endpoint and accumulate
    organically through the feedback loop (high-confidence events → new
    references).

    This replaces the naïve lexicon look-up with a semantically-aware
    classifier that captures sarcasm, mixed sentiment, and domain-specific
    language — just like the skill knowledge-graph search works.
    """

    def __init__(
        self,
        api_base_url: str | None = None,
        api_key: str | None = None,
        top_k: int = 7,
        min_similarity: float = 0.40,
    ):
        self._litellm_url = api_base_url or os.environ.get("LITELLM_URL", "http://litellm:4000")
        self._litellm_key = api_key or os.environ.get("LITELLM_MASTER_KEY", "")
        self._top_k = top_k
        self._min_similarity = min_similarity
        # Internal API URL for DB queries (runs inside same container network)
        self._api_url = os.environ.get("ARIA_API_URL", "http://aria-api:8000")

    # ── embedding generation ────────────────────────────────────────
    async def _embed(self, text: str) -> List[float]:
        """Generate 768-dim embedding via LiteLLM proxy."""
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self._litellm_url}/v1/embeddings",
                json={"model": "nomic-embed-text", "input": text[:2000]},
                headers={"Authorization": f"Bearer {self._litellm_key}"},
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    # ── reference lookup via API ────────────────────────────────────
    async def _find_nearest_references(
        self, query_embedding: List[float],
    ) -> List[Dict[str, Any]]:
        """Search semantic_memories for nearest sentiment references.

        Uses the ``/memories/search`` endpoint which wraps pgvector
        ``cosine_distance`` ordering.
        """
        import httpx
        # The memories/search endpoint accepts a text query and does
        # embedding generation + cosine search server-side.
        # We need to call the DB directly via the internal API when we
        # already have an embedding.  Fall back to text search if needed.
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self._api_url}/api/memories/search-by-vector",
                json={
                    "embedding": query_embedding,
                    "category": "sentiment_reference",
                    "limit": self._top_k,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("memories", [])
        return []

    # ── classification ──────────────────────────────────────────────
    async def classify(self, text: str, context: Optional[List[str]] = None) -> Optional[Sentiment]:
        """Classify sentiment by comparing input embedding to reference corpus.

        Returns ``None`` when there are no reference sentences or when
        the nearest neighbours are too distant (below ``min_similarity``).
        The caller should fall back to LLM / lexicon when ``None`` is
        returned.
        """
        try:
            embedding = await self._embed(text)
        except Exception:
            return None

        refs = await self._find_nearest_references(embedding)
        if not refs:
            return None

        # Filter by minimum similarity
        valid = [r for r in refs if r.get("similarity", 0) >= self._min_similarity]
        if not valid:
            return None

        # Distance-weighted vote
        total_weight = 0.0
        w_valence = 0.0
        w_arousal = 0.0
        w_dominance = 0.0
        emotion_votes: Dict[str, float] = {}

        for ref in valid:
            sim = ref["similarity"]
            meta = ref.get("metadata", {}) or {}
            weight = sim ** 2  # quadratic weighting to favour close matches
            total_weight += weight

            w_valence += meta.get("valence", 0.0) * weight
            w_arousal += meta.get("arousal", 0.5) * weight
            w_dominance += meta.get("dominance", 0.5) * weight

            emotion = meta.get("primary_emotion", "neutral")
            emotion_votes[emotion] = emotion_votes.get(emotion, 0.0) + weight

        if total_weight == 0:
            return None

        avg_valence = w_valence / total_weight
        avg_arousal = w_arousal / total_weight
        avg_dominance = w_dominance / total_weight
        best_emotion = max(emotion_votes, key=emotion_votes.get)
        avg_sim = sum(r["similarity"] for r in valid) / len(valid)

        return Sentiment(
            valence=round(avg_valence, 4),
            arousal=round(avg_arousal, 4),
            dominance=round(avg_dominance, 4),
            confidence=round(min(1.0, avg_sim * 1.1), 4),  # slight boost
            primary_emotion=best_emotion,
            labels=[f"embedding_top{len(valid)}", f"avg_sim={avg_sim:.3f}"],
        )


# ═══════════════════════════════════════════════════════════════════
# LLM Classifier (via LiteLLM proxy)
# ═══════════════════════════════════════════════════════════════════

class LLMSentimentClassifier:
    """LLM-based sentiment classification for higher accuracy."""

    def __init__(self, model: str = None):
        self._litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
        self._litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")
        # Resolve model from models.yaml (Constraint #3) — fallback to free model
        if model:
            self._model = model
        else:
            try:
                from aria_models import load_config
                cfg = load_config()
                profiles = cfg.get("profiles", {})
                sentiment_profile = profiles.get("sentiment", profiles.get("routing", {}))
                self._model = sentiment_profile.get("model", "gpt-oss-small-free")
            except Exception:
                self._model = "gpt-oss-small-free"

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
                    "model": self._model,
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
    Multi-strategy sentiment engine.

    Priority order:
      1. **Embedding** (pgvector cosine similarity against labelled reference
         corpus) — most accurate, semantic-level understanding.
      2. **LLM** — used when embeddings return no confident match or when
         the lexicon is ambiguous.
      3. **Lexicon** — fastest fallback, always computed as a baseline.

    Blend weights (when multiple strategies fire):
      - embedding_weight  0.50
      - llm_weight        0.30
      - lexicon_weight    0.20
    """

    def __init__(
        self,
        llm_classifier: Optional[LLMSentimentClassifier] = None,
        embedding_classifier: Optional[EmbeddingSentimentClassifier] = None,
        lexicon_weight: float = 0.20,
        llm_weight: float = 0.30,
        embedding_weight: float = 0.50,
        use_llm_threshold: float = 0.6,
    ):
        self.llm_classifier = llm_classifier
        self.embedding_classifier = embedding_classifier
        self.lexicon_weight = lexicon_weight
        self.llm_weight = llm_weight
        self.embedding_weight = embedding_weight
        self.use_llm_threshold = use_llm_threshold
        self.history: deque = deque(maxlen=50)

    async def analyze(self, text: str, context: Optional[List[str]] = None) -> Sentiment:
        import logging
        log = logging.getLogger("aria.sentiment")

        # ── Step 1: fast lexicon (always computed as baseline) ───────
        l_val, l_aro, l_dom = SentimentLexicon.score(text)

        lexicon_matches = sum(
            1 for w in re.findall(r"\b\w+\b", text.lower())
            if w in SentimentLexicon.POSITIVE_WORDS or w in SentimentLexicon.NEGATIVE_WORDS
        )
        lexicon_confidence = min(1.0, max(0.3, lexicon_matches / 3) if lexicon_matches > 0 else 0.15)

        # ── Step 2: embedding classifier (highest priority) ────────
        emb_result: Optional[Sentiment] = None
        if self.embedding_classifier:
            try:
                emb_result = await self.embedding_classifier.classify(text, context)
            except Exception as e:
                log.warning("Embedding classify failed: %s", e)

        # ── Step 3: LLM (if embedding didn't produce a confident result) ──
        llm_result: Optional[Sentiment] = None
        needs_llm = (
            self.llm_classifier
            and (emb_result is None or emb_result.confidence < 0.55)
            and (lexicon_confidence < self.use_llm_threshold or abs(l_val) < 0.3)
        )
        if needs_llm:
            try:
                llm_result = await self.llm_classifier.classify(text, context)
            except Exception as e:
                log.warning("LLM classify failed: %s", e)

        # ── Step 4: build final blended result ─────────────────────
        sources_used: List[str] = ["lexicon"]
        strategies: List[Tuple[Sentiment, float]] = []

        # Always include lexicon
        lex_emotion = self._derive_lexicon_emotion(l_val, l_dom, text)
        lex_sentiment = Sentiment(
            valence=l_val, arousal=l_aro, dominance=l_dom,
            confidence=lexicon_confidence, primary_emotion=lex_emotion,
        )

        if emb_result is not None and llm_result is not None:
            # All three available — full blend
            strategies = [
                (emb_result, self.embedding_weight),
                (llm_result, self.llm_weight),
                (lex_sentiment, self.lexicon_weight),
            ]
            sources_used = ["embedding", "llm", "lexicon"]
        elif emb_result is not None:
            # Embedding + lexicon (no LLM)
            emb_w = self.embedding_weight + self.llm_weight * 0.6
            lex_w = self.lexicon_weight + self.llm_weight * 0.4
            strategies = [(emb_result, emb_w), (lex_sentiment, lex_w)]
            sources_used = ["embedding", "lexicon"]
        elif llm_result is not None:
            # LLM + lexicon (no embedding — legacy path)
            strategies = [
                (llm_result, 0.7),
                (lex_sentiment, 0.3),
            ]
            sources_used = ["llm", "lexicon"]
        else:
            # Lexicon only
            strategies = [(lex_sentiment, 1.0)]

        blended = self._blend(strategies, sources_used)
        self.history.append(blended)
        return blended

    # ── helpers ─────────────────────────────────────────────────────
    @staticmethod
    def _derive_lexicon_emotion(valence: float, dominance: float, text: str) -> str:
        """Derive primary_emotion from lexicon scores + word signals."""
        text_lower = text.lower()
        has_frustration = any(w in text_lower for w in ("frustrated", "frustrating", "annoying", "annoyed", "stuck"))
        has_confusion = any(w in text_lower for w in ("confused", "confusing", "unclear", "lost"))

        if valence <= -0.25 and has_frustration:
            return "frustrated"
        if valence <= -0.25 and has_confusion:
            return "confused"
        if valence >= 0.25:
            return "happy"
        if valence <= -0.25:
            return "sad"
        if dominance > 0.4:
            return "assertive"
        return "neutral"

    @staticmethod
    def _blend(
        strategies: List[Tuple[Sentiment, float]],
        sources: List[str],
    ) -> Sentiment:
        """Weighted blend of multiple Sentiment results."""
        total_w = sum(w for _, w in strategies)
        if total_w == 0:
            return strategies[0][0]

        val = sum(s.valence * w for s, w in strategies) / total_w
        aro = sum(s.arousal * w for s, w in strategies) / total_w
        dom = sum(s.dominance * w for s, w in strategies) / total_w
        conf = max(s.confidence for s, _ in strategies)

        # Pick emotion from the highest-weighted strategy
        best_s = max(strategies, key=lambda x: x[1])[0]
        emotion = best_s.primary_emotion
        labels = list(best_s.labels) + [f"blend={'+'.join(sources)}"]

        return Sentiment(
            valence=round(val, 4),
            arousal=round(aro, 4),
            dominance=round(dom, 4),
            confidence=round(conf, 4),
            primary_emotion=emotion,
            labels=labels,
        )


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
        self._embedding_classifier: Optional[EmbeddingSentimentClassifier] = None
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

        # Embedding classifier — uses pgvector cosine similarity
        use_embedding = self.config.config.get("use_embedding", True)
        if use_embedding:
            self._embedding_classifier = EmbeddingSentimentClassifier()

        self._analyzer = SentimentAnalyzer(
            llm_classifier=self._llm_classifier,
            embedding_classifier=self._embedding_classifier,
            lexicon_weight=float(self.config.config.get("lexicon_weight", 0.20)),
            llm_weight=float(self.config.config.get("llm_weight", 0.30)),
            embedding_weight=float(self.config.config.get("embedding_weight", 0.50)),
        )
        self._conv_analyzer = ConversationAnalyzer(self._analyzer)

        self._status = SkillStatus.AVAILABLE
        self.logger.info("Sentiment analysis initialized (embedding=%s, llm=%s, api=%s)",
                         use_embedding, use_llm, self._api is not None)
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
