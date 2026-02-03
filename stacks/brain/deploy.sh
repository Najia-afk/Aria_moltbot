#!/bin/bash
# Aria Brain Stack - Deploy Script
# Usage: ./deploy.sh [deploy|rebuild|stop|logs|status|clean]
set -e

cd "$(dirname "$0")"

log() { echo -e "\033[0;32m[DEPLOY]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
error() { echo -e "\033[0;31m[ERROR]\033[0m $1"; exit 1; }

check_env() {
    [ ! -f ".env" ] && error ".env not found. Copy from .env.example"
    source .env
    [ -z "$SERVICE_HOST" ] && error "SERVICE_HOST not set in .env"
}

init_dirs() {
    mkdir -p certs grafana/provisioning/datasources init-scripts
    
    cat > init-scripts/01-init-databases.sh << 'EOF'
#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    SELECT 'CREATE DATABASE litellm' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'litellm')\gexec
    GRANT ALL PRIVILEGES ON DATABASE litellm TO $POSTGRES_USER;
EOSQL
EOF
    chmod +x init-scripts/01-init-databases.sh
    
    cat > grafana/provisioning/datasources/datasources.yml << 'EOF'
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF
}

deploy() {
    check_env
    init_dirs
    log "Building and starting..."
    docker compose build
    docker compose up -d
    sleep 10
    docker compose ps
    source .env
    log "✅ Done! https://${SERVICE_HOST}/"
}

case "${1:-deploy}" in
    deploy) deploy ;;
    rebuild)
        warn "Full rebuild - all data lost!"
        read -p "Type 'yes': " c; [ "$c" != "yes" ] && exit 0
        docker compose down -v --remove-orphans
        rm -rf certs/*.pem init-scripts/*
        deploy ;;
    stop) docker compose down ;;
    logs) docker compose logs -f ${2:-} ;;
    status) docker compose ps ;;
    clean)
        warn "DESTROY all data!"
        read -p "Type 'yes': " c; [ "$c" != "yes" ] && exit 0
        docker compose down -v --remove-orphans
        rm -rf certs/*.pem init-scripts/* ;;
    *) echo "Usage: $0 {deploy|rebuild|stop|logs|status|clean}" ;;
esac
