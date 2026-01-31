# Aria Moltbot - Deployment System

## Project Structure

```
Aria_moltbot/
├── deploy/                    # Deployment scripts & configs
│   ├── scripts/
│   │   ├── 01_clean.sh       # Kill processes, clean server
│   │   ├── 02_build.sh       # Build Docker images
│   │   ├── 03_deploy.sh      # Deploy full stack
│   │   ├── 04_import.sh      # Import data & soul
│   │   └── 05_verify.sh      # Health checks
│   ├── docker/
│   │   ├── Dockerfile.aria   # Alpine-based Aria image
│   │   ├── Dockerfile.brain  # Brain/API image
│   │   └── docker-compose.yml
│   ├── nginx/
│   │   └── nginx.conf        # Reverse proxy for web access
│   └── config/
│       └── .env.production
│
├── aria_memory/              # Preserved data (extracted)
├── skills/                   # Python skills
├── stacks/                   # Stack configurations
└── src/                      # Source code
    ├── api/                  # FastAPI backend
    ├── brain/                # Brain logic
    └── web/                  # Web dashboard
```

## Quick Deploy (from Windows)

```powershell
# One-command deploy
.\deploy\deploy.ps1 -Target <SERVICE_HOST>
```

## Web Access (after deployment)

| Service | URL | Purpose |
|---------|-----|---------|
| Dashboard | https://<SERVICE_HOST>/ | Main Aria UI |
| Grafana | https://<SERVICE_HOST>/grafana | Monitoring |
| Traefik | https://<SERVICE_HOST>/traefik/dashboard | Proxy dashboard |
| API | https://<SERVICE_HOST>/api | REST API |
| PGAdmin | https://<SERVICE_HOST>/pgadmin | Database UI |

## Components

- **OpenClaw/Clawdbot**: AI chat interface (from git)
- **PostgreSQL**: Data warehouse
- **Traefik**: Reverse proxy + SSL
- **Grafana + Prometheus**: Monitoring
- **LiteLLM**: Model router
