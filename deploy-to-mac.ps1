#!/usr/bin/env pwsh
# ============================================
# Aria Brain - One-Click Mac Deployment Script
# Usage: .\deploy-to-mac.ps1 [-Message "commit message"] [-NoPush] [-RebuildOnly]
# ============================================
param(
    [string]$Message = "Auto-deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    [switch]$NoPush,
    [switch]$RebuildOnly,
    [string]$KeyPath = "$env:USERPROFILE\.ssh\najia_mac_key",
    [string]$MacUser = "najia",
    [string]$MacHost = "192.168.1.53",
    [string]$RemotePath = "/Users/najia/aria"
)

$ErrorActionPreference = "Stop"

function Write-Step { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Success { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warning { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[FAIL] $msg" -ForegroundColor Red; exit 1 }

# Verify SSH key exists
if (-not (Test-Path $KeyPath)) {
    Write-Fail "SSH key not found at: $KeyPath"
}

# Get the repository root
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$RepoRoot\.git")) {
    $RepoRoot = $PSScriptRoot
}
Push-Location $RepoRoot

try {
    # ============================================
    # Step 1: Git Operations (unless RebuildOnly)
    # ============================================
    if (-not $RebuildOnly) {
        Write-Step "Checking git status..."
        
        $status = git status --porcelain
        if ($status) {
            Write-Step "Staging all changes..."
            git add -A
            
            Write-Step "Committing with message: $Message"
            git commit -m $Message
            Write-Success "Changes committed"
        } else {
            Write-Warning "No changes to commit"
        }
        
        if (-not $NoPush) {
            Write-Step "Pushing to remote..."
            git push
            Write-Success "Pushed to remote"
        }
    }

    # ============================================
    # Step 2: SSH to Mac and Deploy
    # ============================================
    Write-Step "Connecting to Mac server ($MacUser@$MacHost)..."
    
    $sshCommand = @"
cd $RemotePath && \
echo '==> Pulling latest changes...' && \
git pull && \
echo '==> Entering stacks/brain directory...' && \
cd stacks/brain && \
echo '==> Stopping existing containers...' && \
docker compose down && \
echo '==> Building fresh images (no cache for web/api)...' && \
docker compose build --no-cache aria-web aria-api && \
echo '==> Starting all services...' && \
docker compose up -d && \
echo '==> Waiting for services to start...' && \
sleep 10 && \
echo '==> Service Status:' && \
docker compose ps && \
echo '' && \
echo '==> Deployment complete!'
"@

    # Execute SSH command
    ssh -i $KeyPath -o StrictHostKeyChecking=no "$MacUser@$MacHost" $sshCommand
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "`nDeployment completed successfully!"
        Write-Host "`nAccess your services at:" -ForegroundColor Cyan
        Write-Host "  - Dashboard: https://$MacHost/" -ForegroundColor White
        Write-Host "  - API Docs:  https://$MacHost/api/docs" -ForegroundColor White
        Write-Host "  - Clawdbot:  https://$MacHost/clawdbot/" -ForegroundColor White
        Write-Host "  - Grafana:   https://$MacHost/grafana/" -ForegroundColor White
    } else {
        Write-Fail "Deployment failed with exit code: $LASTEXITCODE"
    }

} catch {
    Write-Fail "Error: $_"
} finally {
    Pop-Location
}
