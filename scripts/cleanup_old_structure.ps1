# cleanup_old_structure.ps1
# Script to remove deprecated files/folders after migrating to new structure
# Review before running!

Write-Host "Aria Blue - Structure Cleanup Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This will remove deprecated files. Review before running!" -ForegroundColor Yellow
Write-Host ""

# Old skills folder (replaced by aria_skills/)
$oldSkills = @(
    "skills/",
    "skills/__init__.py",
    "skills/moltbook_poster.py",
    "skills/health_monitor.py",
    "skills/goal_scheduler.py",
    "skills/knowledge_graph.py",
    "skills/requirements.txt"
)

# Old app folder (replaced by aria_agents/ + aria_skills/)
$oldApp = @(
    "app/",
    "app/__init__.py",
    "app/main.py",
    "app/api/",
    "app/config/",
    "app/static/",
    "app/templates/",
    "app/utils/"
)

# Old src folder (merged into new structure)
$oldSrc = @(
    "src/",
    "src/api/",
    "src/database/",
    "src/web/"
)

# Files to remove
$filesToRemove = @(
    "STRUCTURE.md",          # Outdated structure doc
    "ARIA_MANUAL.md",        # Replaced by README.md
    "deploy.ps1"             # Old deploy script
)

Write-Host "Folders to remove:" -ForegroundColor Magenta
$oldSkills + $oldApp + $oldSrc | ForEach-Object { Write-Host "  - $_" }

Write-Host ""
Write-Host "Files to remove:" -ForegroundColor Magenta
$filesToRemove | ForEach-Object { Write-Host "  - $_" }

Write-Host ""
$confirm = Read-Host "Proceed with removal? (y/N)"

if ($confirm -eq "y" -or $confirm -eq "Y") {
    # Remove old skills folder
    if (Test-Path "skills") {
        Remove-Item -Recurse -Force "skills"
        Write-Host "Removed: skills/" -ForegroundColor Green
    }
    
    # Remove old app folder
    if (Test-Path "app") {
        Remove-Item -Recurse -Force "app"
        Write-Host "Removed: app/" -ForegroundColor Green
    }
    
    # Remove old src folder
    if (Test-Path "src") {
        Remove-Item -Recurse -Force "src"
        Write-Host "Removed: src/" -ForegroundColor Green
    }
    
    # Remove individual files
    foreach ($file in $filesToRemove) {
        if (Test-Path $file) {
            Remove-Item -Force $file
            Write-Host "Removed: $file" -ForegroundColor Green
        }
    }
    
    Write-Host ""
    Write-Host "Cleanup complete!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "New structure:" -ForegroundColor Cyan
    Write-Host "  aria_mind/    - OpenClaw workspace (SOUL.md, IDENTITY.md, etc.)"
    Write-Host "  aria_skills/  - Skill implementations"
    Write-Host "  aria_agents/  - Agent orchestration"
    Write-Host "  tests/        - pytest test suite"
    Write-Host "  stacks/       - Docker configurations (keep)"
    Write-Host "  scripts/      - Utility scripts (keep)"
    Write-Host "  aria_memory/  - Preserved data (keep)"
} else {
    Write-Host "Aborted." -ForegroundColor Red
}
