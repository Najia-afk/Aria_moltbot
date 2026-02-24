# Sprint 4-8 Overview — Aria v3 Hardening

**Generated:** 2026-02-24
**Total Tickets:** 55
**Total Estimated:** ~84 hours

---

## Sprint 4: Security Hardening (P0)

| Ticket | Title | Points | Phase |
|--------|-------|--------|-------|
| S-100 | Remove Docker socket mount from aria-api | 3 | 1 |
| S-101 | Add non-root USER to all Dockerfiles | 5 | 1 |
| S-102 | Sandbox isolation (network, read-only, non-root) | 3 | 1 |
| S-103 | Add authentication middleware to FastAPI | 8 | 1 |
| S-104 | Fix sandbox code injection (write_file/read_file) | 3 | 1 |
| S-105 | Fix pytest_runner command injection | 2 | 1 |
| S-106 | Remove hardcoded sk-aria-internal credential | 2 | 1 |
| S-107 | Secure Traefik dashboard (remove --api.insecure) | 2 | 1 |
| S-108 | Remove PostgreSQL port exposure | 1 | 1 |
| S-109 | Restrict CORS origins + set Browserless token | 2 | 1 |

**Sprint 4 Total:** 31 points, ~16 hours

---

## Sprint 5: Architecture Cleanup (P1)

| Ticket | Title | Points | Phase |
|--------|-------|--------|-------|
| S-110 | Delete superseded llm/ skill directory | 1 | 2 |
| S-111 | Delete deprecated database/ skill directory | 1 | 2 |
| S-112 | Create public api_client methods for common operations | 8 | 2 |
| S-113 | Refactor 11 skills to use api_client public methods | 5 | 2 |
| S-114 | Fix model_switcher cross-layer import | 3 | 2 |
| S-115 | Fix conversation_summary to route through litellm skill | 3 | 2 |
| S-116 | Fix input_guard / social / session_manager architecture | 5 | 2 |
| S-117 | Add health checks to 10 missing Docker services | 5 | 2 |
| S-118 | Pin all Docker image versions | 2 | 2 |
| S-119 | Fix deploy script DB credentials | 2 | 2 |
| S-120 | Docker network segmentation | 5 | 2 |
| S-121 | Multi-stage Docker builds + .dockerignore | 3 | 2 |

**Sprint 5 Total:** 43 points, ~20 hours

---

## Sprint 6: Documentation (P2)

| Ticket | Title | Points | Phase |
|--------|-------|--------|-------|
| S-130 | Rewrite STRUCTURE.md (remove ghosts, add missing) | 3 | 3 |
| S-131 | Update API.md and API_ENDPOINT_INVENTORY.md | 3 | 3 |
| S-132 | Rewrite aria_memories/README.md | 1 | 3 |
| S-133 | Fix TEST_COVERAGE_AUDIT false claims | 2 | 3 |
| S-134 | Update aria_mind/SKILLS.md (add 13 skills) | 2 | 3 |
| S-135 | Fix all doc contradictions (10 items) | 3 | 3 |
| S-136 | Create RPG system documentation | 3 | 3 |
| S-137 | Create Analysis/Sentiment system docs | 2 | 3 |
| S-138 | Create CONTRIBUTING.md | 2 | 3 |
| S-139 | Document 22 new dashboard templates | 2 | 3 |
| S-140 | Archive stale AUDIT_REPORT.md | 1 | 3 |
| S-141 | Align architecture layer numbering | 1 | 3 |
| S-142 | Document engine telemetry + tool_registry + swarm | 2 | 3 |
| S-143 | Update DEPLOYMENT.md (14 services, correct ports) | 2 | 3 |
| S-144 | Fix Dict → dict + add @logged_method | 2 | 3 |

**Sprint 6 Total:** 29 points, ~12 hours

---

## Sprint 7: Testing (P2)

| Ticket | Title | Points | Phase |
|--------|-------|--------|-------|
| S-150 | Create skill test framework with mocked api_client | 5 | 4 |
| S-151 | Unit tests for L0-L2 skills (7 skills) | 5 | 4 |
| S-152 | Unit tests for L3 domain skills batch 1 (10 skills) | 8 | 4 |
| S-153 | Unit tests for L3 domain skills batch 2 (10 skills) | 8 | 4 |
| S-154 | Unit tests for L4 orchestration skills (6 skills) | 5 | 4 |
| S-155 | Integration tests for artifacts/rpg/roundtable routers | 5 | 4 |
| S-156 | Docker health check integration tests | 3 | 4 |
| S-157 | End-to-end workflow tests | 5 | 4 |
| S-158 | Implement SAST scanning (bandit/semgrep) | 3 | 4 |
| S-159 | Dependency vulnerability scanning | 2 | 4 |

**Sprint 7 Total:** 49 points, ~24 hours

---

## Sprint 8: Operations & Monitoring (P3)

| Ticket | Title | Points | Phase |
|--------|-------|--------|-------|
| S-160 | Fix Prometheus to scrape aria-engine | 1 | 5 |
| S-161 | Grafana dashboards for all services | 5 | 5 |
| S-162 | Alerting rules for health check failures | 3 | 5 |
| S-163 | Fix KG BFS N+1 queries | 3 | 5 |
| S-164 | Fix roundtable session loading (pagination) | 3 | 5 |
| S-165 | Implement skill latency logging (Aria's goal) | 5 | 5 |
| S-166 | Add persistence to stub skills | 5 | 5 |
| S-167 | Context.json auto-sync + batch operations | 3 | 5 |

**Sprint 8 Total:** 28 points, ~12 hours
