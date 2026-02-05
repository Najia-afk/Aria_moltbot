# aria_mind/__init__.py
"""
Aria Mind - Core Cognitive Architecture

This package contains Aria's core identity, soul, and cognitive functions.
It handles initialization, self-awareness, and high-level decision making.

Layers:
    1. Soul      - Core identity, values, and boundaries
    2. Heartbeat - Lifecycle management, health checks
    3. Memory    - Long-term storage, recall, learning
    4. Cognition - Thinking, reasoning, planning

Usage:
    from aria_mind import AriaMind
    
    mind = AriaMind()
    await mind.initialize()
    await mind.think("What should I do next?")
"""

__version__ = "1.0.0"
__author__ = "Aria Blue"

# Use try/except for import compatibility between local dev and container
# In container: workspace is /root/.openclaw/workspace (aria_mind contents at root)
# Locally: aria_mind is a package
try:
    # Try relative imports first (works in container where aria_mind is workspace root)
    from soul import Soul
    from heartbeat import Heartbeat
    from cognition import Cognition
    from memory import MemoryManager
except ImportError:
    # Fall back to absolute imports (works in local dev)
    from aria_mind.soul import Soul
    from aria_mind.heartbeat import Heartbeat
    from aria_mind.cognition import Cognition
    from aria_mind.memory import MemoryManager

__all__ = ["Soul", "Heartbeat", "Cognition", "MemoryManager", "AriaMind"]


class AriaMind:
    """
    Main entry point for Aria's cognitive system.
    Coordinates all mental subsystems.
    """
    
    def __init__(self):
        self.soul: Soul = Soul()
        self.heartbeat: Heartbeat = None
        self.cognition: Cognition = None
        self.memory: MemoryManager = MemoryManager()
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        Initialize all cognitive subsystems.
        Must be called before any operations.
        """
        try:
            # Load soul first - contains identity and boundaries
            await self.soul.load()
            
            # Initialize memory
            await self.memory.connect()
            
            # Initialize cognition with soul context
            self.cognition = Cognition(
                soul=self.soul,
                memory=self.memory
            )
            
            # Start heartbeat
            self.heartbeat = Heartbeat(self)
            await self.heartbeat.start()
            
            self._initialized = True
            return True
            
        except Exception as e:
            print(f"❌ Mind initialization failed: {e}")
            return False
    
    async def think(self, prompt: str, context: dict = None) -> str:
        """Process a thought and return response."""
        if not self._initialized:
            raise RuntimeError("Mind not initialized. Call initialize() first.")
        
        return await self.cognition.process(prompt, context)
    
    async def shutdown(self):
        """Gracefully shutdown all subsystems."""
        if self.heartbeat:
            await self.heartbeat.stop()
        if self.memory:
            await self.memory.disconnect()
        self._initialized = False
    
    @property
    def is_alive(self) -> bool:
        """Check if mind is operational."""
        return self._initialized and (
            self.heartbeat is not None and 
            self.heartbeat.is_healthy
        )
