```skill
---
name: aria-sentiment-analysis
description: "ðŸ’­ Multi-dimensional sentiment analysis with adaptive tone"
metadata: {"aria": {"emoji": "ðŸ’­"}}
---

# aria-sentiment-analysis

Multi-dimensional sentiment analysis engine. Detects valence, arousal, and
dominance across messages. Derives frustration, satisfaction, and confusion
scores. Blends fast lexicon analysis with LLM classification. Tracks
conversation trajectories and recommends adaptive response tones.

## Architecture

```
User text
    â†“
SentimentLexicon (fast, ~30% weight)
    + LLMSentimentClassifier (kimi model, ~70% weight when ambiguous)
    â†“
SentimentAnalyzer â†’ Sentiment(valence, arousal, dominance, primary_emotion)
    â†“                      â†“
ConversationAnalyzer    ResponseTuner
(trajectory, volatility, (empathetic / step-by-step /
 turning points)         celebratory / neutral)
    â†“
SemanticMemory (category: sentiment / sentiment_conversation)
```

## Integration

Hooked into `aria_mind/cognition.py` at Step 2.1 â€” every user message gets
automatic sentiment analysis. The derived sentiment and tone recommendation
are injected into the context dict for downstream agent use.

## Usage

```bash
# Analyze a single message
exec python3 /app/skills/run_skill.py sentiment_analysis analyze_message '{"text": "This is really frustrating, nothing works!"}'

# Analyze full conversation trajectory
exec python3 /app/skills/run_skill.py sentiment_analysis analyze_conversation '{"messages": [{"role": "user", "content": "help me"}, {"role": "assistant", "content": "sure!"}]}'

# Get tone recommendation for response tuning
exec python3 /app/skills/run_skill.py sentiment_analysis get_tone_recommendation '{"text": "I keep getting errors"}'

# View sentiment history
exec python3 /app/skills/run_skill.py sentiment_analysis get_sentiment_history '{"limit": 20}'
```

## Functions

### analyze_message
Analyze sentiment of a single message. Returns valence (-1 to 1), arousal,
dominance, primary emotion, derived frustration/satisfaction/confusion scores,
and an adaptive tone recommendation. Stores result in semantic memory.

### analyze_conversation
Analyze sentiment trajectory of a full conversation. Detects whether the
conversation is improving, declining, stable, or volatile. Identifies
turning points and peak sentiment moments.

### get_tone_recommendation
Quick tone recommendation without storing â€” returns one of 4 profiles:
- **empathetic**: High frustration â†’ acknowledge + gentle guidance
- **step-by-step**: High confusion â†’ structured walkthrough
- **celebratory**: High satisfaction â†’ reinforce success
- **neutral**: Default balanced tone

### get_sentiment_history
Return recent sentiment events from both the in-memory session history
and the persistent semantic memory storage.

## Dependencies
- `api_client` (semantic memory storage)
- LiteLLM proxy (kimi model for LLM classification)
```
