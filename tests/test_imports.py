#!/usr/bin/env python3
"""Test that all core modules can be imported in the OpenClaw container."""

def test_imports():
    results = []
    
    # Test security module
    try:
        from security import AriaSecurityGateway, PromptGuard, InputSanitizer, RateLimiter
        results.append("✓ security: OK")
    except Exception as e:
        results.append(f"✗ security: {e}")
    
    # Test soul module
    try:
        from soul import Soul, FocusManager
        results.append("✓ soul: OK")
    except Exception as e:
        results.append(f"✗ soul: {e}")
    
    # Test cognition module
    try:
        from cognition import Cognition, HAS_SECURITY
        results.append(f"✓ cognition: OK (HAS_SECURITY={HAS_SECURITY})")
    except Exception as e:
        results.append(f"✗ cognition: {e}")
    
    # Test memory module
    try:
        from memory import MemoryManager
        results.append("✓ memory: OK")
    except Exception as e:
        results.append(f"✗ memory: {e}")
    
    # Test heartbeat module
    try:
        from heartbeat import Heartbeat
        results.append("✓ heartbeat: OK")
    except Exception as e:
        results.append(f"✗ heartbeat: {e}")
    
    # Test aria_agents
    try:
        from aria_agents.coordinator import AgentCoordinator
        from aria_agents.base import BaseAgent, AgentRole
        results.append("✓ aria_agents: OK")
    except Exception as e:
        results.append(f"✗ aria_agents: {e}")
    
    # Test aria_skills
    try:
        from aria_skills import SkillRegistry
        from aria_skills.database import DatabaseSkill
        results.append("✓ aria_skills: OK")
    except Exception as e:
        results.append(f"✗ aria_skills: {e}")
    
    # Test aria_models
    try:
        from aria_models.loader import get_route_skill, normalize_model_id
        results.append("✓ aria_models: OK")
    except Exception as e:
        results.append(f"✗ aria_models: {e}")
    
    # Print results
    print("\n=== Aria Module Import Test ===\n")
    for r in results:
        print(r)
    print("\n" + "=" * 32)
    
    # Check for failures
    failures = [r for r in results if r.startswith("✗")]
    if failures:
        print(f"\n{len(failures)} module(s) failed to import")
        return False
    else:
        print(f"\nAll {len(results)} modules imported successfully!")
        return True


if __name__ == "__main__":
    import sys
    success = test_imports()
    sys.exit(0 if success else 1)
