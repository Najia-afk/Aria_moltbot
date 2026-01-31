# ARIA MANUAL - Deployment Guide

Deployment guide for the Aria stack.

---

## Prerequisites

- Docker & Docker Compose
- macOS with Apple Silicon (for Metal GPU)
- Git

---

## Quick Deploy

### 1. Clone Repository

```bash
git clone https://github.com/aria-blue/aria.git
cd aria/stacks/brain
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
nano .env
```

### 3. Start Native Ollama (Metal GPU)

On macOS with Apple Silicon, run Ollama natively for GPU acceleration (~20 tok/s vs ~3 tok/s in Docker):

```bash
# Start native Ollama
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Pull models
ollama pull qwen3-vl:8b
```

### 4. Start Docker Stack

```bash
docker compose up -d
docker compose ps
```

---

## API Keys Required

Configure these in `.env`:

### Google Gemini
1. Go to https://aistudio.google.com/apikey
2. Create new API key
3. Add to `.env`: `GOOGLE_GEMINI_KEY=your_key_here`

### Moonshot/Kimi (Optional)
1. Go to https://platform.moonshot.cn/
2. Register and get API key
3. Add to `.env`: `MOONSHOT_KIMI_KEY=your_key_here`

---

## Database

The API auto-creates schema on startup. No manual database commands required.

### Legacy Data Import

If importing pre-existing data:

```bash
python scripts/import_legacy_csv.py
```

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| Traefik | 80/443 | HTTPS routing |
| API | 8000 | FastAPI backend |
| Web | 5000 | Flask UI |
| LiteLLM | 18793 | LLM router |
| Grafana | 3001 | Monitoring |
| PGAdmin | 5050 | DB admin |
| Clawdbot | 18789 | OpenClaw gateway |
| Prometheus | 9090 | Metrics |

---

## Troubleshooting

1. **Docker won't start:** Check `docker logs <container>`, verify .env
2. **Database errors:** Check postgres logs, verify credentials
3. **Slow LLM:** Ensure native Ollama is running (not Docker Ollama) for Metal GPU
4. **Can't access web UI:** Check firewall, verify ports open

---

## Checklist

### Initial Setup
- [ ] Repository cloned
- [ ] .env configured with credentials
- [ ] Native Ollama running with Metal GPU
- [ ] Docker stack started
- [ ] API keys added

### Verification
- [ ] `docker compose ps` shows all services healthy
- [ ] Grafana accessible
- [ ] LiteLLM responding
- [ ] Ollama generating at ~20 tok/s

---

*Aria Blue ⚡️ - Deployment Guide*
