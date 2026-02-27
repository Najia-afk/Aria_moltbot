# aria_skills/health/retry_engine.py
"""
Retry engine with exponential backoff and jitter.

Part of Aria's self-healing system (TICKET-36).
"""
import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, TypeVar, Any
from functools import wraps

from error_classifier import ErrorClassifier, ErrorType, ErrorClassification


T = TypeVar('T')


class RetryState(Enum):
    """States for retry tracking."""
    IDLE = "idle"
    RETRYING = "retrying"
    EXHAUSTED = "exhausted"
    SUCCESS = "success"


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: Optional[Any]
    attempts: int
    total_delay: float
    final_error: Optional[str]
    classification: Optional[ErrorClassification]


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_max: float = 1.0
    timeout: Optional[float] = None


class RetryEngine:
    """
    Retry engine with exponential backoff and intelligent error classification.
    
    Features:
    - Exponential backoff with configurable base
    - Random jitter to prevent thundering herd
    - Integration with ErrorClassifier for smart retry decisions
    - Circuit breaker awareness
    - Per-skill and per-operation configuration
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.classifier = ErrorClassifier()
        self._retry_stats: dict[str, dict] = {}
    
    def calculate_delay(self, attempt: int, classification: Optional[ErrorClassification] = None) -> float:
        """
        Calculate delay for a retry attempt.
        
        Uses exponential backoff: base_delay * (exponential_base ^ attempt)
        Adds jitter if enabled.
        """
        # Base exponential delay
        delay = self.config.base_delay * (self.config.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.config.max_delay)
        
        # Use classification's recommended delay if available
        if classification and classification.retry_delay_seconds > 0:
            delay = max(delay, classification.retry_delay_seconds)
        
        # Add jitter
        if self.config.jitter:
            jitter = random.uniform(0, self.config.jitter_max)
            delay += jitter
        
        return delay
    
    async def execute(
        self,
        operation: Callable[..., Any],
        operation_name: str = "operation",
        *args,
        **kwargs
    ) -> RetryResult:
        """
        Execute an operation with retry logic.
        
        Args:
            operation: Async callable to execute
            operation_name: Name for tracking/stats
            *args, **kwargs: Arguments to pass to operation
            
        Returns:
            RetryResult with success status and metadata
        """
        attempts = 0
        total_delay = 0.0
        last_error: Optional[str] = None
        last_classification: Optional[ErrorClassification] = None
        
        max_attempts = self.config.max_retries + 1  # +1 for initial attempt
        
        while attempts < max_attempts:
            attempts += 1
            
            try:
                # Apply timeout if configured
                if self.config.timeout:
                    result = await asyncio.wait_for(
                        operation(*args, **kwargs),
                        timeout=self.config.timeout
                    )
                else:
                    result = await operation(*args, **kwargs)
                
                # Success!
                self._record_success(operation_name, attempts)
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_delay=total_delay,
                    final_error=None,
                    classification=last_classification
                )
                
            except asyncio.TimeoutError as e:
                last_error = f"TimeoutError: {str(e)}"
                last_classification = self.classifier.classify(last_error)
                
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                last_classification = self.classifier.classify_exception(e)
            
            # Check if we should retry
            if attempts >= max_attempts:
                break  # Exhausted retries
                
            if not last_classification.retry_recommended:
                break  # Error type says don't retry
            
            # Calculate and apply delay
            delay = self.calculate_delay(attempts - 1, last_classification)
            total_delay += delay
            
            await asyncio.sleep(delay)
        
        # All retries exhausted
        self._record_failure(operation_name, attempts, last_error)
        return RetryResult(
            success=False,
            result=None,
            attempts=attempts,
            total_delay=total_delay,
            final_error=last_error,
            classification=last_classification
        )
    
    def _record_success(self, operation_name: str, attempts: int):
        """Record successful operation."""
        if operation_name not in self._retry_stats:
            self._retry_stats[operation_name] = {"success": 0, "failure": 0, "retries": 0}
        self._retry_stats[operation_name]["success"] += 1
        self._retry_stats[operation_name]["retries"] += attempts - 1
    
    def _record_failure(self, operation_name: str, attempts: int, error: str):
        """Record failed operation."""
        if operation_name not in self._retry_stats:
            self._retry_stats[operation_name] = {"success": 0, "failure": 0, "retries": 0}
        self._retry_stats[operation_name]["failure"] += 1
        self._retry_stats[operation_name]["retries"] += attempts
    
    def get_stats(self) -> dict:
        """Get retry statistics."""
        return {
            "operations": dict(self._retry_stats),
            "classifier": self.classifier.get_stats()
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self._retry_stats.clear()


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True
):
    """
    Decorator to add retry logic to async functions.
    
    Usage:
        @with_retry(max_retries=3)
        async def fetch_data():
            return await api.get_data()
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        jitter=jitter
    )
    
    def decorator(func: Callable[..., Any]):
        engine = RetryEngine(config)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await engine.execute(
                lambda: func(*args, **kwargs),
                operation_name=func.__name__
            )
            if result.success:
                return result.result
            else:
                raise Exception(f"Retry exhausted: {result.final_error}")
        
        wrapper._retry_engine = engine
        wrapper.get_retry_stats = engine.get_stats
        return wrapper
    
    return decorator


# Singleton for global retry operations
_default_engine: Optional[RetryEngine] = None


def get_retry_engine() -> RetryEngine:
    """Get or create default retry engine."""
    global _default_engine
    if _default_engine is None:
        _default_engine = RetryEngine()
    return _default_engine


async def retry_operation(
    operation: Callable[..., Any],
    *args,
    max_retries: int = 3,
    **kwargs
) -> Any:
    """
    Convenience function for one-off retry operations.
    
    Usage:
        result = await retry_operation(fetch_data, max_retries=3)
    """
    config = RetryConfig(max_retries=max_retries)
    engine = RetryEngine(config)
    result = await engine.execute(operation, *args, **kwargs)
    
    if result.success:
        return result.result
    else:
        raise Exception(f"Operation failed after {result.attempts} attempts: {result.final_error}")
