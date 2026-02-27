# Self-Healing Error Recovery System - Design Doc

## Overview
Automatic error detection, retry, and recovery for Aria's skills and API operations.

## Components

### 1. Error Classifier (`error_classifier.py`)
- Categorizes errors: transient, persistent, auth, rate-limit, fatal
- Uses regex patterns + LLM fallback for unknown errors

### 2. Retry Engine (`retry_engine.py`)
- Exponential backoff with jitter
- Max retry attempts: 3 (configurable per skill)
- Circuit breaker pattern for cascading failures

### 3. Recovery Strategies
| Error Type | Strategy |
|-----------|----------|
| Transient | Retry with backoff |
| Rate Limit | Exponential backoff + queue |
| Auth | Refresh token once, then alert |
| Timeout | Retry with increased timeout |
| Fatal | Log + alert + skip |

### 4. Health Integration
- Failed operations increment error counter
- After 3 failures in 5 min → health check triggered
- Auto-disable flaky skills after threshold

## Implementation Plan
- [x] Design document (this file)
- [x] Error classifier module (completed 2026-02-20, saved to aria_memories/exports/)
- [ ] Retry engine with backoff
- [ ] Circuit breaker integration (partial - recovery.py exists)
- [ ] Health monitoring hooks
- [ ] Skill wrapper decorator

## Progress: 50% → 60%

## Component Details

### ErrorClassifier (v1.0)
Location: `aria_memories/exports/error_classifier.py`

Features:
- Pattern-based classification using regex
- 6 error types: TRANSIENT, TIMEOUT, RATE_LIMIT, AUTH, FATAL, PERSISTENT
- Confidence scoring (0.0-1.0)
- Recovery strategy per type (retry flags, delays, max retries)
- Stats tracking for monitoring
- Convenience function: `classify_error(message, code)`

Usage:
```python
from error_classifier import classify_error, ErrorClassifier

# Quick classification
result = classify_error("Connection reset by peer")
# → ErrorType.TRANSIENT, retry=True, delay=1s, max_retries=3

# Full classifier with history
classifier = ErrorClassifier()
for error in errors:
    classification = classifier.classify(error)
    if classification.retry_recommended:
        retry_with_delay(classification.retry_delay_seconds)
```

### Next Steps
1. Implement retry engine with exponential backoff
2. Integrate classifier into skill wrapper
3. Add health monitoring hooks to track failure rates
