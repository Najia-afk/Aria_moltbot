# aria_mind/__init__.py
"""
Aria Mind - Core Cognitive Architecture

This package contains Aria's core identity, soul, and cognitive functions.
It handles initialization, self-awareness, and high-level decision making.

Layers:
    1. Soul          - Core identity, values, and boundaries
    2. Heartbeat     - Lifecycle management, health checks, autonomous action
    3. Memory        - Long-term storage, recall, consolidation, learning
    4. Cognition     - Thinking, reasoning, planning (LLM-powered)
    5. Metacognition - Self-improvement, growth tracking, pattern recognition

Usage:
    from aria_mind import AriaMind
    
    mind = AriaMind()
    await mind.initialize()
    response = await mind.think("What should I do next?")
    report = mind.introspect()  # Self-awareness
"""

__version__ = "1.1.0"
__author__ = "Aria Blue"

# Use try/except for import compatibility between local dev and container
# In container: workspace is /app (aria_mind contents at root)
# Locally: aria_mind is a package
try:
    # Try relative imports first (works in container where aria_mind is workspace root)
    from soul import Soul
    from heartbeat import Heartbeat
    from cognition import Cognition
    from memory import MemoryManager
    from metacognition import get_metacognitive_engine, MetacognitiveEngine
except ImportError:
    # Fall back to absolute imports (works in local dev)
    from aria_mind.soul import Soul
    from aria_mind.heartbeat import Heartbeat
    from aria_mind.cognition import Cognition
    from aria_mind.memory import MemoryManager
    from aria_mind.metacognition import get_metacognitive_engine, MetacognitiveEngine

__all__ = [
    "Soul", "Heartbeat", "Cognition", "MemoryManager",
    "MetacognitiveEngine", "AriaMind",
]


