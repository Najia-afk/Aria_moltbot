"""
Generic Circuit Breaker — shared by LLMGateway and AriaSkill (S-22).

States:
    CLOSED  → requests flow normally; failures are counted
    OPEN    → requests are immediately rejected
    HALF-OPEN → after reset timeout, one probe request is allowed

Usage:
    cb = CircuitBreaker(name="llm", threshold=5, reset_after=30.0)

    if cb.is_open():
        raise SomeError("circuit open")

    try:
        result = await do_something()
        cb.record_success()
    except Exception:
        cb.record_failure()
        raise
"""
import logging
import time

logger = logging.getLogger("aria.engine.circuit_breaker")


class CircuitBreaker:
    """Thread-safe* circuit breaker with three states.

    * For asyncio single-threaded event loops; no locking needed.
    """

    __slots__ = (
        "name",
        "threshold",
        "reset_after",
        "_failures",
        "_opened_at",
        "_logger",
    )

    def __init__(
        self,
        name: str = "default",
        threshold: int = 5,
        reset_after: float = 30.0,
    ):
        self.name = name
        self.threshold = threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at: float | None = None
        self._logger = logger

    # ── State queries ────────────────────────────────────────────

    def is_open(self) -> bool:
        """Return True if the breaker is OPEN (reject requests)."""
        if self._failures < self.threshold:
            return False
        if self._opened_at is None:
            return False
        elapsed = time.monotonic() - self._opened_at
        if elapsed > self.reset_after:
            # Transition to HALF-OPEN — allow a probe request
            self._failures = 0
            self._opened_at = None
            self._logger.info(
                "Circuit breaker %s half-open after %.0fs — allowing probe",
                self.name,
                elapsed,
            )
            return False
        return True

    @property
    def state(self) -> str:
        """Return human-readable state: 'closed', 'open', or 'half-open'."""
        if self._failures < self.threshold:
            return "closed"
        if self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed > self.reset_after:
                return "half-open"
        return "open"

    @property
    def failure_count(self) -> int:
        return self._failures

    # ── Outcome recording ────────────────────────────────────────

    def record_success(self) -> None:
        """Reset failure counter after a successful request."""
        self._failures = 0

    def record_failure(self) -> None:
        """Increment failure counter; open breaker when threshold reached."""
        self._failures += 1
        if self._failures >= self.threshold:
            self._opened_at = time.monotonic()
            self._logger.warning(
                "Circuit breaker %s OPEN after %d consecutive failures",
                self.name,
                self._failures,
            )

    # ── Reset ────────────────────────────────────────────────────

    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED state."""
        self._failures = 0
        self._opened_at = None

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self.name!r}, state={self.state!r}, "
            f"failures={self._failures}/{self.threshold})"
        )
