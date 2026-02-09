# aria_mind/memory.py
"""
Memory Manager - Long-term storage and recall.

Integrates with:
- Database skill for persistent key-value memory
- File-based storage for artifacts (research, plans, drafts, exports)
"""
import json
import logging
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from aria_skills.database import DatabaseSkill

# File-based storage paths (inside container)
ARIA_MEMORIES_PATH = os.environ.get("ARIA_MEMORIES_PATH", "/root/.openclaw/aria_memories")
ARIA_REPO_PATH = os.environ.get("ARIA_REPO_PATH", "/root/repo/aria_memories")


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
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._short_term.append(entry)  # deque auto-trims at maxlen
    
    def recall_short(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent short-term memories."""
        return list(self._short_term)[-limit:]
    
    def clear_short(self):
        """Clear short-term memory."""
        self._short_term.clear()
    
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
    
    # -------------------------------------------------------------------------
    # File-based memory (aria_memories/)
    # For artifacts: research, plans, drafts, exports, etc.
    # -------------------------------------------------------------------------
    
    def _get_memories_path(self) -> Path:
        """Get the aria_memories base path."""
        # Try dedicated mount first
        if Path(ARIA_MEMORIES_PATH).exists():
            return Path(ARIA_MEMORIES_PATH)
        # Fall back to repo mount
        if Path(ARIA_REPO_PATH).exists():
            return Path(ARIA_REPO_PATH)
        # Local development
        local = Path(__file__).parent.parent / "aria_memories"
        if local.exists():
            return local
        return Path(ARIA_MEMORIES_PATH)  # Default, may not exist
    
    def save_artifact(
        self,
        content: str,
        filename: str,
        category: str = "general",
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save a file artifact to aria_memories.
        
        Args:
            content: File content to write
            filename: Name of the file (e.g., "research_report.md")
            category: Folder category (logs, research, plans, drafts, exports)
            subfolder: Optional subfolder within category
        
        Returns:
            Dict with success status and file path
        """
        base = self._get_memories_path()
        
        # Build path: aria_memories/<category>/<subfolder>/<filename>
        folder = base / category
        if subfolder:
            folder = folder / subfolder
        
        try:
            folder.mkdir(parents=True, exist_ok=True)
            filepath = folder / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            self.logger.info(f"Saved artifact: {filepath}")
            return {
                "success": True,
                "path": str(filepath),
                "relative": f"aria_memories/{category}/{subfolder}/{filename}" if subfolder else f"aria_memories/{category}/{filename}",
            }
        except Exception as e:
            self.logger.error(f"Failed to save artifact: {e}")
            return {"success": False, "error": str(e)}
    
    def load_artifact(
        self,
        filename: str,
        category: str = "general",
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Load a file artifact from aria_memories.
        
        Returns:
            Dict with success status and content
        """
        base = self._get_memories_path()
        
        folder = base / category
        if subfolder:
            folder = folder / subfolder
        
        filepath = folder / filename
        
        try:
            if not filepath.exists():
                return {"success": False, "error": f"File not found: {filepath}"}
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            return {"success": True, "content": content, "path": str(filepath)}
        except Exception as e:
            self.logger.error(f"Failed to load artifact: {e}")
            return {"success": False, "error": str(e)}
    
    def list_artifacts(
        self,
        category: str = "general",
        subfolder: Optional[str] = None,
        pattern: str = "*",
    ) -> List[Dict[str, Any]]:
        """
        List artifacts in a category folder.
        
        Returns:
            List of file info dicts
        """
        base = self._get_memories_path()
        
        folder = base / category
        if subfolder:
            folder = folder / subfolder
        
        if not folder.exists():
            return []
        
        files = []
        for f in folder.glob(pattern):
            if f.is_file():
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "path": str(f),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
        
        return sorted(files, key=lambda x: x["modified"], reverse=True)
    
    def save_json_artifact(
        self,
        data: Any,
        filename: str,
        category: str = "exports",
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save structured data as JSON."""
        content = json.dumps(data, indent=2, default=str)
        if not filename.endswith(".json"):
            filename += ".json"
        return self.save_artifact(content, filename, category, subfolder)
    
    def load_json_artifact(
        self,
        filename: str,
        category: str = "exports",
        subfolder: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load JSON artifact."""
        result = self.load_artifact(filename, category, subfolder)
        if result.get("success") and result.get("content"):
            try:
                result["data"] = json.loads(result["content"])
            except json.JSONDecodeError as e:
                result["success"] = False
                result["error"] = f"Invalid JSON: {e}"
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get memory system status."""
        memories_path = self._get_memories_path()
        return {
            "connected": self._connected,
            "has_database": self._db is not None,
            "short_term_count": len(self._short_term),
            "max_short_term": self._max_short_term,
            "file_storage": {
                "path": str(memories_path),
                "available": memories_path.exists(),
            },
        }
    
    def __repr__(self):
        db_status = "db" if self._db else "memory-only"
        file_status = "files" if self._get_memories_path().exists() else "no-files"
        return f"<MemoryManager: {db_status}, {file_status}, {len(self._short_term)} short-term>"
