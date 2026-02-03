#!/bin/bash
# =============================================================================
# Aria Brain Stack - One-Click Deploy Script
# =============================================================================
# Usage: ./deploy.sh [command]
#
# Commands:
#   deploy    - Build and deploy the full stack (default)
#   rebuild   - Destroy everything and redeploy from scratch
#   stop      - Stop all services
#   logs      - Show logs for all services
#   status    - Show service status
#   clean     - Remove all containers, volumes, and data (DESTRUCTIVE!)
#
# Requirements:
#   - Docker and Docker Compose installed
#   - .env file configured (copy from .env.template)
#   - Git repository cloned
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Logging functions
log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        error "Docker Compose is not installed. Please install Docker Compose first."
    fi
    
    # Check .env file
    if [ ! -f ".env" ]; then
        if [ -f ".env.template" ]; then
            warn ".env file not found. Creating from template..."
            cp .env.template .env
            warn "Please edit .env file with your configuration, especially SERVICE_HOST"
            warn "Then run this script again."
            exit 1
        else
            error ".env file not found. Please create one from .env.template"
        fi
    fi
    
    # Validate required variables
    source .env
    if [ -z "$SERVICE_HOST" ] || [ "$SERVICE_HOST" = "your_server_ip_or_domain" ]; then
        error "SERVICE_HOST is not configured in .env file. Please set it to your server's IP or domain."
    fi
    
    log "Prerequisites check passed ✅"
}

# Create required directories
create_directories() {
    log "Creating required directories..."
    mkdir -p certs
    mkdir -p grafana/provisioning/datasources
    mkdir -p grafana/provisioning/dashboards
    mkdir -p init-scripts
    log "Directories created ✅"
}

# Initialize database scripts
init_database_scripts() {
    log "Creating database initialization scripts..."
    
    # Multi-database init script
    cat > init-scripts/01-init-databases.sh << 'INITEOF'
#!/bin/bash
set -e

# Create litellm database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE litellm' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
    GRANT ALL PRIVILEGES ON DATABASE litellm TO $POSTGRES_USER;
EOSQL
INITEOF
    chmod +x init-scripts/01-init-databases.sh
    
    log "Database scripts created ✅"
}

# Initialize Grafana provisioning
init_grafana() {
    log "Initializing Grafana provisioning..."
    
    # Datasource config
    cat > grafana/provisioning/datasources/datasources.yml << 'GRAFANAEOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
GRAFANAEOF
    
    log "Grafana provisioning created ✅"
}

# Build and deploy
deploy() {
    check_prerequisites
    create_directories
    init_database_scripts
    init_grafana
    
    log "Building and deploying Aria stack..."
    
    # Use portable compose file if available
    COMPOSE_FILE="docker-compose.yml"
    if [ -f "docker-compose.portable.yml" ]; then
        COMPOSE_FILE="docker-compose.portable.yml"
        info "Using portable compose configuration"
    fi
    
    # Build images
    log "Building Docker images..."
    docker compose -f "$COMPOSE_FILE" build
    
    # Start services
    log "Starting services..."
    docker compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services
    log "Waiting for services to start..."
    sleep 15
    
    # Show status
    docker compose -f "$COMPOSE_FILE" ps
    
    # Get SERVICE_HOST from .env
    source .env
    
    echo ""
    log "🎉 Aria stack deployed successfully!"
    echo ""
    echo "📊 Access Points:"
    echo "   Dashboard:  https://${SERVICE_HOST}/"
    echo "   Clawdbot:   https://${SERVICE_HOST}/clawdbot/"
    echo "   API Docs:   https://${SERVICE_HOST}/api/docs"
    echo "   Grafana:    https://${SERVICE_HOST}/grafana/"
    echo "   Traefik:    https://${SERVICE_HOST}/traefik/"
    echo ""
    warn "Note: Accept the self-signed certificate warning in your browser"
}

# Stop services
stop() {
    log "Stopping Aria stack..."
    
    COMPOSE_FILE="docker-compose.yml"
    [ -f "docker-compose.portable.yml" ] && COMPOSE_FILE="docker-compose.portable.yml"
    
    docker compose -f "$COMPOSE_FILE" down
    log "Services stopped ✅"
}

# Show logs
logs() {
    COMPOSE_FILE="docker-compose.yml"
    [ -f "docker-compose.portable.yml" ] && COMPOSE_FILE="docker-compose.portable.yml"
    
    if [ -n "$2" ]; then
        docker compose -f "$COMPOSE_FILE" logs -f "$2"
    else
        docker compose -f "$COMPOSE_FILE" logs -f --tail=100
    fi
}

# Show status
status() {
    COMPOSE_FILE="docker-compose.yml"
    [ -f "docker-compose.portable.yml" ] && COMPOSE_FILE="docker-compose.portable.yml"
    
    docker compose -f "$COMPOSE_FILE" ps
}

# Clean everything (DESTRUCTIVE!)
clean() {
    warn "⚠️  This will DESTROY all containers, volumes, and data!"
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Aborted."
        exit 0
    fi
    
    log "Stopping and removing all containers..."
    
    COMPOSE_FILE="docker-compose.yml"
    [ -f "docker-compose.portable.yml" ] && COMPOSE_FILE="docker-compose.portable.yml"
    
    docker compose -f "$COMPOSE_FILE" down -v --remove-orphans
    
    log "Removing generated files..."
    rm -rf certs/*.pem
    rm -rf init-scripts/*
    
    log "Clean complete ✅"
}

# Rebuild from scratch
rebuild() {
    warn "This will destroy all data and rebuild from scratch!"
    read -p "Are you sure? (type 'yes' to confirm): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Aborted."
        exit 0
    fi
    
    clean
    deploy
}

# Main
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    rebuild)
        rebuild
        ;;
    stop)
        stop
        ;;
    logs)
        logs "$@"
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    *)
        echo "Usage: $0 {deploy|rebuild|stop|logs|status|clean}"
        echo ""
        echo "Commands:"
        echo "  deploy    - Build and deploy the full stack (default)"
        echo "  rebuild   - Destroy everything and redeploy from scratch"
        echo "  stop      - Stop all services"
        echo "  logs      - Show logs for all services (or specify service name)"
        echo "  status    - Show service status"
        echo "  clean     - Remove all containers, volumes, and data"
        exit 1
        ;;
esac
