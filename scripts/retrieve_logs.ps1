# =============================================================================
# retrieve_logs.ps1 — Pull logs from Mac Mini for offline analysis (Windows)
# TICKET-28: Log Analysis (Aria Blue v1.1)
#
# Usage:
#   .\scripts\retrieve_logs.ps1 [-OutputDir DIR] [-Hours N]
# =============================================================================
[CmdletBinding()]
param(
    [string]$OutputDir = "aria_memories\logs",
    [int]$Hours = 168,
    [string]$SSHKey = "$env:USERPROFILE\.ssh\najia_mac_key",
    [string]$SSHHost = "najia@192.168.1.53"
)

$ErrorActionPreference = "Continue"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

Write-Host "=== Aria Log Retrieval — $(Get-Date) ===" -ForegroundColor Cyan
Write-Host "Target: $SSHHost | Hours: ${Hours}h | Output: $OutputDir"
Write-Host ""

$SSHBase = "ssh -i `"$SSHKey`" -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SSHHost"

# ---- 1. OpenClaw (clawdbot) logs ----
Write-Host "[1/4] Retrieving OpenClaw logs (${Hours}h)..." -ForegroundColor Yellow
$OpenClawFile = Join-Path $OutputDir "openclaw_${Timestamp}.log"
try {
    $output = & ssh -i $SSHKey -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SSHHost "docker logs clawdbot --since ${Hours}h 2>&1" 2>&1
    $output | Out-File -FilePath $OpenClawFile -Encoding utf8
    $lineCount = (Get-Content $OpenClawFile | Measure-Object -Line).Lines
    Write-Host "  OK Saved $lineCount lines -> $OpenClawFile" -ForegroundColor Green
} catch {
    Write-Host "  FAIL Failed to retrieve OpenClaw logs: $_" -ForegroundColor Red
    "RETRIEVAL_FAILED" | Out-File -FilePath $OpenClawFile
}

# ---- 2. LiteLLM logs ----
Write-Host "[2/4] Retrieving LiteLLM logs (tail 2000)..." -ForegroundColor Yellow
$LiteLLMFile = Join-Path $OutputDir "litellm_${Timestamp}.log"
try {
    $output = & ssh -i $SSHKey -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SSHHost "docker logs litellm --tail 2000 2>&1" 2>&1
    $output | Out-File -FilePath $LiteLLMFile -Encoding utf8
    $lineCount = (Get-Content $LiteLLMFile | Measure-Object -Line).Lines
    Write-Host "  OK Saved $lineCount lines -> $LiteLLMFile" -ForegroundColor Green
} catch {
    Write-Host "  FAIL Failed to retrieve LiteLLM logs: $_" -ForegroundColor Red
    "RETRIEVAL_FAILED" | Out-File -FilePath $LiteLLMFile
}

# ---- 3. MLX process info ----
Write-Host "[3/4] Retrieving MLX process info..." -ForegroundColor Yellow
$MLXFile = Join-Path $OutputDir "mlx_processes_${Timestamp}.log"
try {
    $output = & ssh -i $SSHKey -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SSHHost "ps aux | grep -i mlx 2>&1; echo '---'; top -l 1 -n 10 2>/dev/null | head -20 || echo 'top unavailable'" 2>&1
    $output | Out-File -FilePath $MLXFile -Encoding utf8
    Write-Host "  OK Saved -> $MLXFile" -ForegroundColor Green
} catch {
    Write-Host "  FAIL Failed to retrieve MLX info: $_" -ForegroundColor Red
    "RETRIEVAL_FAILED" | Out-File -FilePath $MLXFile
}

# ---- 4. Docker stats snapshot ----
Write-Host "[4/4] Retrieving Docker stats snapshot..." -ForegroundColor Yellow
$DockerFile = Join-Path $OutputDir "docker_stats_${Timestamp}.log"
try {
    $output = & ssh -i $SSHKey -o ConnectTimeout=10 -o StrictHostKeyChecking=no $SSHHost "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1; echo '---'; docker stats --no-stream 2>&1" 2>&1
    $output | Out-File -FilePath $DockerFile -Encoding utf8
    Write-Host "  OK Saved -> $DockerFile" -ForegroundColor Green
} catch {
    Write-Host "  FAIL Failed to retrieve Docker stats: $_" -ForegroundColor Red
    "RETRIEVAL_FAILED" | Out-File -FilePath $DockerFile
}

Write-Host ""
Write-Host "=== Retrieval complete ===" -ForegroundColor Cyan
Write-Host "Log files:"
Get-ChildItem -Path $OutputDir -Filter "*_${Timestamp}.log" | Format-Table Name, Length, LastWriteTime -AutoSize
