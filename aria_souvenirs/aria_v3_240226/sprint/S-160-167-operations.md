# Sprint 8: Operations & Monitoring Tickets

---

## S-160: Fix Prometheus to Scrape aria-engine
**Points:** 1 | **Priority:** P3

Add `aria-engine:8081/metrics` as scrape target in `stacks/brain/prometheus.yml`. The engine exposes Prometheus metrics but Prometheus doesn't collect them.

---

## S-161: Grafana Dashboards for All Services
**Points:** 5 | **Priority:** P3

Create dashboards for: API latency/throughput, engine work cycles, skill invocation stats, memory usage trends, token consumption.

---

## S-162: Alerting Rules for Health Check Failures
**Points:** 3 | **Priority:** P3

Configure Prometheus alerting rules for: service down >5min, memory >80%, disk >90%, error rate spike, LiteLLM budget exceeded.

---

## S-163: Fix KG BFS N+1 Queries
**Points:** 3 | **Priority:** P3

Knowledge graph BFS traversal in `src/api/routers/knowledge.py` triggers N+1 DB queries. Use batch loading or recursive CTE.

---

## S-164: Fix Roundtable Session Loading (Pagination)
**Points:** 3 | **Priority:** P3

`engine_roundtable.py` loads all sessions into memory. Add pagination with cursor-based approach.

---

## S-165: Implement Skill Latency Logging (Aria's Goal)
**Points:** 5 | **Priority:** P3

Aria designed this but never implemented: `skill_latency_logs` table, `@log_latency` decorator, apply to api_client/health/agent_manager skills. Complete her 70% goal.

---

## S-166: Add Persistence to Stub Skills
**Points:** 5 | **Priority:** P3

Implement API persistence for: data_pipeline (in-memory → API), portfolio (in-memory → API), brainstorm (in-memory → API), community (in-memory → API). Requires new API endpoints.

---

## S-167: Context.json Auto-Sync + Batch Operations
**Points:** 3 | **Priority:** P3

Fix stale context.json issue: auto-sync on error, conflict detection. Add batch operation capability for bulk API queries (Aria identified needing this for souvenir cleanup).
