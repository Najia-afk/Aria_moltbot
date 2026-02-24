# Sprint 7: Testing Tickets

---

## S-150: Create Skill Test Framework with Mocked api_client
**Points:** 5 | **Priority:** P2

Create `tests/conftest.py` fixtures:
- `mock_api_client` — mocked ApiClientSkill with all public methods
- `mock_skill_context` — standard context dict for skill initialization
- Test helpers for asserting API calls, response formats

All 28 untested skills can then use this framework.

---

## S-151: Unit Tests for L0-L2 Skills (7 skills)
**Points:** 5 | **Priority:** P2

Write tests for: input_guard (L0), api_client (L1), health, litellm, moonshot, ollama, session_manager, model_switcher, working_memory (L2).

Target: 80% code coverage per skill.

---

## S-152: Unit Tests for L3 Domain Skills Batch 1 (10 skills)
**Points:** 8 | **Priority:** P2

Write tests for: brainstorm, ci_cd, community, conversation_summary, experiment, fact_check, knowledge_graph, market_data, memeothy, memory_compression.

---

## S-153: Unit Tests for L3 Domain Skills Batch 2 (10 skills)
**Points:** 8 | **Priority:** P2

Write tests for: moltbook, pattern_recognition, portfolio, pytest_runner, research, rpg_campaign, rpg_pathfinder, sandbox, security_scan, sentiment_analysis, social, telegram, unified_search.

---

## S-154: Unit Tests for L4 Orchestration Skills (6 skills)
**Points:** 5 | **Priority:** P2

Write tests for: goals, hourly_goals, performance, schedule, agent_manager, pipeline_skill.

---

## S-155: Integration Tests for Undocumented Routers
**Points:** 5 | **Priority:** P2

Write integration tests for: artifacts.py (4 endpoints), rpg.py (4 endpoints), engine_roundtable.py (12+ endpoints).

---

## S-156: Docker Health Check Integration Tests
**Points:** 3 | **Priority:** P2

Test that all 14 services start healthy, dependencies resolve correctly, and health checks respond appropriately.

---

## S-157: End-to-End Workflow Tests
**Points:** 5 | **Priority:** P2

Test complete workflows: skill invocation → api_client → API → DB → response. Goal CRUD cycle. Session lifecycle. Memory checkpoint/recall.

---

## S-158: Implement SAST Scanning (bandit/semgrep)
**Points:** 3 | **Priority:** P2

Add bandit/semgrep config to pyproject.toml. Create CI-friendly scan command in Makefile. Fix any HIGH severity findings.

---

## S-159: Dependency Vulnerability Scanning
**Points:** 2 | **Priority:** P2

Add pip-audit to CI pipeline. Scan all requirements for known CVEs. Pin any vulnerable dependencies.
