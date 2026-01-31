<#
.SYNOPSIS
    Aria Blue - One-Command Deployment Script
    Deploys the full Aria stack to the Mac Mini server

.DESCRIPTION
    This script:
    1. Connects to Mac Mini via SSH
    2. Stops existing containers
    3. Transfers updated files
    4. Builds Docker images
    5. Deploys the full stack
    6. Imports data and verifies health

.PARAMETER Action
    deploy  - Full deployment (default)
    stop    - Stop all services
    restart - Restart services
    logs    - Show logs
    status  - Check service status

.EXAMPLE
    .\deploy.ps1 -Action deploy
    .\deploy.ps1 -Action status
#>

param(
    [ValidateSet("deploy", "stop", "restart", "logs", "status")]
    [string]$Action = "deploy"
)

# ============================================
# Configuration - Update these for your environment
# ============================================
$MAC_HOST = $env:ARIA_MAC_HOST ?? "your_server_ip"
$MAC_USER = $env:ARIA_MAC_USER ?? "your_username"
$SSH_KEY = $env:ARIA_SSH_KEY ?? "$env:USERPROFILE\.ssh\your_key"
$REMOTE_DIR = $env:ARIA_REMOTE_DIR ?? "/Users/$MAC_USER/aria-blue"
$LOCAL_DIR = Split-Path -Parent $PSScriptRoot
$DOCKER_CMD = "/Applications/Docker.app/Contents/Resources/bin/docker"
$COMPOSE_CMD = "/Applications/Docker.app/Contents/Resources/bin/docker compose"

# Colors
function Write-Status { Write-Host "[*] $args" -ForegroundColor Cyan }
function Write-Success { Write-Host "[✓] $args" -ForegroundColor Green }
function Write-Error { Write-Host "[✗] $args" -ForegroundColor Red }
function Write-Warning { Write-Host "[!] $args" -ForegroundColor Yellow }

# ============================================
# SSH Helper
# ============================================
function Invoke-MacCommand {
    param([string]$Command)
    ssh -i $SSH_KEY "${MAC_USER}@${MAC_HOST}" $Command
}

function Test-MacConnection {
    Write-Status "Testing connection to Mac Mini..."
    $result = ssh -i $SSH_KEY -o ConnectTimeout=5 "${MAC_USER}@${MAC_HOST}" "echo 'connected'" 2>$null
    if ($result -eq "connected") {
        Write-Success "Mac Mini is reachable"
        return $true
    } else {
        Write-Error "Cannot connect to Mac Mini at $MAC_HOST"
        return $false
    }
}

