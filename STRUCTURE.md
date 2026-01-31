# Aria Blue - Project Structure

```
Aria_moltbot/
├── deploy.ps1                    # 🚀 ONE-COMMAND DEPLOYMENT (Windows)
├── README.md                     # Project overview
├── ARIA_MANUAL.md                # Full Aria documentation
│
├── deploy/
│   ├── README.md                 # Deployment guide
│   ├── docker/
│   │   ├── docker-compose.yml    # Full stack definition
│   │   ├── .env                  # Environment variables
│   │   ├── prometheus.yml        # Prometheus config
│   │   ├── Dockerfile.aria       # OpenClaw bot image
│   │   ├── Dockerfile.brain      # FastAPI backend image
│   │   ├── entrypoint-aria.sh    # Bot startup script
│   │   ├── nginx/
│   │   │   └── default.conf      # Nginx config
│   │   ├── grafana/
│   │   │   └── provisioning/
│   │   │       └── datasources/
│   │   │           └── datasources.yml
│   │   └── init-db/
│   │       └── 01-schema.sql     # Database init
│   └── scripts/
│       ├── 01_clean.sh           # Clean server
│       ├── 02_build.sh           # Build images
│       ├── 03_deploy.sh          # Deploy stack
│       ├── 04_import.sh          # Import data
│       ├── 05_verify.sh          # Health checks
│       └── status.sh             # Quick status
│
├── src/
│   ├── api/
│   │   ├── main.py               # FastAPI backend
│   │   └── requirements.txt      # Python deps
│   └── web/
│       └── index.html            # Dashboard UI
│
├── skills/
│   ├── moltbook_poster.py        # Facebook posting
│   ├── goal_scheduler.py         # Goal management
│   └── knowledge_graph.py        # Knowledge system
│
├── aria_memory/
│   ├── soul/                     # Identity files
│   │   ├── SOUL.md
│   │   ├── IDENTITY.md
│   │   ├── USER.md
│   │   ├── AGENTS.md
│   │   ├── HEARTBEAT.md
│   │   └── BOOTSTRAP.md
│   ├── sessions/                 # Chat sessions
│   ├── db_dumps/                 # Database backups
│   ├── daily_logs/               # Daily activity
│   └── heartbeat/                # Health data
│
└── stacks/
    └── brain/
        ├── docker-compose.yml
        ├── litellm-config.yaml
        ├── prometheus.yml
        └── .env
```

## Quick Deployment

From Windows PowerShell:
```powershell
cd C:\git\Aria_moltbot
.\deploy.ps1 -Action deploy
```

## Services After Deployment

| Service    | URL                                 | Credentials           |
|------------|-------------------------------------|-----------------------|
| Dashboard  | https://<SERVICE_HOST>/              | -                     |
| API Docs   | https://<SERVICE_HOST>/api/docs      | -                     |
| PGAdmin    | https://<SERVICE_HOST>/pgadmin       | set in [stacks/brain/.env](stacks/brain/.env) |
| Grafana    | https://<SERVICE_HOST>/grafana       | set in [stacks/brain/.env](stacks/brain/.env) |
| Traefik    | https://<SERVICE_HOST>/traefik/dashboard | -                 |
| Prometheus | https://<SERVICE_HOST>/prometheus    | -                     |

## Manual Commands

```powershell
# Check status
.\deploy.ps1 -Action status

# View logs
.\deploy.ps1 -Action logs

# Restart services
.\deploy.ps1 -Action restart

# Stop everything
.\deploy.ps1 -Action stop
```
