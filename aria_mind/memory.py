# aria_mind/memory.py
"""
Memory Manager - Long-term storage and recall.

Integrates with the database skill for persistent memory.
"""
import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_skills.database import DatabaseSkill


class MemoryManager:
    """
    Aria's memory system.
    
    Handles:
    - Short-term context (in-memory)
    - Long-term storage (database)
    - Memory retrieval and search
    """
    
    def __init__(self, db_skill: Optional["DatabaseSkill"] = None):
        self._db = db_skill
        self._max_short_term = 100
        self._short_term: deque = deque(maxlen=self._max_short_term)
        self._connected = False
        self.logger = logging.getLogger("aria.memory")
    
    def set_database(self, db_skill: "DatabaseSkill"):
        """Inject database skill."""
        self._db = db_skill
    
    async def connect(self) -> bool:
        """Connect to memory storage."""
        if self._db:
            try:
                await self._db.initialize()
                self._connected = self._db.is_available
                return self._connected
            except Exception as e:
                self.logger.error(f"Memory connection failed: {e}")
                return False
        
        # No database - use in-memory only
        self._connected = True
        self.logger.warning("No database - using in-memory storage only")
        return True
    
    async def disconnect(self):
        """Disconnect from storage."""
        if self._db:
            await self._db.close()
        self._connected = False
    
    # -------------------------------------------------------------------------
    # Short-term memory (conversation context)
    # -------------------------------------------------------------------------
    
    def remember_short(self, content: str, category: str = "context"):
        """Add to short-term memory."""
        entry = {
            "content": content,
            "category": category,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._short_term.append(entry)  # deque auto-trims at maxlen
    
    def recall_short(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent short-term memories."""
        return list(self._short_term)[-limit:]
    
    def clear_short(self):
        """Clear short-term memory."""
        self._short_term = []
    
    # -------------------------------------------------------------------------
    # Long-term memory (database)
    # -------------------------------------------------------------------------
    
    async def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
    ) -> bool:
        """Store in long-term memory."""
        if not self._db:
            self.logger.warning("No database for long-term memory")
            return False
        
        result = await self._db.store_memory(key, value, category)
        return result.success
    
    async def recall(self, key: str) -> Optional[Any]:
        """Recall from long-term memory."""
        if not self._db:
            return None
        
        result = await self._db.recall_memory(key)
        if result.success and result.data:
            return result.data.get("value")
        return None
    
    async def search(
        self,
        pattern: str,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search long-term memories."""
        if not self._db:
            return []
        
        result = await self._db.search_memories(pattern, category, limit)
        return result.data if result.success else []
    
    # -------------------------------------------------------------------------
    # Thoughts (internal monologue)
    # -------------------------------------------------------------------------
    
    async def log_thought(
        self,
        content: str,
        category: str = "reflection",
    ) -> bool:
        """Log an internal thought."""
        # Add to short-term
        self.remember_short(content, category)
        
        # Persist if database available
        if self._db:
            result = await self._db.log_thought(content, category)
            return result.success
        
        return True
    
    async def get_recent_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent thoughts."""
        if self._db:
            result = await self._db.get_recent_thoughts(limit)
            return result.data if result.success else []
        
        # Fall back to short-term
        return [
            m for m in self.recall_short(limit)
            if m.get("category") in ("reflection", "thought")
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get memory system status."""
        return {
            "connected": self._connected,
            "has_database": self._db is not None,
            "short_term_count": len(self._short_term),
            "max_short_term": self._max_short_term,
        }
    
    def __repr__(self):
        db_status = "db" if self._db else "memory-only"
        return f"<MemoryManager: {db_status}, {len(self._short_term)} short-term>"