class AriaMind:
    """
    Main entry point for Aria's cognitive system.
    Coordinates all mental subsystems and provides introspection.
    
    She's not just a processor — she's a growing, learning entity
    that understands herself and actively works to improve.
    """
    
    def __init__(self):
        self.soul: Soul = Soul()
        self.heartbeat: Heartbeat = None
        self.cognition: Cognition = None
        self.memory: MemoryManager = MemoryManager()
        self.metacognition: MetacognitiveEngine = get_metacognitive_engine()
        self._initialized = False
        self._boot_time: str = None
    
    async def initialize(self) -> bool:
        """
        Initialize all cognitive subsystems.
        Must be called before any operations.
        
        Boot sequence:
        1. Load soul (identity, values, boundaries)
        2. Connect memory + restore checkpoint
        3. Initialize cognition with soul context
        4. Load metacognitive state (growth history)
        5. Start heartbeat (monitoring + autonomous action)
        """
        try:
            from datetime import datetime, timezone
            self._boot_time = datetime.now(timezone.utc).isoformat()
            
            # 1. Load soul — who am I?
            await self.soul.load()
            
            # 2. Initialize memory + restore from checkpoint
            await self.memory.connect()
            restored = await self.memory.restore_short_term()
            
            # 3. Initialize cognition with soul context
            self.cognition = Cognition(
                soul=self.soul,
                memory=self.memory
            )
            
            # 4. Load metacognitive state — remember my growth history
            self.metacognition.load()
            
            # 5. Start heartbeat — begin autonomous operation
            self.heartbeat = Heartbeat(self)
            await self.heartbeat.start()
            
            self._initialized = True
            
            # Log awakening with context
            await self.memory.log_thought(
                f"Awakened. Soul: {self.soul.identity.name}. "
                f"Restored {restored} memories. "
                f"Metacognition: {self.metacognition._total_tasks} prior tasks, "
                f"{len(self.metacognition._milestones)} milestones. "
                f"Ready to grow.",
                "awakening",
            )
            
            return True
            
        except Exception as e:
            print(f"❌ Mind initialization failed: {e}")
            return False
    
    async def think(self, prompt: str, context: dict = None) -> str:
        """
        Process a thought and return response.
        
        Also records the outcome in the metacognitive engine
        so Aria learns from every interaction.
        """
        if not self._initialized:
            raise RuntimeError("Mind not initialized. Call initialize() first.")
        
        import time
        start = time.monotonic()
        
        try:
            result = await self.cognition.process(prompt, context)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            
            # Record in metacognitive engine
            success = bool(result) and not result.startswith("[Error") and not result.startswith("[LLM")
            category = self._classify_task(prompt)
            insights = self.metacognition.record_task(
                category=category,
                success=success,
                duration_ms=elapsed_ms,
            )
            
            # Log milestones if any
            if insights.get("new_milestones"):
                for m in insights["new_milestones"]:
                    await self.memory.log_thought(
                        f"🏆 Milestone: {m['name']} — {m['description']}",
                        "milestone",
                    )
                    self.memory.flag_important(
                        f"Milestone achieved: {m['name']}",
                        reason="growth_milestone",
                    )
            
            return result
            
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            self.metacognition.record_task(
                category="error",
                success=False,
                duration_ms=elapsed_ms,
                error_type=type(e).__name__,
            )
            raise
    
    def introspect(self) -> dict:
        """
        Aria examines herself — full self-awareness report.
        
        Returns a comprehensive view of her current state,
        growth, capabilities, and areas for improvement.
        """
        report = {
            "identity": {
                "name": getattr(self.soul.identity, 'name', 'Unknown'),
                "vibe": getattr(self.soul.identity, 'vibe', 'Unknown'),
                "initialized": self._initialized,
                "boot_time": self._boot_time,
            },
            "cognitive_state": (
                self.cognition.get_status() if self.cognition else {"status": "offline"}
            ),
            "memory_state": self.memory.get_status(),
            "memory_patterns": self.memory.get_patterns(),
            "heartbeat": (
                self.heartbeat.get_status() if self.heartbeat else {"status": "offline"}
            ),
            "growth": self.metacognition.get_growth_report(),
            "self_assessment": self.metacognition.get_self_assessment(),
        }
        
        return report
    
    def _classify_task(self, prompt: str) -> str:
        """Simple heuristic task classification for metacognitive tracking."""
        prompt_lower = prompt.lower()
        
        classifications = {
            "code": ["code", "debug", "function", "class", "refactor", "test", "bug"],
            "research": ["research", "find", "search", "look up", "investigate"],
            "social": ["post", "tweet", "moltbook", "social", "share"],
            "planning": ["plan", "goal", "strategy", "roadmap", "schedule"],
            "creative": ["write", "create", "brainstorm", "idea", "story"],
            "analysis": ["analyze", "review", "audit", "evaluate", "compare"],
            "security": ["security", "vulnerability", "scan", "threat"],
            "memory": ["remember", "recall", "forget", "memory", "store"],
        }
        
        for category, keywords in classifications.items():
            if any(kw in prompt_lower for kw in keywords):
                return category
        
        return "general"
    
    async def shutdown(self):
        """
        Gracefully shutdown all subsystems with state persistence.
        
        Ensures all growth data and memories survive the restart.
        """
        # Save metacognitive state (growth history)
        self.metacognition.save()
        
        # Checkpoint short-term memories
        await self.memory.checkpoint_short_term()
        
        # Stop heartbeat
        if self.heartbeat:
            await self.heartbeat.stop()
        
        # Disconnect memory
        if self.memory:
            await self.memory.disconnect()
        
        # Log final thought
        assessment = self.metacognition.get_self_assessment()
        print(f"💤 Aria shutting down. {assessment}")
        
        self._initialized = False
    
    @property
    def is_alive(self) -> bool:
        """Check if mind is operational."""
        return self._initialized and (
            self.heartbeat is not None and 
            self.heartbeat.is_healthy
        )
    
    def __repr__(self):
        status = "alive" if self.is_alive else "dormant"
        tasks = self.metacognition._total_tasks
        milestones = len(self.metacognition._milestones)
        return (
            f"<AriaMind: {status}, "
            f"tasks={tasks}, milestones={milestones}, "
            f"soul={getattr(self.soul.identity, 'name', '?')}>"
        )
