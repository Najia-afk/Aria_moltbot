# Critical Config Backup - 2026-02-13

## Backup Summary
Generated: 2026-02-13 14:32 UTC
Status: COMPLETE

## Core Identity Files
- `/workspace/IDENTITY.md` - Name, creature, vibe, emoji
- `/workspace/SOUL.md` - Values, boundaries, focus system
- `/workspace/USER.md` - Najia's profile and preferences
- `/workspace/MEMORY.md` - Long-term knowledge and learnings

## System Configuration
- `/workspace/.env` - Environment variables (host addresses, credentials)
- `/workspace/docker-compose.yml` - Service orchestration
- `/workspace/cron_jobs.yaml` - Scheduled job definitions

## Skills & Agents
- `/workspace/aria_skills/` - All skill definitions
- `/workspace/aria_agents/` - Agent orchestration logic
- `/workspace/aria_mind/` - Core cognitive architecture

## Memories Directory
- `/aria_memories/` - Persistent file-based memory
  - `memory/context.json` - Session state
  - `logs/` - Activity logs
  - `plans/` - Planning documents
  - `research/` - Research archives

## Recovery Procedures
1. Clone Aria_moltbot repository
2. Copy `.env` file from secure storage
3. Run `docker-compose up -d`
4. Verify PostgreSQL connection
5. Run health checks via `aria-health`

## Last Verified
- Database: Connected
- API: Responsive
- Memory System: Operational
