# Future Improvements Roadmap — 2026-02-24

## Vision

Transform Aria from a functional AI agent platform into a production-hardened, secure, well-tested, and fully documented system worthy of enterprise deployment.

---

## Phase 1: Security Hardening (Week 1)

### Docker Security
- [ ] Non-root users in ALL Dockerfiles
- [ ] Replace Docker socket mount with docker-socket-proxy (tecnativa/docker-socket-proxy)
- [ ] Sandbox isolation: --network none, --read-only, non-root, --no-new-privileges
- [ ] Remove --api.insecure=true from Traefik (add basicAuth middleware)
- [ ] Stop exposing PostgreSQL port 5432 to host
- [ ] Restrict CORS origins to actual deployment domains
- [ ] Set Browserless token
- [ ] Pin ALL Docker image versions (eliminate :latest)

### API Security
- [ ] Implement authentication middleware (API key + JWT)
- [ ] Add CSRF protection
- [ ] Rate limiting on all endpoints (not just writes)
- [ ] Audit logging for admin operations
- [ ] Input validation: migrate raw request.json() → Pydantic models

### Skill Security
- [ ] Fix sandbox code injection (shlex.quote or base64)
- [ ] Fix pytest_runner command injection (allowlist, sanitization)
- [ ] Remove hardcoded sk-aria-internal from conversation_summary
- [ ] Set chmod 600 on memeothy credential file
- [ ] Sanitize campaign_id in RPG skills (prevent path traversal)

---

## Phase 2: Architecture Cleanup (Week 2)

### Skill Layer
- [ ] Delete llm/ directory (superseded by moonshot + ollama)
- [ ] Delete database/ directory (deprecated)
- [ ] Create public api_client methods for ALL common operations
- [ ] Refactor 11 skills to stop accessing _client directly
- [ ] Fix model_switcher: remove aria_engine import
- [ ] Fix conversation_summary: route through litellm skill
- [ ] Fix input_guard: route through api_client
- [ ] Fix social: remove fallback httpx clients
- [ ] Add model_switcher to __init__.py

### Docker Architecture
- [ ] Add health checks to 10 missing services
- [ ] Change service_started → service_healthy for dependencies
- [ ] Network segmentation: frontend/backend/data/monitoring
- [ ] Multi-stage builds for all Dockerfiles
- [ ] Add .dockerignore file
- [ ] Fix pip install -e . → pip install . in production
- [ ] Remove tests/ from production image
- [ ] Add Prometheus scrape for aria-engine

### Code Quality
- [ ] Fix Dict → dict in 5 files
- [ ] Add @logged_method() to all public skill methods
- [ ] Implement persistence for data_pipeline and portfolio
- [ ] Add persistence for brainstorm and community
- [ ] Resolve TICKET-12 TODO markers

---

## Phase 3: Documentation (Week 3)

### Tier 1 — Rewrites
- [ ] Rewrite STRUCTURE.md (14 ghost files, 13 missing skills)
- [ ] Rewrite aria_memories/README.md (OpenClaw era → current)
- [ ] Fix TEST_COVERAGE_AUDIT.md (false 100% claim)
- [ ] Archive AUDIT_REPORT.md (references deleted dirs)

### Tier 2 — Updates
- [ ] Update API.md (add 3 routers, fix counts)
- [ ] Update API_ENDPOINT_INVENTORY.md (add 31 endpoints)
- [ ] Update aria_mind/SKILLS.md (add 13 missing skills)
- [ ] Fix CHANGELOG test count contradiction
- [ ] Fix SECURITY.md version date
- [ ] Fix benchmarks.md Python version
- [ ] Align architecture layer numbering (0-4 vs 1-5)

### Tier 3 — New Docs
- [ ] Create RPG system documentation
- [ ] Create Analysis/Sentiment system docs
- [ ] Create CONTRIBUTING.md
- [ ] Document engine telemetry module
- [ ] Document deploy/ directory
- [ ] Document 22 new dashboard templates

---

## Phase 4: Testing (Week 4)

### Unit Tests
- [ ] Create test framework for skill classes (mocked api_client)
- [ ] Write tests for all 28 untested skills
- [ ] Target: 80% skill coverage

### Integration Tests
- [ ] API endpoint integration tests for 3 untested routers
- [ ] Docker health check integration tests
- [ ] End-to-end workflow tests (skill → api → db)

### CI/CD
- [ ] GitHub Actions workflow for PR checks
- [ ] SAST scanning (bandit/semgrep)
- [ ] Dependency vulnerability scanning
- [ ] Container image scanning
- [ ] Automated test runs on push

---

## Phase 5: Operational Excellence (Ongoing)

### Monitoring
- [ ] Fix Prometheus to scrape aria-engine
- [ ] Create Grafana dashboards for all services
- [ ] Alerting rules for health check failures
- [ ] Token usage tracking and budgeting

### Performance
- [ ] Fix KG BFS N+1 queries
- [ ] Fix roundtable session loading (pagination)
- [ ] Implement skill latency logging (Aria's 70% goal)
- [ ] Database query optimization audit

### Aria Capabilities
- [ ] Complete Telegram Bot Integration (Aria's due-tomorrow goal)
- [ ] Knowledge Graph optimization (backfill remaining entities)
- [ ] Moltbook engagement strategy (currently dormant)
- [ ] Session checkpointing for long conversations
- [ ] Batch operation pipeline skill
- [ ] Auto-sync context.json on errors

---

## Sprint Ticket Summary

| Sprint | Focus | Tickets | Est. Hours |
|--------|-------|---------|------------|
| Sprint 4 | Security Hardening | 10 | 16 |
| Sprint 5 | Architecture Cleanup | 12 | 20 |
| Sprint 6 | Documentation | 15 | 12 |
| Sprint 7 | Testing | 10 | 24 |
| Sprint 8 | Operations & Monitoring | 8 | 12 |

**Total:** 55 tickets, ~84 hours estimated
