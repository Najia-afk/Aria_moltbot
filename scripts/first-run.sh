#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Aria Brain Stack — First-Run Setup Script (macOS / Linux)
# Creates .env from .env.example with required secrets generated.
# ──────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STACK_DIR="$REPO_ROOT/stacks/brain"
ENV_EXAMPLE="$STACK_DIR/.env.example"
ENV_FILE="$STACK_DIR/.env"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

banner() {
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║       🦀 Aria Brain — First Run 🦀       ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${NC}"
}

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()     { echo -e "${RED}[ERROR]${NC} $*"; }

generate_secret() {
    python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null \
        || openssl rand -base64 32 | tr -d '/+=' | head -c 43
}

# ── Pre-flight checks ────────────────────────────────────────

banner

# Check Docker
if ! command -v docker &>/dev/null; then
    err "Docker is not installed. Please install Docker first."
    err "  macOS: https://docs.docker.com/desktop/install/mac-install/"
    err "  Linux: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker info &>/dev/null; then
    err "Docker daemon is not running. Please start Docker Desktop or the Docker service."
    exit 1
fi

info "Docker detected: $(docker --version)"

# Check docker compose
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    err "Docker Compose not found. Please install Docker Compose."
    exit 1
fi

info "Compose detected: $($COMPOSE_CMD version 2>/dev/null || echo 'available')"

# Check for Ollama (optional)
if command -v ollama &>/dev/null; then
    info "Ollama detected: $(ollama --version 2>/dev/null || echo 'available')"
else
    warn "Ollama not found — local models won't be available."
    warn "  Install: https://ollama.com/download"
fi

# ── .env Setup ────────────────────────────────────────────────

if [ ! -f "$ENV_EXAMPLE" ]; then
    err "Cannot find $ENV_EXAMPLE"
    exit 1
fi

if [ -f "$ENV_FILE" ]; then
    warn ".env already exists at $ENV_FILE"
    read -rp "Overwrite? (y/N) " choice
    if [[ ! "$choice" =~ ^[Yy]$ ]]; then
        info "Keeping existing .env. Exiting."
        exit 0
    fi
    cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"
    info "Backed up existing .env"
fi

cp "$ENV_EXAMPLE" "$ENV_FILE"
info "Created .env from .env.example"

# ── Generate required secrets ─────────────────────────────────

info "Generating secrets..."

DB_PASS=$(generate_secret)
WEB_KEY=$(generate_secret)
LITELLM_KEY="sk-aria-$(generate_secret)"
GRAFANA_PASS=$(generate_secret)
PGADMIN_PASS=$(generate_secret)
API_KEY=$(generate_secret)
ADMIN_KEY=$(generate_secret)

# Use sed to fill in required values
if [[ "$OSTYPE" == "darwin"* ]]; then
    SED_I="sed -i ''"
else
    SED_I="sed -i"
fi

fill_env() {
    local key="$1" val="$2"
    # Replace "KEY=" (empty) with "KEY=value"
    eval "$SED_I 's|^${key}=$|${key}=${val}|' \"$ENV_FILE\""
}

fill_env "DB_PASSWORD" "$DB_PASS"
fill_env "WEB_SECRET_KEY" "$WEB_KEY"
fill_env "LITELLM_MASTER_KEY" "$LITELLM_KEY"
fill_env "GRAFANA_PASSWORD" "$GRAFANA_PASS"
fill_env "PGADMIN_PASSWORD" "$PGADMIN_PASS"
fill_env "ARIA_API_KEY" "$API_KEY"
fill_env "ARIA_ADMIN_KEY" "$ADMIN_KEY"

info "Required secrets generated and written to .env"

# ── Optional: prompt for API keys ─────────────────────────────

echo ""
echo -e "${CYAN}Optional API Keys${NC} (press Enter to skip)"
echo "These can be added to .env later."
echo ""

read -rp "OpenRouter API Key (sk-or-v1-...): " OR_KEY
if [ -n "$OR_KEY" ]; then
    fill_env "OPEN_ROUTER_KEY" "$OR_KEY"
    info "OpenRouter key saved"
fi

read -rp "Moonshot/Kimi API Key: " KIMI_KEY
if [ -n "$KIMI_KEY" ]; then
    fill_env "MOONSHOT_KIMI_KEY" "$KIMI_KEY"
    info "Moonshot key saved"
fi

# ── Summary ───────────────────────────────────────────────────

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Setup complete!                                 ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "  .env location:  $ENV_FILE"
echo ""
echo "  Generated credentials:"
echo "    DB_PASSWORD       = ${DB_PASS:0:8}..."
echo "    WEB_SECRET_KEY    = ${WEB_KEY:0:8}..."
echo "    LITELLM_MASTER_KEY= ${LITELLM_KEY:0:15}..."
echo "    ARIA_API_KEY      = ${API_KEY:0:8}..."
echo "    ARIA_ADMIN_KEY    = ${ADMIN_KEY:0:8}..."
echo "    GRAFANA_PASSWORD  = ${GRAFANA_PASS:0:8}..."
echo "    PGADMIN_PASSWORD  = ${PGADMIN_PASS:0:8}..."
echo ""
echo "  Next steps:"
echo "    1. Review/edit:  nano $ENV_FILE"
echo "    2. Start stack:  cd $STACK_DIR && $COMPOSE_CMD up -d"
echo "    3. Open web UI:  http://localhost:5000"
echo "    4. Open API docs: http://localhost:8000/docs"
echo ""
