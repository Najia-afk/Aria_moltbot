"""
Aria Brain API — Configuration
All environment variables and service configuration in one place.
"""

import os
from datetime import datetime, timezone

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

# ── Networking ────────────────────────────────────────────────────────────────
DOCKER_HOST_IP = os.getenv("DOCKER_HOST_IP", "host.docker.internal")
MLX_ENABLED = os.getenv("MLX_ENABLED", "false").lower() == "true"

# ── Service discovery (name → (base_url, health_path)) ───────────────────────
SERVICE_URLS: dict[str, tuple[str, str]] = {
    "grafana":    (os.getenv("GRAFANA_URL",    "http://grafana:3000"),           "/api/health"),
    "prometheus": (os.getenv("PROMETHEUS_URL",  "http://prometheus:9090"),        "/prometheus/-/healthy"),
    "ollama":     (os.getenv("OLLAMA_URL",      f"http://{DOCKER_HOST_IP}:11434"), "/api/tags"),
    "litellm":    (os.getenv("LITELLM_URL",     "http://litellm:4000"),          "/health/liveliness"),
    "clawdbot":   (os.getenv("CLAWDBOT_URL",    "http://clawdbot:18789"),        "/"),
    "pgadmin":    (os.getenv("PGADMIN_URL",     "http://aria-pgadmin:80"),       "/"),
    "browser":    (os.getenv("BROWSER_URL", "http://aria-browser:3000"),         "/"),
    "traefik":    (os.getenv("TRAEFIK_URL",     "http://traefik:8080"),          "/api/overview"),
    "aria-web":   (os.getenv("ARIA_WEB_URL",    "http://aria-web:5000"),         "/"),
    "aria-api":   (os.getenv("ARIA_API_SELF_URL", "http://localhost:8000"),      "/health"),
}

if MLX_ENABLED:
    SERVICE_URLS["mlx"] = (
        os.getenv("MLX_URL", f"http://{DOCKER_HOST_IP}:8080"),
        "/v1/models",
    )

# ── Admin / Service control ──────────────────────────────────────────────────
ARIA_ADMIN_TOKEN = os.getenv("ARIA_ADMIN_TOKEN")
if not ARIA_ADMIN_TOKEN:
    import logging as _logging
    _logging.getLogger("aria.api").warning("ARIA_ADMIN_TOKEN not set — admin endpoints will reject all requests")
SERVICE_CONTROL_ENABLED = os.getenv(
    "ARIA_SERVICE_CONTROL_ENABLED", "false"
).lower() in {"1", "true", "yes"}

# ── LiteLLM / Providers ─────────────────────────────────────────────────────
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
MOONSHOT_KIMI_KEY  = os.getenv("MOONSHOT_KIMI_KEY", "")
OPEN_ROUTER_KEY    = os.getenv("OPEN_ROUTER_KEY", "")

# ── OpenClaw ─────────────────────────────────────────────────────────────────
OPENCLAW_JOBS_PATH = os.getenv("OPENCLAW_JOBS_PATH", "/openclaw/cron/jobs.json")
OPENCLAW_SESSIONS_INDEX_PATH = os.getenv(
    "OPENCLAW_SESSIONS_INDEX_PATH", "/openclaw/agents/main/sessions/sessions.json"
)
OPENCLAW_AGENTS_ROOT = os.getenv("OPENCLAW_AGENTS_ROOT", "/openclaw/agents")
OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS = int(
    os.getenv("OPENCLAW_SESSIONS_SYNC_INTERVAL_SECONDS", "30")
)

# ── Startup jobs ─────────────────────────────────────────────────────────────
SKILL_BACKFILL_ON_STARTUP = os.getenv(
    "SKILL_BACKFILL_ON_STARTUP", "true"
).lower() in {"1", "true", "yes"}

# ── Runtime ──────────────────────────────────────────────────────────────────
STARTUP_TIME = datetime.now(timezone.utc)
API_VERSION  = "3.0.0"
