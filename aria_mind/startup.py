# aria_mind/startup.py
"""
Aria Startup - First boot and awakening sequence.

Run this when Aria first wakes up to:
1. Initialize all systems
2. Post awakening message to Moltbook
3. Log to database
"""
import asyncio
import ast
import json
import logging
import os
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aria.startup")


def _resolve_path(*candidates: str) -> Path | None:
    """Resolve first existing file from candidate paths."""
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return path
    return None


def _verify_markdown_file(path: Path) -> tuple[bool, str]:
    """Check markdown file is readable and non-empty."""
    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return False, "empty file"
        return True, f"{len(content)} chars"
    except Exception as exc:
        return False, str(exc)


def _verify_python_file(path: Path) -> tuple[bool, str]:
    """Check Python file is readable and syntactically valid."""
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        return True, f"{len(source.splitlines())} lines"
    except Exception as exc:
        return False, str(exc)


def review_boot_assets() -> bool:
    """
    Review and validate core Aria docs/scripts before startup.

    Enforces ordered checks so boot fails early if core context is missing
    or syntactically invalid.
    """
    docs_in_order = [
        "BOOTSTRAP.md",
        "SOUL.md",
        "IDENTITY.md",
        "SECURITY.md",
        "MEMORY.md",
        "AGENTS.md",
        "SKILLS.md",
        "TOOLS.md",
        "ORCHESTRATION.md",
    ]
    scripts_in_order = [
        "startup.py",
        "cognition.py",
        "memory.py",
        "security.py",
        "heartbeat.py",
    ]

    print("🧾 Phase 0: Reviewing Core Files...")
    all_ok = True

    for filename in docs_in_order:
        resolved = _resolve_path(f"aria_mind/{filename}", filename)
        if not resolved:
            print(f"   ✗ {filename}: missing")
            all_ok = False
            continue
        ok, detail = _verify_markdown_file(resolved)
        emoji = "✓" if ok else "✗"
        print(f"   {emoji} {filename}: {detail}")
        all_ok = all_ok and ok

    for filename in scripts_in_order:
        resolved = _resolve_path(f"aria_mind/{filename}", filename)
        if not resolved:
            print(f"   ✗ {filename}: missing")
            all_ok = False
            continue
        ok, detail = _verify_python_file(resolved)
        emoji = "✓" if ok else "✗"
        print(f"   {emoji} {filename}: {detail}")
        all_ok = all_ok and ok

    return all_ok


def validate_env():
    """Warn on missing critical environment variables."""
    required = {
        "DB_PASSWORD": "Database will fail to authenticate",
        "LITELLM_MASTER_KEY": "LLM proxy auth will fail",
    }
    recommended = [
        "WEB_SECRET_KEY", "ARIA_API_TOKEN", "BRAVE_API_KEY",
        "CORS_ALLOWED_ORIGINS", "MAC_HOST",
    ]
    for var, impact in required.items():
        val = os.getenv(var, "")
        if not val or val in ("admin", "sk-change-me", "aria-dev-secret-key", "default-aria-api-token"):
            logger.error(f"MISSING/INSECURE REQUIRED: {var} — {impact}")
    for var in recommended:
        if not os.getenv(var):
            logger.warning(f"MISSING RECOMMENDED: {var}")


