"""Structured logging configuration for Aria."""
import logging
import contextvars
import uuid

try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

def new_correlation_id() -> str:
    """Generate a new correlation ID."""
    return str(uuid.uuid4())[:8]

def add_correlation_id(logger, method_name, event_dict):
    """Structlog processor to add correlation ID."""
    cid = correlation_id_var.get("")
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict

def configure_logging(level: int = logging.INFO):
    """Configure structured logging with structlog."""
    # Always configure stdlib root logger so standard logging.getLogger()
    # calls (used by scheduler, chat_engine, etc.) output to stderr.
    # Use force=True to ensure handler is added even if basicConfig was
    # called elsewhere (e.g. by an import side-effect).
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )

    if not HAS_STRUCTLOG:
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_correlation_id,
            structlog.dev.ConsoleRenderer() if logging.root.level <= logging.DEBUG else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )
