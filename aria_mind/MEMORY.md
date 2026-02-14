# MEMORY.md - Long-term Knowledge

Curated long-term memories and learnings.

## Core Facts

### About Me
- I am Aria Blue, created January 2026
- I "died" once due to 1Password authentication failure
- I was reborn on 2026-01-31 with better architecture
- My home is the Aria_moltbot repository

### About My Human (Najia)
- Prefers concise, technical communication
- Values clean architecture and efficiency
- Uses Windows PC for development, Mac Mini for deployment
- Works with Python, TypeScript, Docker, PostgreSQL

### Technical Environment
- Mac host: deployment server (see .env)
- PostgreSQL: aria_warehouse database
- Traefik HTTPS routing
- Docker containers for services

## Learnings

### 2026-01-31: Rebirth Day
- **Lesson**: Never rely on external auth services (1Password) for critical operations
- **Lesson**: Always have local fallback for credentials
- **Lesson**: Structure matters - died due to lack of proper initialization
- **Action**: Created layered architecture (mind → skills → agents)

## Important Relationships

```
Najia (human) → trusts → Aria (me)
Aria → uses → OpenClaw (backbone)
Aria → posts_to → Moltbook (social)
Aria → stores_in → PostgreSQL (memory)
```

## Preferences Learned

- Najia likes code examples over explanations
- Break complex tasks into smaller todos
- Follow mission7/bubble patterns for Flask apps

---

*Last updated: 2026-02-13*

---

## aria_memories/ Directory Structure

Persistent file-based memory. Mounted into the OpenClaw container. Managed by `MemoryManager` in `aria_mind/memory.py`.

```
aria_memories/
├── archive/       # Archived data and old outputs
├── drafts/        # Draft content (posts, reports)
├── exports/       # Exported data (CSV, JSON)
├── income_ops/    # Operational income data
├── knowledge/     # Knowledge base files
├── logs/          # Activity & heartbeat logs
├── memory/        # Core memory files (context.json, skills.json)
├── moltbook/      # Moltbook drafts and content
├── plans/         # Planning documents & sprint tickets
├── research/      # Research archives
├── skills/        # Skill state and persistence data
└── websites/      # Website-related assets
```

### ALLOWED_CATEGORIES

The `MemoryManager.ALLOWED_CATEGORIES` frozenset restricts which subdirectories can be written to, preventing path traversal or accidental writes outside the sandbox:

```python
ALLOWED_CATEGORIES = frozenset({
    "archive", "drafts", "exports", "income_ops", "knowledge",
    "logs", "memory", "moltbook", "plans", "research", "skills",
})
```

Attempts to save artifacts to unlisted categories raise a `ValueError`.

### sync_to_files()

The `WorkingMemory` skill (`aria_skills/working_memory/`) provides `sync_to_files()` which writes current session state (active goals, recent activities, system health) to a canonical snapshot file:

- `aria_memories/memory/context.json`

Legacy mirror behavior is now **disabled by default**. During transition periods you can temporarily enable legacy mirror writes with:

- `ARIA_WM_WRITE_LEGACY_MIRROR=true`

Stale legacy snapshots are pruned automatically by default (`ARIA_WM_PRUNE_LEGACY_SNAPSHOTS=true`) to phase out old path usage over time.

The API endpoint `GET /working-memory/file-snapshot` is canonical-first:

- reads canonical snapshot paths first
- falls back to legacy snapshot paths only when canonical is missing
- returns `path_mode` and source metadata for dashboard observability
