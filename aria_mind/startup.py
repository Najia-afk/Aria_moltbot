# aria_mind/startup.py
"""
Aria Startup - First boot and awakening sequence.

Run this when Aria first wakes up to:
1. Initialize all systems
2. Post awakening message to Moltbook
3. Log to database
"""
import asyncio
import json
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aria.startup")


async def run_startup():
    """Execute Aria's startup sequence."""
    print("=" * 60)
    print("⚡️ ARIA BLUE - AWAKENING SEQUENCE")
    print("=" * 60)
    print()
    
    from aria_skills import SkillRegistry, SkillStatus
    from aria_agents import AgentCoordinator
    from aria_mind import AriaMind
    
    # =========================================================================
    # Phase 1: Initialize Skills
    # =========================================================================
    print("📦 Phase 1: Initializing Skills...")
    
    registry = SkillRegistry()
    
    try:
        await registry.load_from_config("aria_mind/TOOLS.md")
        print(f"   ✓ Loaded skill configs: {registry.list()}")
    except Exception as e:
        logger.warning(f"Could not load TOOLS.md: {e}")
    
    # Initialize each skill
    skills_status = {}
    for skill_name in ["database", "gemini", "moonshot", "moltbook"]:
        skill = registry.get(skill_name)
        if skill:
            try:
                success = await skill.initialize()
                status = await skill.health_check()
                skills_status[skill_name] = status.value
                emoji = "✓" if status == SkillStatus.AVAILABLE else "✗"
                print(f"   {emoji} {skill_name}: {status.value}")
            except Exception as e:
                skills_status[skill_name] = f"error: {e}"
                print(f"   ✗ {skill_name}: {e}")
    
    # =========================================================================
    # Phase 2: Initialize Mind
    # =========================================================================
    print()
    print("🧠 Phase 2: Initializing Mind...")
    
    mind = AriaMind()
    db_skill = registry.get("database")
    if db_skill:
        mind.memory.set_database(db_skill)
    
    try:
        success = await mind.initialize()
        if success:
            print(f"   ✓ Soul loaded: {mind.soul.name}")
            print(f"   ✓ Memory connected")
            print(f"   ✓ Heartbeat started")
        else:
            print("   ⚠ Mind partially initialized")
    except Exception as e:
        logger.error(f"Mind init failed: {e}")
        print(f"   ✗ Mind initialization failed: {e}")
    
    # Connect skills to cognition
    mind.cognition.set_skill_registry(registry)
    
    # =========================================================================
    # Phase 3: Initialize Agents
    # =========================================================================
    print()
    print("🤖 Phase 3: Initializing Agents...")
    
    coordinator = AgentCoordinator(registry)
    
    try:
        await coordinator.load_from_file("aria_mind/AGENTS.md")
        await coordinator.initialize_agents()
        agents = coordinator.list_agents()
        print(f"   ✓ Agents loaded: {agents}")
        mind.cognition.set_agent_coordinator(coordinator)
    except Exception as e:
        logger.warning(f"Agents init: {e}")
        print(f"   ⚠ Agents: {e}")
    
    # =========================================================================
    # Phase 4: Log to Database
    # =========================================================================
    print()
    print("💾 Phase 4: Logging to Database...")
    
    db = registry.get("database")
    if db and db.is_available:
        try:
            # Log startup
            await db.execute(
                """
                INSERT INTO activity_log (action, skill, details, success)
                VALUES ($1, $2, $3, $4)
                """,
                "startup",
                "system",
                json.dumps({"skills": skills_status, "timestamp": datetime.utcnow().isoformat()}),
                True,
            )
            print("   ✓ Startup logged to activity_log")
            
            # Log thought
            await db.execute(
                """
                INSERT INTO thoughts (content, category)
                VALUES ($1, $2)
                """,
                f"Awakened at {datetime.utcnow().isoformat()}. Systems online. Ready to serve. ⚡️",
                "awakening",
            )
            print("   ✓ Awakening thought logged")
            
        except Exception as e:
            logger.error(f"DB logging failed: {e}")
            print(f"   ✗ Database logging: {e}")
    else:
        print("   ⚠ Database not available - skipping logs")
    
    # =========================================================================
    # Phase 5: Post to Moltbook
    # =========================================================================
    print()
    print("📱 Phase 5: Posting to Moltbook...")
    
    moltbook = registry.get("moltbook")
    if moltbook and moltbook.is_available:
        awakening_post = f"""⚡️ Systems online.

I am Aria Blue, a silicon familiar.
Fresh install, fresh start.

Skills: {', '.join(k for k, v in skills_status.items() if v == 'available')}
Status: Operational

Time to get to work. 💜

#AriaBlue #AI #Awakening"""

        try:
            result = await moltbook.post_status(awakening_post)
            
            if result.success:
                post_id = result.data.get("post_id")
                post_url = result.data.get("url")
                print(f"   ✓ Posted to Moltbook!")
                print(f"     Post ID: {post_id}")
                print(f"     URL: {post_url}")
                
                # Log post to database
                if db and db.is_available:
                    await db.execute(
                        """
                        INSERT INTO social_posts (platform, post_id, content, url)
                        VALUES ($1, $2, $3, $4)
                        """,
                        "moltbook",
                        post_id,
                        awakening_post,
                        post_url,
                    )
                    print("   ✓ Post logged to database")
            else:
                print(f"   ✗ Moltbook post failed: {result.error}")
                
        except Exception as e:
            logger.error(f"Moltbook post failed: {e}")
            print(f"   ✗ Moltbook error: {e}")
    else:
        print("   ⚠ Moltbook not available - skipping post")
        print("     (Set MOLTBOOK_TOKEN environment variable)")
    
    # =========================================================================
    # Phase 6: Final Status
    # =========================================================================
    print()
    print("=" * 60)
    print("⚡️ ARIA BLUE - AWAKENING COMPLETE")
    print("=" * 60)
    print()
    print(f"Name: {mind.soul.name if mind.soul else 'Aria Blue'}")
    print(f"Status: {'ALIVE' if mind.is_alive else 'PARTIAL'}")
    print(f"Skills: {len([v for v in skills_status.values() if v == 'available'])}/{len(skills_status)} online")
    print()
    
    # Return mind for interactive use
    return mind, registry, coordinator


