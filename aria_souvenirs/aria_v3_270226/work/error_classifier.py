# aria_skills/health/error_classifier.py
"""
Error classifier for self-healing system.

Categorizes errors into types: transient, persistent, auth, rate-limit, timeout, fatal.
Uses regex pattern matching with LLM fallback for unknown errors.

Part of Aria's self-healing system (TICKET-36).
"""
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Pattern


class ErrorType(Enum):
    """Categories of errors for recovery strategy selection."""
    TRANSIENT = "transient"      # Temporary, retry likely succeeds
    PERSISTENT = "persistent"    # Requires fix, retry won't help
    AUTH = "auth"                # Authentication/authorization issue
    RATE_LIMIT = "rate_limit"    # Too many requests
    TIMEOUT = "timeout"          # Operation timed out
    FATAL = "fatal"              # Unrecoverable, manual intervention needed
    UNKNOWN = "unknown"          # Needs classification


@dataclass
class ErrorClassification:
    """Result of error classification."""
    error_type: ErrorType
    confidence: float  # 0.0-1.0
    retry_recommended: bool
    retry_delay_seconds: float
    max_retries: int
    reason: str


# Regex patterns for error classification
ERROR_PATTERNS: dict[ErrorType, list[Pattern]] = {
    ErrorType.TRANSIENT: [
        re.compile(r"connection\s+(?:reset|refused|closed)", re.I),
        re.compile(r"temporary\s+(?:failure|error)", re.I),
        re.compile(r"dns\s+(?:error|failure|timeout)", re.I),
        re.compile(r"network\s+unreachable", re.I),
        re.compile(r"EOF\s+occurred", re.I),
        re.compile(r"broken\s+pipe", re.I),
        re.compile(r"ssl\s+(?:error|handshake)", re.I),
        re.compile(r"remote\s+end\s+closed", re.I),
    ],
    ErrorType.TIMEOUT: [
        re.compile(r"timeout", re.I),
        re.compile(r"timed\s+out", re.I),
        re.compile(r"deadline\s+exceeded", re.I),
        re.compile(r"request\s+timeout", re.I),
        re.compile(r"socket\s+timeout", re.I),
        re.compile(r"read\s+timeout", re.I),
        re.compile(r"connect\s+timeout", re.I),
    ],
    ErrorType.RATE_LIMIT: [
        re.compile(r"rate\s*limit", re.I),
        re.compile(r"too\s+many\s+requests", re.I),
        re.compile(r"429", re.I),
        re.compile(r"quota\s+exceeded", re.I),
        re.compile(r"throttl", re.I),  # throttle, throttled, throttling
        re.compile(r"capacity\s+exceeded", re.I),
    ],
    ErrorType.AUTH: [
        re.compile(r"unauthorized", re.I),
        re.compile(r"authentication", re.I),
        re.compile(r"forbidden", re.I),
        re.compile(r"403", re.I),
        re.compile(r"401", re.I),
        re.compile(r"invalid\s+(?:token|key|credential)", re.I),
        re.compile(r"expired\s+(?:token|session)", re.I),
        re.compile(r"permission\s+denied", re.I),
    ],
    ErrorType.FATAL: [
        re.compile(r"fatal", re.I),
        re.compile(r"panic", re.I),
        re.compile(r"segfault", re.I),
        re.compile(r"out\s+of\s+(?:memory|disk)", re.I),
        re.compile(r"disk\s+full", re.I),
        re.compile(r"corrupt", re.I),
    ],
    ErrorType.PERSISTENT: [
        re.compile(r"not\s+(?:found|exist)", re.I),
        re.compile(r"404", re.I),
        re.compile(r"invalid\s+(?:parameter|argument|input)", re.I),
        re.compile(r"bad\s+request", re.I),
        re.compile(r"400", re.I),
        re.compile(r"constraint\s+violation", re.I),
        re.compile(r"unique\s+constraint", re.I),
        re.compile(r"foreign\s+key", re.I),
    ],
}

