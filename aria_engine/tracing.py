"""
OpenTelemetry tracing foundation for Aria Engine (S-25).

Opt-in: tracing is only activated when OTEL_EXPORTER_OTLP_ENDPOINT is set.
Without it, all calls are safe no-ops.

Usage (in entrypoint.py):
    from aria_engine.tracing import configure_tracing
    configure_tracing()  # call once at startup, before DB / HTTP activity
"""
import logging
import os

logger = logging.getLogger("aria.engine.tracing")

_CONFIGURED = False


def configure_tracing() -> bool:
    """
    Initialize the OpenTelemetry SDK with OTLP exporter.

    Returns True if tracing was configured, False if skipped (no env var
    or missing dependencies).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return True

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError:
        logger.warning(
            "opentelemetry packages not installed — tracing disabled. "
            "Install with: pip install 'aria-blue[tracing]'"
        )
        return False

    try:
        resource = Resource.create(
            {
                "service.name": os.environ.get("OTEL_SERVICE_NAME", "aria-engine"),
                "service.version": os.environ.get("ARIA_VERSION", "3.0.0"),
                "deployment.environment": os.environ.get("ARIA_ENV", "production"),
            }
        )

        provider = TracerProvider(resource=resource)

        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        trace.set_tracer_provider(provider)

        _CONFIGURED = True
        logger.info("OpenTelemetry tracing configured → %s", endpoint)
        return True
    except Exception as e:
        logger.warning("Failed to configure OpenTelemetry: %s", e)
        return False


def instrument_libraries() -> None:
    """
    Activate auto-instrumentation for asyncpg (DB) and httpx (HTTP client).

    Safe to call even when the instrumentation packages are not installed —
    each instrumentor is wrapped in its own try/except.
    """
    if not _CONFIGURED:
        return

    # asyncpg — traces every SQL query
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
        logger.info("Instrumented asyncpg (database traces)")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-asyncpg not installed — skipped")
    except Exception as e:
        logger.warning("asyncpg instrumentation failed: %s", e)

    # httpx — traces outbound HTTP calls (LiteLLM, API, etc.)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.info("Instrumented httpx (HTTP client traces)")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed — skipped")
    except Exception as e:
        logger.warning("httpx instrumentation failed: %s", e)


def get_tracer(name: str = "aria.engine"):
    """
    Return an OpenTelemetry tracer for manual span creation.

    If tracing is not configured, returns a no-op tracer so callers don't
    need guard clauses.

    Usage::

        from aria_engine.tracing import get_tracer
        tracer = get_tracer("aria.engine.chat")

        async def handle_message(msg):
            with tracer.start_as_current_span("handle_message") as span:
                span.set_attribute("message.role", msg.role)
                ...
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        # Return a no-op tracer stub
        return _NoOpTracer()


class _NoOpTracer:
    """Minimal stub so callers can use `tracer.start_as_current_span()` safely."""

    def start_as_current_span(self, name, **kwargs):
        return _NoOpSpan()


class _NoOpSpan:
    """Context-manager stub for when OTel is not installed."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def set_attribute(self, key, value):
        pass

    def set_status(self, *args, **kwargs):
        pass

    def record_exception(self, exc):
        pass
