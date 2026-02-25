# S-28: First-Run Script & Quickstart Documentation
**Epic:** E15 — Fresh Install | **Priority:** P1 | **Points:** 3 | **Phase:** 2

## Problem
When someone clones the repo and runs `docker compose up`, several things break or are confusing:

1. **No API keys for LLM providers** → ALL model calls fail. No Moonshot key (kimi), no OpenRouter key, no Ollama running natively. No clear guidance on which keys are required.

2. **`LITELLM_MASTER_KEY` defaults to `sk-change-me`** → LiteLLM starts but uses a known insecure key.

3. **Docker socket proxy requires `/var/run/docker.sock`** → fails on Windows.

4. **Ollama expected running natively** on `host.docker.internal:11434` — not documented for non-Mac users. Windows/Linux have different host networking.

5. **aria-web doesn't depend on aria-api** → web shows errors for first 30-60 seconds until API is ready.

6. **No .env file guidance** — `.env.example` exists with 80+ variables but no indication of which are REQUIRED vs optional.

## Root Cause
The project was developed on a specific Mac Mini. No fresh-install testing on clean machines, especially Windows or Linux.

## Fix

### Fix 1: Create first-run script
**File:** `scripts/first-run.sh` (NEW)
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Aria First-Run Setup"
echo "========================"

# 1. Detect OS
OS=$(uname -s)
echo "Detected OS: $OS"

# 2. Copy .env.example if no .env
if [ ! -f stacks/brain/.env ]; then
    cp stacks/brain/.env.example stacks/brain/.env
    echo "✓ Created stacks/brain/.env from template"
fi

# 3. Prompt for required keys
echo ""
echo "📋 Required API Keys:"
echo "  - At minimum, you need ONE LLM provider key."
echo "  - Recommended: MOONSHOT_API_KEY (for kimi model)"
read -p "MOONSHOT_API_KEY (press Enter to skip): " MOONSHOT_KEY
if [ -n "$MOONSHOT_KEY" ]; then
    sed -i "s/MOONSHOT_API_KEY=.*/MOONSHOT_API_KEY=$MOONSHOT_KEY/" stacks/brain/.env
fi

read -p "OPENROUTER_API_KEY (press Enter to skip): " OR_KEY
if [ -n "$OR_KEY" ]; then
    sed -i "s/OPENROUTER_API_KEY=.*/OPENROUTER_API_KEY=$OR_KEY/" stacks/brain/.env
fi

# 4. Generate random LiteLLM master key
LITELLM_KEY="sk-aria-$(openssl rand -hex 16)"
sed -i "s/LITELLM_MASTER_KEY=.*/LITELLM_MASTER_KEY=$LITELLM_KEY/" stacks/brain/.env
echo "✓ Generated random LITELLM_MASTER_KEY"

# 5. Generate random ARIA_API_KEY
API_KEY="aria-$(openssl rand -hex 16)"
sed -i "s/ARIA_API_KEY=.*/ARIA_API_KEY=$API_KEY/" stacks/brain/.env
echo "✓ Generated random ARIA_API_KEY"

# 6. Adjust for OS
if [ "$OS" = "Linux" ] || [ "$OS" = "MINGW"* ]; then
    echo "⚠️  Docker socket proxy may need adjustment for your OS."
    echo "   See S-01 for details."
fi

# 7. Check for Ollama
if command -v ollama &>/dev/null; then
    echo "✓ Ollama detected — local models available"
else
    echo "ℹ  Ollama not found — local models (qwen3-mlx) will be unavailable"
    echo "   Install: https://ollama.com"
fi

echo ""
echo "✅ Setup complete! Run: docker compose up -d"
echo "   Web UI: http://localhost:5050"
echo "   API:    http://localhost:8000/docs"
echo "   Your API key: $API_KEY"
```

### Fix 2: Create Windows PowerShell version
**File:** `scripts/first-run.ps1` (NEW)
Same logic as first-run.sh but for Windows PowerShell.

### Fix 3: Add Quickstart section to README
**File:** `README.md`
```markdown
## 🚀 Quickstart (5 minutes)

### Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- At least one LLM API key (Moonshot recommended for kimi)

### First Run
```bash
# Clone
git clone <repo-url> && cd Aria_moltbot

# Run setup
./scripts/first-run.sh   # macOS/Linux
# or
.\scripts\first-run.ps1  # Windows

# Start
docker compose up -d

# Wait ~60 seconds for all services to be healthy
docker compose ps

# Open
open http://localhost:5050
```

### Required Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| MOONSHOT_API_KEY | For kimi model | Moonshot AI key |
| OPENROUTER_API_KEY | For free models | OpenRouter key |
| ARIA_API_KEY | Auto-generated | API authentication |
| LITELLM_MASTER_KEY | Auto-generated | LiteLLM internal |
```

### Fix 4: Mark required vs optional vars in .env.example
**File:** `stacks/brain/.env.example`
Add clear section headers:
```env
# ═══════════════════════════════════════
# REQUIRED — Aria will not function without these
# ═══════════════════════════════════════
ARIA_API_KEY=change-me
LITELLM_MASTER_KEY=sk-change-me

# ═══════════════════════════════════════
# LLM PROVIDERS — At least one is required
# ═══════════════════════════════════════
MOONSHOT_API_KEY=
OPENROUTER_API_KEY=

# ═══════════════════════════════════════
# OPTIONAL — Defaults work for development
# ═══════════════════════════════════════
DB_PASSWORD=Aria2026secure
...
```

### Fix 5: Add aria-api dependency to aria-web
**File:** `stacks/brain/docker-compose.yml`
```yaml
  aria-web:
    depends_on:
      aria-db:
        condition: service_healthy
      aria-api:
        condition: service_healthy  # NEW — wait for API
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | Script/docs only |
| 2 | .env for secrets | ✅ | Keys in .env |
| 3 | models.yaml truth | ❌ | |
| 4 | Docker-first testing | ✅ | Scripts target Docker |
| 5 | aria_memories writable | ❌ | |
| 6 | No soul modification | ❌ | |

## Dependencies
- S-01 (Docker portability) — first-run script references Docker socket fix
- S-16 (auth) — first-run generates API key

## Verification
```bash
# 1. Fresh install simulation:
rm -f stacks/brain/.env
./scripts/first-run.sh
cat stacks/brain/.env | grep 'ARIA_API_KEY'
# EXPECTED: Random key generated

# 2. Docker compose up succeeds:
docker compose up -d
sleep 60
docker compose ps
# EXPECTED: All services healthy

# 3. Web UI accessible:
curl -s -o /dev/null -w "%{http_code}" http://localhost:5050
# EXPECTED: 200

# 4. README has quickstart:
grep -c 'Quickstart' README.md
# EXPECTED: ≥ 1
```

## Prompt for Agent
```
Read these files FIRST:
- stacks/brain/.env.example (full)
- stacks/brain/docker-compose.yml (L1-L50 — service overview)
- README.md (full)
- scripts/ — list existing scripts

CONSTRAINTS: #2 (.env for secrets). Must work on macOS, Linux, AND Windows.

STEPS:
1. Create scripts/first-run.sh with OS detection, key generation, env setup
2. Create scripts/first-run.ps1 for Windows PowerShell
3. Add Quickstart section to README.md
4. Mark required vs optional vars in .env.example with clear section headers
5. Add aria-api to aria-web depends_on in docker-compose.yml
6. Test on a clean directory (no .env file)
7. Ensure scripts are executable (chmod +x)
8. Add .env to .gitignore (if not already)
9. Verify docker compose up works after running first-run script
```
