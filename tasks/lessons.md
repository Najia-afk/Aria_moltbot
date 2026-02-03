# Aria Deployment - Lessons Learned

## February 3, 2026 - Infrastructure Overhaul

### Issues Identified

1. **Hardcoded IPs and Paths**
   - Multiple references to `192.168.1.53` in configs
   - Hardcoded `/Users/najia/` paths in docker-compose
   - `host.docker.internal` assumed to always work

2. **Traefik Configuration**
   - Domain redirects to local IP instead of proxying properly
   - WebSocket handling for clawdbot inconsistent
   - Missing proper CORS headers for Tailscale access

3. **MLX Service Issues**
   - No graceful fallback when MLX runs out of RAM
   - Service gets stuck, blocking requests
   - LiteLLM not configured for automatic fallback

4. **Website API Data**
   - Wallet prices not pulling from API correctly
   - Some endpoints returning empty data
   - Missing error handling for offline services

### Solutions Implemented

1. **Portable Configuration**
   - Created `.env.template` with all configurable values
   - `SERVICE_HOST` variable for server IP/domain
   - `DOCKER_HOST_IP` for container-to-host communication
   - `MLX_ENABLED` flag to disable when insufficient RAM

2. **Traefik Improvements**
   - Added proper WebSocket headers (`websocket-headers` middleware)
   - Configured sticky sessions for clawdbot
   - Added CORS middleware (`cors-all`) for cross-origin access
   - Priority-based routing to avoid conflicts

3. **MLX Fallback**
   - Added `MLX_ENABLED=false` option in .env
   - Configured LiteLLM fallbacks: local -> free cloud -> paid
   - API gracefully skips MLX health checks when disabled

4. **One-Click Deploy**
   - `deploy.sh` script for full stack deployment
   - `server-rebuild.sh` for clean rebuild with --disable-moltbook option
   - Proper initialization of database scripts and Grafana provisioning

### Key Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SERVICE_HOST` | Server IP or domain | `192.168.1.53` |
| `SERVICE_PROTOCOL` | http or https | `https` |
| `DOCKER_HOST_IP` | Host IP from container | `host.docker.internal` |
| `MLX_ENABLED` | Enable MLX service | `true` or `false` |
| `MOLTBOOK_TOKEN` | Leave empty to disable auto-post | `` |

### Git Workflow Pattern

```bash
# LOCAL: Make changes, commit, push
git add . && git commit -m "message" && git push

# SERVER: Pull and rebuild
ssh server
cd ~/aria-blue && git pull
cd stacks/brain && ./server-rebuild.sh --disable-moltbook
```

### Testing Checklist

- [ ] All services start without errors
- [ ] Clawdbot WebSocket connects properly
- [ ] API /status returns all services
- [ ] Wallet balances fetch correctly
- [ ] Models list populates
- [ ] Tailscale access works (no redirect loops)

### Notes for Future

1. Consider adding Let's Encrypt for production TLS
2. Add health check endpoint for MLX with RAM monitoring
3. Implement proper service discovery instead of hardcoded URLs
4. Add Prometheus alerts for service failures