# Recovery strategies per error type
RECOVERY_STRATEGIES: dict[ErrorType, dict] = {
    ErrorType.TRANSIENT: {
        "retry_recommended": True,
        "retry_delay_seconds": 1.0,
        "max_retries": 3,
    },
    ErrorType.TIMEOUT: {
        "retry_recommended": True,
        "retry_delay_seconds": 2.0,
        "max_retries": 2,
    },
    ErrorType.RATE_LIMIT: {
        "retry_recommended": True,
        "retry_delay_seconds": 5.0,
        "max_retries": 5,
    },
    ErrorType.AUTH: {
        "retry_recommended": False,
        "retry_delay_seconds": 0.0,
        "max_retries": 0,
    },
    ErrorType.FATAL: {
        "retry_recommended": False,
        "retry_delay_seconds": 0.0,
        "max_retries": 0,
    },
    ErrorType.PERSISTENT: {
        "retry_recommended": False,
        "retry_delay_seconds": 0.0,
        "max_retries": 0,
    },
    ErrorType.UNKNOWN: {
        "retry_recommended": True,
        "retry_delay_seconds": 1.0,
        "max_retries": 1,
    },
}


class ErrorClassifier:
    """
    Classifies errors to determine recovery strategy.
    
    Uses pattern matching first, with optional LLM fallback for
    errors that don't match known patterns.
    """
    
    def __init__(self, use_llm_fallback: bool = False):
        self.use_llm_fallback = use_llm_fallback
        self._classification_history: list[ErrorClassification] = []
    
    def classify(
        self, 
        error_message: str, 
        error_code: Optional[str] = None,
        context: Optional[dict] = None
    ) -> ErrorClassification:
        """
        Classify an error based on message and optional code.
        
        Args:
            error_message: The error message or exception string
            error_code: Optional HTTP status code or error code
            context: Optional context dict with skill_name, operation, etc.
            
        Returns:
            ErrorClassification with recovery strategy
        """
        search_text = error_message
        if error_code:
            search_text = f"{error_code} {search_text}"
        
        # Try pattern matching first
        for error_type, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(search_text):
                    strategy = RECOVERY_STRATEGIES[error_type]
                    classification = ErrorClassification(
                        error_type=error_type,
                        confidence=0.85,
                        retry_recommended=strategy["retry_recommended"],
                        retry_delay_seconds=strategy["retry_delay_seconds"],
                        max_retries=strategy["max_retries"],
                        reason=f"Matched pattern: {pattern.pattern[:50]}..."
                    )
                    self._classification_history.append(classification)
                    return classification
        
        # No pattern matched
        if self.use_llm_fallback:
            # LLM classification would go here
            # For now, return unknown
            pass
        
        strategy = RECOVERY_STRATEGIES[ErrorType.UNKNOWN]
        classification = ErrorClassification(
            error_type=ErrorType.UNKNOWN,
            confidence=0.5,
            retry_recommended=strategy["retry_recommended"],
            retry_delay_seconds=strategy["retry_delay_seconds"],
            max_retries=strategy["max_retries"],
            reason="No matching pattern found"
        )
        self._classification_history.append(classification)
        return classification
    
    def classify_exception(self, exception: Exception) -> ErrorClassification:
        """Classify from an Exception object."""
        error_message = str(exception)
        error_type = type(exception).__name__
        return self.classify(f"{error_type}: {error_message}")
    
    def should_retry(self, error_message: str) -> tuple[bool, float]:
        """
        Quick check if error should be retried.
        
        Returns:
            Tuple of (should_retry, delay_seconds)
        """
        classification = self.classify(error_message)
        return classification.retry_recommended, classification.retry_delay_seconds
    
    def get_stats(self) -> dict:
        """Return classification statistics."""
        if not self._classification_history:
            return {"total": 0}
        
        from collections import Counter
        type_counts = Counter(c.error_type.value for c in self._classification_history)
        
        return {
            "total": len(self._classification_history),
            "by_type": dict(type_counts),
            "avg_confidence": sum(c.confidence for c in self._classification_history) / len(self._classification_history),
        }
    
    def clear_history(self) -> None:
        """Clear classification history."""
        self._classification_history.clear()


# Convenience function for quick classification
def classify_error(
    error_message: str,
    error_code: Optional[str] = None
) -> ErrorClassification:
    """Classify an error message (convenience function)."""
    classifier = ErrorClassifier()
    return classifier.classify(error_message, error_code)
