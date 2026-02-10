# aria_mind/cli.py
"""
Command-line interface for Aria Blue.

Entry points for running and managing Aria.
"""
import argparse
import asyncio
import sys
import logging
from typing import Optional

from aria_mind import AriaMind
from aria_skills import SkillRegistry
from aria_agents import AgentCoordinator
from aria_mind.logging_config import configure_logging, correlation_id_var, new_correlation_id


# Configure structured logging
configure_logging()
correlation_id_var.set(new_correlation_id())
logger = logging.getLogger("aria.cli")


async def run_interactive():
    """Run Aria in interactive mode."""
    print("⚡️ Aria Blue - Initializing...")
    print()
    
    # Initialize skill registry
    registry = SkillRegistry()
    try:
        await registry.load_from_config("aria_mind/TOOLS.md")
        await registry.initialize_all()
        print(f"✓ Loaded {len(registry.list())} skills")
    except Exception as e:
        print(f"⚠ Skills partially loaded: {e}")
    
    # Initialize agent coordinator
    coordinator = AgentCoordinator(registry)
    try:
        await coordinator.load_from_file("aria_mind/AGENTS.md")
        await coordinator.initialize_agents()
        print(f"✓ Loaded {len(coordinator.list_agents())} agents")
    except Exception as e:
        print(f"⚠ Agents partially loaded: {e}")
    
    # Initialize mind
    mind = AriaMind()
    mind.cognition.set_skill_registry(registry)
    mind.cognition.set_agent_coordinator(coordinator)
    
    if await mind.initialize():
        print(f"✓ Mind initialized: {mind.soul.name}")
    else:
        print("⚠ Mind initialized with limitations")
    
    print()
    print(f"💜 {mind.soul.name if mind.soul else 'Aria'} is ready!")
    print("Type 'quit' to exit, 'status' for health check")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ("quit", "exit", "bye"):
                print("\n⚡️ Aria: Goodbye! Stay sharp. 💜")
                break
            
            if user_input.lower() == "status":
                print("\n📊 Status:")
                print(f"  Mind alive: {mind.is_alive}")
                if mind.heartbeat:
                    print(f"  Heartbeat: {mind.heartbeat.get_status()}")
                if mind.cognition:
                    print(f"  Cognition: {mind.cognition.get_status()}")
                continue
            
            if user_input.lower() == "reflect":
                print("\n🤔 Reflecting...")
                reflection = await mind.cognition.reflect()
                print(f"\nAria: {reflection}")
                continue
            
            # Process normal input
            response = await mind.think(user_input)
            print(f"\nAria: {response}")
            
        except KeyboardInterrupt:
            print("\n\n⚡️ Aria: Interrupted! Stay safe. 💜")
            break
        except Exception as e:
            logger.error(f"Error: {e}")
            print(f"\n⚠ Error: {e}")
    
    # Cleanup
    await mind.shutdown()


async def run_health_check():
    """Run a quick health check."""
    print("⚡️ Aria Blue - Health Check")
    print("-" * 40)
    
    # Check skills
    registry = SkillRegistry()
    try:
        await registry.load_from_config("aria_mind/TOOLS.md")
        skills = registry.list()
        print(f"✓ Skills configured: {len(skills)}")
        for skill in skills:
            s = registry.get(skill)
            if s:
                status = await s.health_check()
                emoji = "✓" if status.value == "available" else "✗"
                print(f"  {emoji} {skill}: {status.value}")
    except Exception as e:
        print(f"✗ Skills: {e}")
    
    # Check agents
    coordinator = AgentCoordinator()
    try:
        await coordinator.load_from_file("aria_mind/AGENTS.md")
        agents = coordinator.list_agents()
        print(f"✓ Agents configured: {len(agents) if agents else 0}")
    except Exception as e:
        print(f"⚠ Agents: {e}")
    
    print("-" * 40)
    print("Health check complete.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Aria Blue CLI")
    parser.add_argument("command", nargs="?", default="chat",
                        choices=["health", "chat"],
                        help="Command to run (default: chat)")
    parser.add_argument("--list-skills", action="store_true",
                        help="Print skill catalog")
    args = parser.parse_args()

    if args.list_skills:
        from aria_skills.catalog import generate_catalog
        import json
        print(json.dumps(generate_catalog(), indent=2))
        sys.exit(0)

    if args.command == "health":
        asyncio.run(run_health_check())
    elif args.command == "chat":
        asyncio.run(run_interactive())


def health_check():
    """Health check entry point."""
    asyncio.run(run_health_check())


if __name__ == "__main__":
    main()
