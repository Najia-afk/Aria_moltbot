```skill
---
name: aria-pattern-recognition
description: "🔍 Behavioral pattern detection in memory streams"
metadata: {"aria": {"emoji": "🔍"}}
---

# aria-pattern-recognition

Behavioral pattern detection engine. Analyzes memory streams to find
recurring topics, temporal habits, sentiment drift, emerging interests,
and knowledge gaps. Stores detected patterns in semantic memory.

## Architecture

```
Memory stream (list of memory dicts)
    ↓
TopicExtractor (9 keyword domains + entity regex + tech regex)
    ↓
FrequencyTracker (sliding window, default 30 days)
    ↓
PatternRecognizer
    ├── Topic recurrence (repeated subjects)
    ├── Interest emergence (growth rate analysis)
    ├── Temporal patterns (peak hours, active days)
    ├── Sentiment drift (valence trend over time)
    └── Knowledge gaps (repeated questions)
    ↓
SemanticMemory (category: pattern_detection)
```

## Pattern Types

| Type | Description | Detection Method |
|------|-------------|-----------------|
| `topic_recurrence` | Same topic appears repeatedly | Frequency ≥ min threshold |
| `interest_emergence` | New topic growing rapidly | Recent/historical ratio ≥ growth rate |
| `temporal` | Usage patterns by hour/day | Peak hour and active day analysis |
| `sentiment_drift` | Emotional trend over time | Linear regression on valence |
| `knowledge_gap` | Same question asked repeatedly | Question mark + recurrence |

## Usage

```bash
# Run full pattern detection (auto-fetches memories if empty)
exec python3 /app/skills/run_skill.py pattern_recognition detect_patterns '{}'

# With explicit memories and confidence threshold
exec python3 /app/skills/run_skill.py pattern_recognition detect_patterns '{"min_confidence": 0.5}'

# Get recurring topics
exec python3 /app/skills/run_skill.py pattern_recognition get_recurring '{"min_frequency": 0.3}'

# Get emerging interests
exec python3 /app/skills/run_skill.py pattern_recognition get_emerging '{"min_growth_rate": 2.0}'

# Check detection stats
exec python3 /app/skills/run_skill.py pattern_recognition get_pattern_stats '{}'
```

## Functions

### detect_patterns
Run full pattern detection on a list of memories. If no memories provided,
auto-fetches from semantic memory via api_client. Stores top 20 detected
patterns back into semantic memory with confidence scores.

### get_recurring
Get topics that appear with frequency above a threshold (events per day).
Uses the internal frequency tracker's sliding window.

### get_emerging
Get topics that are growing rapidly (recent frequency ÷ historical
frequency ≥ growth rate multiplier).

### get_pattern_stats
Get statistics from the last detection run — pattern counts by type,
new vs persistent patterns, analysis window.

## Web Dashboard

Available at `/patterns` in the Aria web UI. Features:
- Chart.js doughnut chart (patterns by type)
- Confidence distribution bar chart
- Pattern list with color-coded type indicators
- Type filter dropdown
- "Run Detection" button

## Dependencies
- `api_client` (semantic memory for storage and retrieval)
```