async def run_startup():
    """Execute Aria's startup sequence."""
    from aria_mind.logging_config import configure_logging, correlation_id_var, new_correlation_id
    configure_logging()
    correlation_id_var.set(new_correlation_id())

    validate_env()

    print("=" * 60)
    print("⚡️ ARIA BLUE - AWAKENING SEQUENCE")
    print("=" * 60)
    print()

    strict_boot_review = os.getenv("ARIA_STRICT_BOOT_REVIEW", "true").lower() == "true"
    reviewed_ok = review_boot_assets()
    if not reviewed_ok:
        message = "Core startup review failed (missing/invalid .md or .py files)"
        if strict_boot_review:
            raise RuntimeError(message)
        logger.warning(message)
        print(f"   ⚠ {message}")
    
    from aria_skills import SkillRegistry, SkillStatus
    from aria_agents import AgentCoordinator
    from aria_mind import AriaMind
    
    # =========================================================================
    # Phase 1: Initialize Skills
    # =========================================================================
    print("📦 Phase 1: Initializing Skills...")
    
    registry = SkillRegistry()
    
    try:
        tools_md = _resolve_path("aria_mind/TOOLS.md", "TOOLS.md")
        if not tools_md:
            raise FileNotFoundError("TOOLS.md not found in aria_mind/ or workspace root")
        await registry.load_from_config(str(tools_md))
        print(f"   ✓ Loaded skill configs: {registry.list()}")
    except Exception as e:
        logger.warning(f"Could not load TOOLS.md: {e}")
    
    # Initialize each skill
    skills_status = {}
    for skill_name in ["database", "litellm", "moltbook"]:
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

    # Save skill catalog for runtime discovery
    try:
        from aria_skills.catalog import save_catalog
        save_catalog()
    except Exception as e:
        logger.debug(f"Skill catalog save failed: {e}")
    
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
    strict_agent_boot = os.getenv("ARIA_STRICT_AGENT_BOOT", "true").lower() == "true"
    expected_agents = [
        part.strip()
        for part in os.getenv(
            "ARIA_EXPECTED_AGENTS",
            "aria,devops,analyst,creator,memory,aria_talk",
        ).split(",")
        if part.strip()
    ]
    
    try:
        agents_md = _resolve_path("aria_mind/AGENTS.md", "AGENTS.md")
        if not agents_md:
            raise FileNotFoundError("AGENTS.md not found in aria_mind/ or workspace root")
        await coordinator.load_from_file(str(agents_md))
        from aria_agents.loader import AgentLoader
        missing = AgentLoader.missing_expected_agents(coordinator._configs, expected_agents)
        if missing:
            raise RuntimeError(
                "Agent config sanity check failed; missing expected agents: "
                + ", ".join(missing)
            )
        await coordinator.initialize_agents()
        agents = coordinator.list_agents()
        print(f"   ✓ Agents loaded: {agents}")
        mind.cognition.set_agent_coordinator(coordinator)
    except Exception as e:
        if strict_agent_boot:
            raise
        logger.warning(f"Agents init: {e}")
        print(f"   ⚠ Agents: {e}")
    
    # =========================================================================
    # Phase 3.5: Restore Working Memory
    # =========================================================================
    print()
    print("🧩 Phase 3.5: Restoring Working Memory...")

    wm_skill = registry.get("working_memory")
    if not wm_skill:
        # Try to instantiate directly if not loaded via TOOLS.md
        try:
            from aria_skills.working_memory import WorkingMemorySkill
            from aria_skills.base import SkillConfig as _SC
            wm_skill = WorkingMemorySkill(_SC(name="working_memory"))
            await wm_skill.initialize()
            registry._skills["working_memory"] = wm_skill
            registry._skills[wm_skill.canonical_name] = wm_skill
        except Exception as e:
            logger.debug(f"Could not init working_memory skill: {e}")

    if wm_skill and wm_skill.is_available:
        try:
            ckpt = await wm_skill.restore_checkpoint()
            if ckpt.success and ckpt.data and ckpt.data.get("count", 0) > 0:
                print(f"   ✓ Restored checkpoint: {ckpt.data['checkpoint_id']} ({ckpt.data['count']} items)")
                # Reflect on restored context
                ref = await wm_skill.reflect()
                if ref.success:
                    print(f"   ✓ Context summary: {ref.data.get('summary', '')[:120]}...")
            else:
                print("   ℹ Fresh start — no previous checkpoint found")
        except Exception as e:
            logger.warning(f"Working memory restore failed: {e}")
            print(f"   ⚠ Working memory: {e}")
    else:
        print("   ⚠ Working memory skill not available — skipping restore")
    
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
                json.dumps({"skills": skills_status, "timestamp": datetime.now(timezone.utc).isoformat()}),
                True,
            )
            print("   ✓ Startup logged to activity_log")
            
            # Log thought
            await db.execute(
                """
                INSERT INTO thoughts (content, category)
                VALUES ($1, $2)
                """,
                f"Awakened at {datetime.now(timezone.utc).isoformat()}. Systems online. Ready to serve. ⚡️",
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
            
            # Heartbeat DB logging now handled by heartbeat.py via api_client
            
            if heartbeat_count % 60 == 0:  # Every hour (60 * 60s)
                logger.info(f"💓 Heartbeat #{heartbeat_count} - Aria is alive")
            
            await asyncio.sleep(60)  # Beat every 60 seconds
            
    except asyncio.CancelledError:
        print("\n⚠️ Shutdown signal received...")
    finally:
        print("💔 Aria shutting down...")
        # Checkpoint working memory before shutdown
        wm = registry.get("working_memory")
        if wm and wm.is_available:
            try:
                ckpt_result = await wm.checkpoint()
                if ckpt_result.success:
                    print(f"   ✓ Working memory checkpointed: {ckpt_result.data.get('checkpoint_id', '?')}")
                else:
                    print(f"   ⚠ Working memory checkpoint failed: {ckpt_result.error}")
            except Exception as e:
                logger.debug(f"WM checkpoint on shutdown failed: {e}")
        # Shutdown logging now handled via api_client
        try:
            from aria_skills.api_client import get_api_client
            api = await get_api_client()
            if api:
                await api.create_activity(
                    action="shutdown",
                    skill="system",
                    details={"heartbeats": heartbeat_count, "timestamp": datetime.now(timezone.utc).isoformat()},
                    success=True,
                )
        except Exception:
            pass
        await mind.shutdown()
        print("👋 Goodbye.")


def main():
    """Entry point."""
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        print("\n👋 Aria stopped by user.")


if __name__ == "__main__":
    main()
