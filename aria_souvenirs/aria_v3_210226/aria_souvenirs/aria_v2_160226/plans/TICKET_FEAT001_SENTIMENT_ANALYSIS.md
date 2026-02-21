# Sprint Ticket: FEAT-001 — Simplified Sentiment Analysis
**Priority:** P1 | **Points:** 2 | **Phase:** 2  
**Estimate:** 30 minutes

## Problem
Aria has no sentiment awareness — cannot detect user frustration, satisfaction, or confusion. This leads to tone-deaf responses during debugging sessions or when the user is excited.

## Root Cause
No sentiment analysis exists in the cognitive loop. The prototype (`sentiment_analysis.py`, 631 lines) is over-engineered with a broken lexicon, crash bugs, and a full VAD model. The simplified version (`SENTIMENT_SIMPLIFIED.md`) outlines a 20-line approach that covers 90% of value.

## Architecture Decision
**YAGNI applied.** Per `SENTIMENT_SIMPLIFIED.md`:
- No lexicon (too small to be useful — use LLM or simple keyword detection)
- No VAD model (no calibration data exists)
- No RL dashboard (no user feedback data yet)
- Store results via existing `api_client.store_memory_semantic()`

## Implementation

### File: `aria_skills/sentiment_analysis/__init__.py` (NEW)

```python
"""Lightweight sentiment detection — stores results via semantic memory."""
import re
from aria_skills.base import BaseSkill, SkillConfig, SkillResult, SkillStatus, logged_method
from aria_skills.registry import SkillRegistry

# Simple keyword patterns (covers 80% of cases)
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


def detect_sentiment(text: str) -> dict:
    """Quick rule-based sentiment detection. Returns category + confidence."""
    text_lower = text.lower().strip()
    if not text_lower:
        return {"sentiment": "neutral", "confidence": 0.5, "signals": []}

    signals = []
    scores = {"frustration": 0.0, "satisfaction": 0.0, "confusion": 0.0}

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
    dominant = max(scores, key=scores.get)
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

    def __init__(self, config: SkillConfig | None = None):
        super().__init__(config or SkillConfig(name="sentiment_analysis"))

    @property
    def name(self) -> str:
        return "sentiment_analysis"

    async def initialize(self) -> None:
        self._status = SkillStatus.READY

    async def health_check(self) -> SkillResult:
        return SkillResult.ok({"status": "healthy", "type": "rule-based"})

    @logged_method()
    async def analyze_sentiment(self, text: str = "", **kwargs) -> SkillResult:
        """Analyze sentiment of a text message."""
        text = text or kwargs.get("text", "")
        if not text:
            return SkillResult.fail("text is required")

        result = detect_sentiment(text)

        # Store significant sentiment to semantic memory (if api_client available)
        if result["confidence"] >= 0.7 and result["sentiment"] != "neutral":
            try:
                api = self._get_api_client()
                if api:
                    await api.store_memory_semantic(
                        content=f"User sentiment: {result['dominant_emotion']} — \"{text[:200]}\"",
                        category="sentiment",
                        importance=min(0.9, result["confidence"]),
                        metadata={"sentiment": result, "source": "sentiment_analysis"},
                    )
            except Exception:
                pass  # Graceful degradation — sentiment still returned

        return SkillResult.ok(result)

    def _get_api_client(self):
        """Try to get api_client from config or import."""
        try:
            from aria_skills.api_client import AriaAPIClient
            return AriaAPIClient()
        except ImportError:
            return None

    async def close(self) -> None:
        self._status = SkillStatus.UNAVAILABLE
```

### File: `aria_skills/sentiment_analysis/skill.json` (NEW)

```json
{
  "name": "sentiment_analysis",
  "canonical_name": "aria-sentiment",
  "version": "1.0.0",
  "description": "Lightweight sentiment analysis — detects frustration, satisfaction, confusion",
  "layer": "L2",
  "focus_affinity": ["communication", "data"],
  "tools": [
    {
      "name": "analyze_sentiment",
      "description": "Detect sentiment (frustration/satisfaction/confusion) in text",
      "parameters": {
        "text": {"type": "string", "required": true, "description": "Text to analyze"}
      }
    }
  ],
  "dependencies": [],
  "rate_limit": {"max_per_minute": 60}
}
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | YES | Uses api_client for semantic storage, no direct DB |
| 2 | .env for secrets | N/A | No secrets needed |
| 3 | models.yaml source of truth | N/A | No model references (rule-based) |
| 4 | Docker-first testing | YES | Test via run_skill.py |
| 5 | aria_memories only writable | YES | Stores via API, not filesystem |
| 6 | No soul modification | N/A | |

## Dependencies
- BUG-001 should be done first (general stability)
- `api_client` must be available for semantic storage (graceful degradation if not)

## Verification
```bash
# 1. Skill files exist:
ls aria_skills/sentiment_analysis/__init__.py aria_skills/sentiment_analysis/skill.json
# EXPECTED: both files listed

# 2. Python syntax valid:
python3 -c "from aria_skills.sentiment_analysis import detect_sentiment; print(detect_sentiment('this is broken and frustrating'))"
# EXPECTED: {'sentiment': 'negative', 'dominant_emotion': 'frustration', ...}

# 3. Positive detection:
python3 -c "from aria_skills.sentiment_analysis import detect_sentiment; print(detect_sentiment('thanks, that works perfectly!'))"
# EXPECTED: {'sentiment': 'positive', 'dominant_emotion': 'satisfaction', ...}

# 4. Neutral detection:
python3 -c "from aria_skills.sentiment_analysis import detect_sentiment; print(detect_sentiment('please list the files'))"
# EXPECTED: {'sentiment': 'neutral', ...}
```
