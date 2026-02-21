"""
Demo/Test Script for Task-Type-Aware Agent Routing

This script demonstrates the task-type routing system with simulated data.
Run with: python -m aria_memories.knowledge.routing_demo
"""
import json
from datetime import datetime, timezone, timedelta

# Mock the tracker for demo purposes
def _make_record(success, speed, cost, task_type, hours_ago):
    """Helper to create a mock record."""
    return {
        "success": success,
        "speed_score": speed,
        "cost_score": cost,
        "task_type": task_type,
        "created_at": datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    }


class MockPerformanceTracker:
    """Mock tracker with sample data for demonstration."""
    
    def __init__(self):
        base_time = datetime.now(timezone.utc)
        self._records = {
            "analyst": [
                _make_record(True, 0.9, 0.8, "data_analysis", 1),
                _make_record(True, 0.85, 0.8, "data_analysis", 10),
                _make_record(True, 0.88, 0.8, "data_analysis", 20),
                _make_record(False, 0.5, 0.5, "security_scan", 5),
            ],
            "creator": [
                _make_record(True, 0.95, 0.7, "content_creation", 1),
                _make_record(True, 0.92, 0.7, "content_creation", 10),
                _make_record(True, 0.9, 0.7, "content_creation", 20),
                _make_record(False, 0.4, 0.5, "data_analysis", 5),
            ],
            "devops": [
                _make_record(True, 0.9, 0.9, "security_scan", 1),
                _make_record(True, 0.88, 0.9, "security_scan", 10),
                _make_record(True, 0.92, 0.9, "code_review", 15),
                _make_record(True, 0.85, 0.9, "testing", 25),
            ],
        }


def demo_task_classification():
    """Demo: Show task classification in action."""
    print("=" * 70)
    print("DEMO 1: Task Classification")
    print("=" * 70)
    
    from task_type_routing import TaskTypeRouter, TASK_TYPE_PATTERNS
    
    tracker = MockPerformanceTracker()
    router = TaskTypeRouter(tracker)
    
    test_tasks = [
        "Analyze the sales data from last quarter",
        "Write a blog post about AI trends",
        "Scan the codebase for security vulnerabilities",
        "Debug why the API is returning 500 errors",
        "Create a tweet thread about our new feature",
        "Review this pull request for code quality",
        "Refactor the database connection module",
        "Random task with no clear classification",
    ]
    
    print("\nTask -> Classified Type:")
    print("-" * 50)
    for task in test_tasks:
        task_type = router.classify_task(task)
        print(f"  '{task[:45]}...' -> {task_type}")
    
    print(f"\nAvailable task types: {list(TASK_TYPE_PATTERNS.keys())}")


def demo_routing():
    """Demo: Show routing decisions with confidence scores."""
    print("\n" + "=" * 70)
    print("DEMO 2: Task-Type-Aware Routing")
    print("=" * 70)
    
    from task_type_routing import TaskTypeRouter
    
    tracker = MockPerformanceTracker()
    router = TaskTypeRouter(tracker)
    
    candidates = ["analyst", "creator", "devops"]
    
    test_cases = [
        ("Analyze customer churn data", None),
        ("Write a marketing blog post", None),
        ("Scan for CVE vulnerabilities", None),
        ("Review this Python code", "code_review"),
        ("Generic task", "general"),
    ]
    
    print("\nRouting Decisions:")
    print("-" * 70)
    print(f"{'Task':<40} {'Type':<18} {'Agent':<10} {'Conf':<6}")
    print("-" * 70)
    
    for task, task_type in test_cases:
        decision = router.route_task(candidates, task, task_type)
        task_display = task[:38] + ".." if len(task) > 40 else task
        print(f"{task_display:<40} {decision.task_type:<18} {decision.agent_id:<10} {decision.confidence:.2f}")


def demo_specialization_report():
    """Demo: Show specialization learning."""
    print("\n" + "=" * 70)
    print("DEMO 3: Specialization Report")
    print("=" * 70)
    
    from task_type_routing import TaskTypeRouter
    
    tracker = MockPerformanceTracker()
    router = TaskTypeRouter(tracker)
    
    report = router.get_specialization_report()
    
    print("\n📊 Task-Type Experts:")
    print("-" * 50)
    for task_type, expert in report["task_type_experts"].items():
        print(f"  {task_type:<20} -> {expert['agent_id']:<10} (score: {expert['score']})")
    
    print("\n📊 Agent Specializations:")
    print("-" * 50)
    for agent_id, specs in report["agent_specializations"].items():
        print(f"\n  {agent_id}:")
        for task_type, data in specs["top_tasks"]:
            print(f"    - {task_type}: {data['count']} tasks, score {data['score']}")


def demo_comparison():
    """Demo: Compare aggregate vs task-type-aware routing."""
    print("\n" + "=" * 70)
    print("DEMO 4: Aggregate vs Task-Type-Aware Comparison")
    print("=" * 70)
    
    from task_type_routing import TaskTypeRouter, compute_pheromone, COLD_START_SCORE
    
    tracker = MockPerformanceTracker()
    router = TaskTypeRouter(tracker)
    candidates = ["analyst", "creator", "devops"]
    
    task = "Analyze this dataset"
    task_type = "data_analysis"
    
    # Aggregate scores (old way)
    print("\nAggregate Scoring (OLD):")
    print("-" * 50)
    for agent_id in candidates:
        records = tracker._records.get(agent_id, [])
        score = compute_pheromone(records)
        print(f"  {agent_id}: {score:.3f}")
    
    # Task-specific scores (new way)
    print(f"\nTask-Type Scoring for '{task_type}' (NEW):")
    print("-" * 50)
    task_scores = router.get_task_scores(candidates, task_type)
    for agent_id, score in sorted(task_scores.items(), key=lambda x: -x[1]):
        marker = " ⭐ BEST" if score == max(task_scores.values()) else ""
        print(f"  {agent_id}: {score:.3f}{marker}")
    
    # Show the routing decision
    decision = router.route_task(candidates, task, task_type)
    print(f"\n📌 Routing Decision:")
    print(f"   Task: '{task}'")
    print(f"   Type: {decision.task_type}")
    print(f"   Selected Agent: {decision.agent_id}")
    print(f"   Confidence: {decision.confidence:.2f}")
    print(f"   Reason: {decision.reason}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/root/.openclaw/aria_memories/knowledge")
    
    print("\n" + "🐜 " * 20)
    print("  TASK-TYPE-AWARE AGENT ROUTING SYSTEM DEMO")
    print("🐜 " * 20)
    
    try:
        demo_task_classification()
        demo_routing()
        demo_specialization_report()
        demo_comparison()
        
        print("\n" + "=" * 70)
        print("✅ All demos completed successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Review coordinator_integration_patch.py for integration steps")
        print("  2. Apply patches to coordinator.py")
        print("  3. Test with real agent swarm")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