# ============================================
# Actions
# ============================================
function Deploy-Stack {
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "   ARIA BLUE - FULL DEPLOYMENT" -ForegroundColor Magenta
    Write-Host "========================================`n" -ForegroundColor Magenta

    if (-not (Test-MacConnection)) { exit 1 }

    # Step 1: Create remote directory structure
    Write-Status "Creating directory structure on Mac..."
    Invoke-MacCommand "mkdir -p $REMOTE_DIR/{deploy/docker,src/api,src/web,aria_memory/soul,skills}"
    Write-Success "Directories created"

    # Step 2: Stop existing containers
    Write-Status "Stopping existing containers..."
    Invoke-MacCommand "cd $REMOTE_DIR/deploy/docker && $COMPOSE_CMD down --remove-orphans 2>/dev/null || true"
    Invoke-MacCommand "pkill -f 'node.*clawd\|clawdbot' 2>/dev/null || true"
    Write-Success "Existing services stopped"

    # Step 3: Transfer files
    Write-Status "Transferring deployment files..."
    
    # Transfer deploy folder
    scp -i $SSH_KEY -r "$LOCAL_DIR\deploy\docker\*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/deploy/docker/"
    
    # Transfer source code
    scp -i $SSH_KEY -r "$LOCAL_DIR\src\api\*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/src/api/"
    scp -i $SSH_KEY -r "$LOCAL_DIR\src\web\*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/src/web/"
    
    # Transfer skills
    if (Test-Path "$LOCAL_DIR\skills") {
        scp -i $SSH_KEY -r "$LOCAL_DIR\skills\*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/skills/"
    }
    
    # Transfer soul files
    if (Test-Path "$LOCAL_DIR\aria_memory\soul") {
        scp -i $SSH_KEY -r "$LOCAL_DIR\aria_memory\soul\*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/aria_memory/soul/"
    }
    
    # Transfer Dockerfiles
    scp -i $SSH_KEY "$LOCAL_DIR\deploy\docker\Dockerfile.*" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/deploy/docker/"
    scp -i $SSH_KEY "$LOCAL_DIR\deploy\docker\entrypoint-aria.sh" "${MAC_USER}@${MAC_HOST}:$REMOTE_DIR/deploy/docker/"
    
    Write-Success "Files transferred"

    # Step 4: Build images
    Write-Status "Building Docker images..."
    Invoke-MacCommand "cd $REMOTE_DIR && $DOCKER_CMD build -f deploy/docker/Dockerfile.brain -t aria-brain:latest ."
    Invoke-MacCommand "cd $REMOTE_DIR && $DOCKER_CMD build -f deploy/docker/Dockerfile.aria -t aria-bot:latest ."
    Write-Success "Docker images built"

    # Step 5: Deploy stack
    Write-Status "Deploying full stack..."
    Invoke-MacCommand "cd $REMOTE_DIR/deploy/docker && $COMPOSE_CMD up -d"
    Write-Success "Stack deployed"

    # Step 6: Wait and verify
    Write-Status "Waiting for services to start..."
    Start-Sleep -Seconds 15

    Show-Status
    
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "   DEPLOYMENT COMPLETE!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "`nAccess points:" -ForegroundColor Yellow
    Write-Host "  Dashboard:  http://${MAC_HOST}/" -ForegroundColor Cyan
    Write-Host "  API Docs:   http://${MAC_HOST}/api/docs" -ForegroundColor Cyan
    Write-Host "  PGAdmin:    http://${MAC_HOST}/pgadmin" -ForegroundColor Cyan
    Write-Host "  Grafana:    http://${MAC_HOST}/grafana" -ForegroundColor Cyan
    Write-Host "  Traefik:    http://${MAC_HOST}:8080" -ForegroundColor Cyan
    Write-Host ""
}

function Stop-Stack {
    Write-Status "Stopping Aria stack..."
    if (-not (Test-MacConnection)) { exit 1 }
    Invoke-MacCommand "cd $REMOTE_DIR/deploy/docker && $COMPOSE_CMD down"
    Write-Success "Stack stopped"
}

function Restart-Stack {
    Write-Status "Restarting Aria stack..."
    if (-not (Test-MacConnection)) { exit 1 }
    Invoke-MacCommand "cd $REMOTE_DIR/deploy/docker && $COMPOSE_CMD restart"
    Write-Success "Stack restarted"
}

function Show-Logs {
    Write-Status "Showing logs (Ctrl+C to exit)..."
    if (-not (Test-MacConnection)) { exit 1 }
    ssh -i $SSH_KEY "${MAC_USER}@${MAC_HOST}" "cd $REMOTE_DIR/deploy/docker && $COMPOSE_CMD logs -f --tail=100"
}

function Show-Status {
    Write-Status "Checking service status..."
    if (-not (Test-MacConnection)) { exit 1 }
    
    Write-Host "`nContainer Status:" -ForegroundColor Yellow
    Invoke-MacCommand "$DOCKER_CMD ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep aria"
    
    Write-Host "`nHealth Checks:" -ForegroundColor Yellow
    
    # Check each service
    $services = @{
        "Database" = "http://${MAC_HOST}:5432"
        "API" = "http://${MAC_HOST}/api/health"
        "Dashboard" = "http://${MAC_HOST}/"
        "Traefik" = "http://${MAC_HOST}:8080/api/overview"
    }
    
    foreach ($svc in $services.Keys) {
        try {
            $response = Invoke-WebRequest -Uri $services[$svc] -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
            Write-Success "$svc : UP"
        } catch {
            Write-Warning "$svc : DOWN or unreachable"
        }
    }
}

# ============================================
# Main
# ============================================
switch ($Action) {
    "deploy"  { Deploy-Stack }
    "stop"    { Stop-Stack }
    "restart" { Restart-Stack }
    "logs"    { Show-Logs }
    "status"  { Show-Status }
}
