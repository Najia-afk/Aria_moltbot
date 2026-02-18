# Aria Deployment

## Quick Start

All deployment is handled from `stacks/brain/`:

```bash
cd stacks/brain
./deploy.sh deploy
```

## Deploy Commands

| Command | Action |
|---------|--------|
| `./deploy.sh deploy` | Build & start all services |
| `./deploy.sh rebuild` | Force rebuild everything |
| `./deploy.sh stop` | Stop all containers |
| `./deploy.sh logs` | View container logs |
| `./deploy.sh status` | Health check all services |
| `./deploy.sh clean` | Remove all containers & volumes |

## Services (12 total)

| Service | Port | Purpose |
|---------|------|---------|
| aria-web | 5001 | Dashboard UI |
| aria-api | 8000 | FastAPI backend |
| aria-brain | 8001 | Core agent logic |
| litellm | 4000 | LLM router |
| traefik | 80/443 | Reverse proxy |
| aria-engine | 8100 | AI engine gateway |
| aria-db | 5432 | PostgreSQL |
| prometheus | 9090 | Metrics |
| grafana | 3001 | Dashboards |
| aria-pgadmin | 5050 | DB admin |
| aria-browser | 9222 | Headless Chrome |
| tor-proxy | 9050 | Tor network |

## Mac-Specific

The `mac/` folder contains:
- MLX server setup (for local models on Apple Silicon)

## Requirements

- Docker & Docker Compose
- `.env` file in `stacks/brain/` with required variables
