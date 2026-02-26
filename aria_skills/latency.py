# aria_skills/latency.py
"""
Skill latency logging decorator (S-165).

.. deprecated:: 3.0
    Prefer ``BaseSkill.execute_with_metrics()`` which consolidates latency
    tracking into Prometheus + DB telemetry + in-memory health dashboard.
    ``@log_latency`` will be removed in a future release.

Measures execution time of async skill methods and logs to the database
via aria-api. Falls back to logger.debug when no API client is available.
Never breaks the decorated method if logging fails.
"""
import functools
import logging
import time
import warnings

logger = logging.getLogger(__name__)


def log_latency(method):
    """Decorator to log skill method execution latency.

    .. deprecated:: 3.0
        Use ``execute_with_metrics()`` instead.  This decorator is kept for
        backward-compatibility but will be removed in a future release.

    Usage::

        from aria_skills.latency import log_latency

        class MySkill(BaseSkill):
            @log_latency
            async def execute(self, ...):
                ...

    Behaviour:
    - Measures wall-clock time (``time.monotonic``) around the awaited method.
    - If ``self._api`` exists and is truthy, POSTs a latency record to
      ``/skill-latency`` via that client.  Otherwise logs via ``logger.debug``.
    - Exceptions from the wrapped method propagate normally.
    - Logging failures are silently swallowed so they never break the skill.
    """

    warnings.warn(
        "log_latency is deprecated — use BaseSkill.execute_with_metrics() instead (S-25)",
        DeprecationWarning,
        stacklevel=2,
    )

    @functools.wraps(method)
    async def wrapper(self, *args, **kwargs):
        start = time.monotonic()
        error = None
        try:
            result = await method(self, *args, **kwargs)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            try:
                skill_name = getattr(self, "name", self.__class__.__name__)
                method_name = method.__name__
                if hasattr(self, "_api") and self._api:
                    await self._api.post("/skill-latency", json={
                        "skill": skill_name,
                        "method": method_name,
                        "latency_ms": round(elapsed_ms, 2),
                        "error": error,
                    })
                else:
                    logger.debug(
                        "%s.%s: %.1fms%s",
                        skill_name,
                        method_name,
                        elapsed_ms,
                        f" error={error}" if error else "",
                    )
            except Exception:
                pass  # Never break the skill for logging

    return wrapper
