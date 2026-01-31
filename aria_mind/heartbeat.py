# aria_mind/heartbeat.py
"""
Heartbeat - Lifecycle and health monitoring.

Manages scheduled tasks, health checks, and system status.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_mind import AriaMind


class Heartbeat:
    """
    Aria's heartbeat - keeps her alive and healthy.
    
    Responsibilities:
    - Periodic health checks
    - Scheduled task execution
    - System status reporting
    """
    
    def __init__(self, mind: "AriaMind"):
        self._mind = mind
        self._running = False
        self._last_beat: Optional[datetime] = None
        self._beat_count = 0
        self._interval = 60  # seconds
        self._health_status: Dict[str, Any] = {}
        self.logger = logging.getLogger("aria.heartbeat")
    
    @property
    def is_healthy(self) -> bool:
        """Check if heartbeat is functioning."""
        if not self._running:
            return False
        
        if self._last_beat is None:
            return False
        
        # Unhealthy if no beat in 2x interval
        elapsed = (datetime.utcnow() - self._last_beat).total_seconds()
        return elapsed < (self._interval * 2)
    
    async def start(self):
        """Start the heartbeat loop."""
        if self._running:
            return
        
        self._running = True
        self.logger.info("💓 Heartbeat started")
        
        # Start background task
        asyncio.create_task(self._beat_loop())
    
    async def stop(self):
        """Stop the heartbeat."""
        self._running = False
        self.logger.info("💔 Heartbeat stopped")
    
    async def _beat_loop(self):
        """Main heartbeat loop."""
        while self._running:
            try:
                await self._beat()
            except Exception as e:
                self.logger.error(f"Beat failed: {e}")
            
            await asyncio.sleep(self._interval)
    
    async def _beat(self):
        """Single heartbeat cycle."""
        self._last_beat = datetime.utcnow()
        self._beat_count += 1
        
        # Collect health status
        self._health_status = {
            "timestamp": self._last_beat.isoformat(),
            "beat_number": self._beat_count,
            "soul_loaded": self._mind.soul is not None,
            "memory_connected": self._mind.memory is not None,
            "cognition_ready": self._mind.cognition is not None,
        }
        
        self.logger.debug(f"💓 Beat #{self._beat_count}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "running": self._running,
            "healthy": self.is_healthy,
            "last_beat": self._last_beat.isoformat() if self._last_beat else None,
            "beat_count": self._beat_count,
            "details": self._health_status,
        }
    
    def __repr__(self):
        status = "healthy" if self.is_healthy else "unhealthy"
        return f"<Heartbeat: {status}, beats={self._beat_count}>"
