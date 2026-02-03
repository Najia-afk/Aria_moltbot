# Aria Deployment Tasks - February 3, 2026

## Overview
Complete infrastructure overhaul for portable, secure, one-click deployment.

---

## ✅ All Tasks Completed

### 1. Fix Traefik Configuration ✅
- Created [traefik-dynamic.yaml.new](../stacks/brain/traefik-dynamic.yaml.new) with:
  - Proper WebSocket headers for clawdbot
  - CORS middleware for Tailscale access
  - Sticky sessions for WebSocket stability
  - Priority-based routing

### 2. Remove Hardcoded Paths ✅
- Created [.env.template](../stacks/brain/.env.template) with all configurable values
- Created [docker-compose.portable.yml](../stacks/brain/docker-compose.portable.yml):
  - All IPs use `${SERVICE_HOST}` variable
  - Docker host uses `${DOCKER_HOST_IP}` (default: host.docker.internal)
  - Added `extra_hosts` for Linux compatibility

### 3. Website API Data Fetching ✅
- Fixed [main.py](../src/api/main.py):
  - Added `MLX_ENABLED` flag to disable MLX when not available
  - Made `DOCKER_HOST_IP` configurable
  - MLX service gracefully excluded when disabled

### 4. MLX Investigation ✅
- Created [litellm-config.portable.yaml](../stacks/brain/litellm-config.portable.yaml):
  - Fallback chain: local -> free cloud -> paid
  - Auto-fallback when MLX fails (RAM issues)
- Added `MLX_ENABLED=false` option to disable MLX service

### 5. One-Click Deploy Solution ✅
- Created [deploy.sh](../stacks/brain/deploy.sh):
  - `deploy` - Build and deploy
  - `rebuild` - Clean destroy and redeploy
  - `stop`, `logs`, `status`, `clean` commands
- Created [server-rebuild.sh](../stacks/brain/server-rebuild.sh):
  - Full server rebuild script
  - `--disable-moltbook` option to clear MOLTBOOK_TOKEN

### 6. Git Workflow ✅
- Updated [agent-workflow.md](../prompts/agent-workflow.md) with deployment workflow

---

## 🚀 Deployment Instructions

### Step 1: Commit and Push Locally
```powershell
cd c:\git\Aria_moltbot
git add .
git commit -m "Infrastructure overhaul - portable deployment"
git push origin main
```

### Step 2: SSH to Mac Server
```powershell
ssh -i .\najia_mac_key najia@192.168.1.53
```

### Step 3: Pull and Rebuild
```bash
cd ~/aria-blue
git pull origin main

# Copy new portable files over existing ones
cd stacks/brain
cp docker-compose.portable.yml docker-compose.yml
cp traefik-dynamic.yaml.new traefik-dynamic.yaml
cp litellm-config.portable.yaml litellm-config.yaml

# Edit .env if needed (especially to clear MOLTBOOK_TOKEN)
nano .env
# Set: MOLTBOOK_TOKEN=

# Rebuild
chmod +x deploy.sh server-rebuild.sh
./server-rebuild.sh --disable-moltbook
```

### Step 4: Verify
- Dashboard: https://192.168.1.53/
- Clawdbot: https://192.168.1.53/clawdbot/
- API: https://192.168.1.53/api/docs
- Services: https://192.168.1.53/services

---

## Files Changed

| File | Status | Purpose |
|------|--------|---------|
| `stacks/brain/.env.template` | NEW | Template for portable deployment |
| `stacks/brain/docker-compose.portable.yml` | NEW | Portable docker-compose |
| `stacks/brain/traefik-dynamic.yaml.new` | NEW | Fixed Traefik config |
| `stacks/brain/litellm-config.portable.yaml` | NEW | LiteLLM with fallbacks |
| `stacks/brain/deploy.sh` | NEW | One-click deploy script |
| `stacks/brain/server-rebuild.sh` | NEW | Server rebuild script |
| `src/api/main.py` | MODIFIED | MLX_ENABLED flag |
| `prompts/agent-workflow.md` | MODIFIED | Git workflow docs |
| `tasks/lessons.md` | NEW | Lessons learned |
| `tasks/todo.md` | NEW | This file |
