# Code Review Report — 2026-02-24

## Scope

Full codebase review covering:
- Docker infrastructure (14 services)
- FastAPI backend (31 routers, 226 endpoints)
- 42 skill implementations
- Engine modules (25 files)
- Web dashboard (44 templates)
- Agent framework (6 files)
- Build & deployment pipeline

---

## Architecture Compliance

### 5-Layer Architecture: ✅ Well Enforced

```
Layer 0: Kernel (input_guard)
Layer 1: Gateway (api_client, database[deprecated])
Layer 2: Core (health, litellm, moonshot, ollama, session_manager, model_switcher, working_memory)
Layer 3: Domain (26 skills — brainstorm, ci_cd, community, etc.)
Layer 4: Orchestration (goals, hourly_goals, performance, schedule, agent_manager, pipeline)
```

**Zero direct DB imports in skills or agents.** All 38 active skills use api_client or its _client for API access.

### Violations Found

| # | Type | Count | Severity |
|---|------|-------|----------|
| 1 | Cross-layer imports | 5 | HIGH/MEDIUM |
| 2 | Private member access (_client) | 11 skills | MEDIUM |
| 3 | Direct filesystem I/O | 3 skills | MEDIUM |
| 4 | Independent httpx clients | 4 skills | MEDIUM |
| 5 | Hardcoded credentials | 1 skill | HIGH |

---

## Security Review

### Critical Findings

| # | Location | Issue | CVSS-like |
|---|----------|-------|-----------|
| 1 | Docker: aria-api | Docker socket mount → host control | 9.8 |
| 2 | Docker: all | Root containers → privilege escalation | 8.5 |
| 3 | Docker: sandbox | Arbitrary code exec as root + network | 9.5 |
| 4 | API: all 222 endpoints | Zero authentication | 9.0 |
| 5 | Skill: sandbox write_file | f-string code injection | 8.0 |
| 6 | Skill: pytest_runner | Command injection via unsanitized params | 8.0 |
| 7 | Skill: conversation_summary | Hardcoded API key `sk-aria-internal` | 7.0 |
| 8 | Docker: traefik | Dashboard exposed without auth | 7.0 |
| 9 | Docker: CORS | Wildcard origin on all routes | 6.5 |
| 10 | Docker: postgres | Port 5432 exposed to LAN | 6.5 |

### Positive Security Findings
- SQL injection protection: All DB access through SQLAlchemy ORM ✅
- yaml.safe_load used instead of yaml.load ✅
- .env for secrets (no secrets in code except conversation_summary) ✅
- models.yaml single source of truth enforced ✅

---

## Code Quality

### Good Patterns
- Consistent BaseSkill inheritance across all skills
- SkillRegistry decorator pattern for auto-registration
- skill.json manifests for every skill
- Proper async/await throughout
- Separation of concerns between engine/brain/api/skills

### Problems Found

| Category | Count | Details |
|----------|-------|---------|
| Missing type annotations | 5 files | Dict (capital) without import |
| Dead code | 2 dirs | llm/ and database/ should be deleted |
| In-memory-only skills | 4 | brainstorm, community, data_pipeline, portfolio |
| Missing @logged_method | ~15 skills | No observability on public methods |
| No test coverage | 28 skills | Only API-level tests for ~6 skills |
| Stale TODO markers | 2+ | TICKET-12 references never resolved |

---

## Recent Commits Analysis (Feb 22-24)

12 commits in 3 days — active development:

| Commit | Type | Impact |
|--------|------|--------|
| 86be635 | fix | DB schema bootstrap, ghost sessions, LiteLLM consolidation |
| 3917094 | feat | Session sidebar redesign with time grouping |
| ba9861c, d7dacc1, 5f5cfc0 | fix/feat | RPG dashboard routing and design system |
| d4f6b31 | feat | Sprint 1 "The Crystal Ball" — 4 RPG API endpoints |
| 206c294 | docs | AA+ coding standards |
| 853df5a | plan | 3 final sprints planned with Aria |
| f0f753b | chore | Souvenir deduplication (338 groups → 0, saved 1.8MB) |
| 1eb79eb | feat | Shadows of Absalom campaign files |
| 45f2ab7 | fix | 6 knowledge graph bugs (UUID, signatures, traversal) |

**Pattern:** Heavy feature work (RPG), with some DB/schema fixes and documentation.

---

## Recommendations by Priority

### P0 — Fix Immediately
1. Add authentication middleware to FastAPI app
2. Remove Docker socket mount from aria-api
3. Add non-root USER to all Dockerfiles
4. Sanitize sandbox write_file/read_file (code injection)
5. Sanitize pytest_runner params (command injection)
6. Remove hardcoded sk-aria-internal key

### P1 — Fix This Week
7. Create public api_client methods (eliminate _client access)
8. Fix model_switcher cross-layer import
9. Fix conversation_summary to route through litellm skill
10. Add health checks to 10 missing Docker services
11. Pin all Docker image versions
12. Fix deploy script DB credentials

### P2 — Fix This Sprint
13. Delete llm/ and database/ directories
14. Fix Dict → dict in 5 files
15. Add @logged_method to all public skill methods
16. Add model_switcher to __init__.py
17. Implement persistence for data_pipeline and portfolio
18. Network segmentation in Docker Compose

### P3 — Future Improvements
19. Create comprehensive test suite (target: 80% skill coverage)
20. Multi-stage Docker builds
21. Add .dockerignore
22. GitHub Actions CI/CD pipeline
23. Implement Alembic migrations
24. Add request/response logging middleware
