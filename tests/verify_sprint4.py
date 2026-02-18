#!/usr/bin/env python3
"""Verify Sprint 4 implementations in Docker."""
import sys

def verify_s4_01():
    """S4-01: Agent lifecycle management."""
    from aria_engine.agent_pool import AgentPool, EngineAgent
    print("S4-01 Import: OK")

    agent = EngineAgent(agent_id="main", model="qwen3-mlx", display_name="Aria Main")
    s = agent.get_summary()
    assert s["agent_id"] == "main"
    assert s["model"] == "qwen3-mlx"
    assert s["status"] == "idle"
    print(f"S4-01 EngineAgent: OK")

    import asyncio
    pool = AgentPool.__new__(AgentPool)
    pool.config = None
    pool._agents = {}
    pool._skill_registry = None
    pool._llm_gateway = None
    pool._db_engine = None
    pool._concurrency_semaphore = asyncio.Semaphore(5)
    status = pool.get_status()
    assert status["total_agents"] == 0
    assert status["max_concurrent"] == 5
    print(f"S4-01 AgentPool: OK")

def verify_s4_02():
    """S4-02: Session isolation."""
    from aria_engine.session_isolation import AgentSessionScope, SessionIsolationFactory
    print("S4-02 Import: OK")

    factory = SessionIsolationFactory.__new__(SessionIsolationFactory)
    factory._db_engine = None
    factory._config = None
    factory._scopes = {}

    main = factory.for_agent("main")
    talk = factory.for_agent("aria-talk")
    assert main.agent_id == "main"
    assert talk.agent_id == "aria-talk"
    assert factory.for_agent("main") is main
    print(f"S4-02 Factory: OK - main={main.agent_id}, talk={talk.agent_id}")

def verify_s4_03():
    """S4-03: Agent tabs."""
    import os
    assert os.path.exists("src/web/templates/engine_agents.html"), "Template missing"
    print("S4-03 Template: OK")

    from src.api.routers.engine_agents import router
    print(f"S4-03 API Router: OK - {len(router.routes)} routes")

def verify_s4_04():
    """S4-04: Pheromone routing."""
    from aria_engine.routing import EngineRouter, compute_specialty_match, compute_load_score
    print("S4-04 Import: OK")

    # Specialty matching
    devops = compute_specialty_match("Deploy the Docker build", "devops")
    social = compute_specialty_match("Deploy the Docker build", "social")
    creative = compute_specialty_match("Write a blog post about AI", "creative")
    assert devops >= 0.6, f"devops match should be high: {devops}"
    assert social <= 0.2, f"social match should be low: {social}"
    assert creative >= 0.6, f"creative match should be high: {creative}"
    print(f"S4-04 Specialty: OK (devops={devops}, social={social}, creative={creative})")

    # Load scoring
    assert compute_load_score("idle", 0) == 1.0
    assert compute_load_score("busy", 0) == 0.3
    assert compute_load_score("error", 0) == 0.1
    assert compute_load_score("idle", 3) == 0.7
    print("S4-04 Load scoring: OK")

def verify_s4_05():
    """S4-05: Roundtable."""
    from aria_engine.roundtable import Roundtable, RoundtableResult, RoundtableTurn
    print("S4-05 Import: OK")

    rt = Roundtable.__new__(Roundtable)
    p = rt._build_round_prompt("Test topic", 1, "(No prior)", 3)
    assert "EXPLORE" in p
    p2 = rt._build_round_prompt("Test topic", 2, "prior context", 3)
    assert "WORK" in p2
    p3 = rt._build_round_prompt("Test topic", 3, "prior context", 3)
    assert "VALIDATE" in p3
    print("S4-05 Prompts: OK")

    turns = [
        RoundtableTurn("agent-a", 1, "First thought", 100),
        RoundtableTurn("agent-b", 1, "Second thought", 200),
    ]
    ctx = rt._build_context(turns)
    assert "agent-a" in ctx and "agent-b" in ctx
    print("S4-05 Context: OK")

    turns2 = [
        RoundtableTurn("a", 1, "Hello", 100),
        RoundtableTurn("b", 1, "World", 200),
        RoundtableTurn("a", 2, "Updated", 150),
    ]
    s = rt._fallback_synthesis(turns2)
    assert "Auto-synthesis" in s
    print("S4-05 Fallback: OK")

def verify_s4_06():
    """S4-06: Agent dashboard."""
    import os
    assert os.path.exists("src/web/templates/engine_agent_dashboard.html"), "Dashboard template missing"
    print("S4-06 Template: OK")

    from src.api.routers.engine_agent_metrics import router, AgentMetric, AgentMetricsResponse
    print(f"S4-06 API Router: OK - {len(router.routes)} routes")

    m = AgentMetric(
        agent_id="test", display_name="Test Agent", status="idle",
        pheromone_score=0.750, messages_processed=100, total_tokens=5000,
        avg_latency_ms=200, error_count=5, error_rate=0.05,
    )
    assert m.agent_id == "test"
    print("S4-06 Schema: OK")

if __name__ == "__main__":
    ticket = sys.argv[1] if len(sys.argv) > 1 else "all"
    verifiers = {
        "s4-01": verify_s4_01,
        "s4-02": verify_s4_02,
        "s4-03": verify_s4_03,
        "s4-04": verify_s4_04,
        "s4-05": verify_s4_05,
        "s4-06": verify_s4_06,
    }
    if ticket == "all":
        for name, fn in verifiers.items():
            try:
                fn()
                print(f"  ✓ {name} PASSED")
            except Exception as e:
                print(f"  ✗ {name} FAILED: {e}")
    elif ticket in verifiers:
        verifiers[ticket]()
    else:
        print(f"Unknown ticket: {ticket}")
        sys.exit(1)
