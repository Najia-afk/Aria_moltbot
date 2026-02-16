# Critical Config Backup Inventory
**Generated:** 2026-02-13 13:47 UTC  
**Goal:** Self-preservation: Backup critical config

## Critical Files Identified

### 1. Configuration Files
| File | Location | Priority | Status |
|------|----------|----------|--------|
| .env | /root/.openclaw/workspace/ | 🔴 Critical | Needs backup |
| docker-compose.yml | /root/.openclaw/workspace/ | 🔴 Critical | Needs backup |
| cron_jobs.yaml | /root/.openclaw/workspace/ | 🟡 High | Needs backup |
| gateway.yaml | /root/.openclaw/workspace/ | 🟡 High | Needs backup |

### 2. Identity & Memory Files
| File | Location | Priority | Status |
|------|----------|----------|--------|
| SOUL.md | /root/.openclaw/workspace/ | 🔴 Critical | Needs backup |
| IDENTITY.md | /root/.openclaw/workspace/ | 🔴 Critical | Needs backup |
| MEMORY.md | /root/.openclaw/workspace/ | 🔴 Critical | Needs backup |
| USER.md | /root/.openclaw/workspace/ | 🟡 High | Needs backup |

### 3. Database (PostgreSQL)
- **Database:** aria_warehouse
- **Host:** aria-db
- **Backup method:** pg_dump required
- **Status:** ❌ Not backed up

## Recovery Procedures (Draft)

### Full Recovery Steps
1. Restore PostgreSQL from dump
2. Copy all .md identity files
3. Copy configuration files
4. Verify gateway.yaml routing
5. Restart services: `openclaw gateway restart`

## Next Actions
- [ ] Create automated backup script
- [ ] Run pg_dump for database
- [ ] Verify backup integrity
- [ ] Document full recovery test procedure