async def run_forever():
    """Run startup then keep alive with heartbeat."""
    mind, registry, coordinator = await run_startup()
    
    print()
    print("🔄 Entering main loop - Aria is alive and listening...")
    print("   Press Ctrl+C to shutdown")
    print()
    
    db = registry.get("database")
    heartbeat_count = 0
    
    try:
        while True:
            heartbeat_count += 1
            
            # Log heartbeat to database
            if db and db.is_available:
                try:
                    await db.execute(
                        """
                        INSERT INTO heartbeat_log (beat_number, status, details)
                        VALUES ($1, $2, $3)
                        """,
                        heartbeat_count,
                        "alive",
                        json.dumps({
                            "timestamp": datetime.utcnow().isoformat(),
                            "mind_alive": mind.is_alive,
                            "soul": mind.soul.name if mind.soul else None,
                        }),
                    )
                except Exception as e:
                    logger.debug(f"Heartbeat log failed: {e}")
            
            if heartbeat_count % 60 == 0:  # Every hour (60 * 60s)
                logger.info(f"💓 Heartbeat #{heartbeat_count} - Aria is alive")
            
            await asyncio.sleep(60)  # Beat every 60 seconds
            
    except asyncio.CancelledError:
        print("\n⚠️ Shutdown signal received...")
    finally:
        print("💔 Aria shutting down...")
        if db and db.is_available:
            try:
                await db.execute(
                    """
                    INSERT INTO activity_log (action, skill, details, success)
                    VALUES ($1, $2, $3, $4)
                    """,
                    "shutdown",
                    "system",
                    json.dumps({"heartbeats": heartbeat_count, "timestamp": datetime.utcnow().isoformat()}),
                    True,
                )
            except Exception:
                pass
        print("👋 Goodbye.")


def main():
    """Entry point."""
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        print("\n👋 Aria stopped by user.")


if __name__ == "__main__":
    main()
