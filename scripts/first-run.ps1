# ──────────────────────────────────────────────────────────────
# Aria Brain Stack — First-Run Setup Script (Windows PowerShell)
# Creates .env from .env.example with required secrets generated.
# ──────────────────────────────────────────────────────────────
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$StackDir  = Join-Path $RepoRoot "stacks\brain"
$EnvExample= Join-Path $StackDir ".env.example"
$EnvFile   = Join-Path $StackDir ".env"

function Write-Banner {
    Write-Host ""
    Write-Host "  +==========================================+" -ForegroundColor Cyan
    Write-Host "  |       Aria Brain -- First Run            |" -ForegroundColor Cyan
    Write-Host "  +==========================================+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Info  { param($Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Green }
function Write-Warn  { param($Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err   { param($Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }

function New-Secret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes) -replace '[/+=]','' | ForEach-Object { $_.Substring(0, [Math]::Min(43, $_.Length)) }
}

# ── Pre-flight checks ────────────────────────────────────────

Write-Banner

# Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Err "Docker is not installed. Please install Docker Desktop."
    Write-Err "  https://docs.docker.com/desktop/install/windows-install/"
    exit 1
}

try {
    docker info 2>$null | Out-Null
} catch {
    Write-Err "Docker daemon is not running. Please start Docker Desktop."
    exit 1
}

Write-Info "Docker detected: $(docker --version)"

# Docker Compose
$ComposeCmd = $null
try {
    docker compose version 2>$null | Out-Null
    $ComposeCmd = "docker compose"
} catch {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        $ComposeCmd = "docker-compose"
    }
}

if (-not $ComposeCmd) {
    Write-Err "Docker Compose not found. Please install Docker Compose."
    exit 1
}

Write-Info "Compose detected"

# Ollama (optional)
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Info "Ollama detected"
} else {
    Write-Warn "Ollama not found - local models won't be available."
    Write-Warn "  Install: https://ollama.com/download"
}

# ── .env Setup ────────────────────────────────────────────────

if (-not (Test-Path $EnvExample)) {
    Write-Err "Cannot find $EnvExample"
    exit 1
}

if (Test-Path $EnvFile) {
    Write-Warn ".env already exists at $EnvFile"
    $choice = Read-Host "Overwrite? (y/N)"
    if ($choice -ne 'y' -and $choice -ne 'Y') {
        Write-Info "Keeping existing .env. Exiting."
        exit 0
    }
    $timestamp = Get-Date -Format "yyyyMMddHHmmss"
    Copy-Item $EnvFile "$EnvFile.bak.$timestamp"
    Write-Info "Backed up existing .env"
}

Copy-Item $EnvExample $EnvFile
Write-Info "Created .env from .env.example"

# ── Generate required secrets ─────────────────────────────────

Write-Info "Generating secrets..."

$DbPass      = New-Secret
$WebKey       = New-Secret
$LitellmKey   = "sk-aria-$(New-Secret)"
$GrafanaPass  = New-Secret
$PgadminPass  = New-Secret
$ApiKey       = New-Secret
$AdminKey     = New-Secret

function Set-EnvValue {
    param([string]$Key, [string]$Value)
    $content = Get-Content $EnvFile -Raw
    # Replace KEY= (empty) with KEY=value
    $content = $content -replace "(?m)^${Key}=$", "${Key}=${Value}"
    Set-Content $EnvFile -Value $content -NoNewline
}

Set-EnvValue "DB_PASSWORD"       $DbPass
Set-EnvValue "WEB_SECRET_KEY"    $WebKey
Set-EnvValue "LITELLM_MASTER_KEY" $LitellmKey
Set-EnvValue "GRAFANA_PASSWORD"  $GrafanaPass
Set-EnvValue "PGADMIN_PASSWORD"  $PgadminPass
Set-EnvValue "ARIA_API_KEY"      $ApiKey
Set-EnvValue "ARIA_ADMIN_KEY"    $AdminKey

Write-Info "Required secrets generated and written to .env"

# ── Optional: prompt for API keys ─────────────────────────────

Write-Host ""
Write-Host "Optional API Keys (press Enter to skip)" -ForegroundColor Cyan
Write-Host ""

$OrKey = Read-Host "OpenRouter API Key (sk-or-v1-...)"
if ($OrKey) {
    Set-EnvValue "OPEN_ROUTER_KEY" $OrKey
    Write-Info "OpenRouter key saved"
}

$KimiKey = Read-Host "Moonshot/Kimi API Key"
if ($KimiKey) {
    Set-EnvValue "MOONSHOT_KIMI_KEY" $KimiKey
    Write-Info "Moonshot key saved"
}

# ── Summary ───────────────────────────────────────────────────

Write-Host ""
Write-Host "+==================================================+" -ForegroundColor Green
Write-Host "|  Setup complete!                                  |" -ForegroundColor Green
Write-Host "+==================================================+" -ForegroundColor Green
Write-Host ""
Write-Host "  .env location:  $EnvFile"
Write-Host ""
Write-Host "  Generated credentials:"
Write-Host "    DB_PASSWORD       = $($DbPass.Substring(0,8))..."
Write-Host "    WEB_SECRET_KEY    = $($WebKey.Substring(0,8))..."
Write-Host "    LITELLM_MASTER_KEY= $($LitellmKey.Substring(0,15))..."
Write-Host "    ARIA_API_KEY      = $($ApiKey.Substring(0,8))..."
Write-Host "    ARIA_ADMIN_KEY    = $($AdminKey.Substring(0,8))..."
Write-Host "    GRAFANA_PASSWORD  = $($GrafanaPass.Substring(0,8))..."
Write-Host "    PGADMIN_PASSWORD  = $($PgadminPass.Substring(0,8))..."
Write-Host ""
Write-Host "  Next steps:"
Write-Host "    1. Review/edit:  notepad $EnvFile"
Write-Host "    2. Start stack:  cd $StackDir; $ComposeCmd up -d"
Write-Host "    3. Open web UI:  http://localhost:5000"
Write-Host "    4. Open API docs: http://localhost:8000/docs"
Write-Host ""
