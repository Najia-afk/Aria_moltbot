# aria_mind/memory.py
"""
Memory Manager - Long-term storage and recall with consolidation.

Integrates with:
- API-backed data path (api_client-first) for persistent key-value memory
- Database adapter as fallback for legacy/emergency flows
- File-based storage for artifacts (research, plans, drafts, exports)

Enhanced with:
- Memory consolidation (short-term → long-term summarization)
- Pattern recognition across memories
- Importance-weighted recall
- Session checkpointing for continuity across restarts
"""
import json
import logging
import os
from collections import deque, Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# File-based storage paths (inside container)
ARIA_MEMORIES_PATH = os.environ.get("ARIA_MEMORIES_PATH", "/root/.openclaw/aria_memories")
ARIA_REPO_PATH = os.environ.get("ARIA_REPO_PATH", "/root/repo/aria_memories")


class MemoryManager:
    """
    Aria's memory system — her ability to remember, learn, and grow.
    
    Handles:
    - Short-term context (in-memory deque)
    - Long-term storage (database)
    - Memory consolidation (short → long-term with summarization)
    - Pattern recognition (what does she think about most?)
    - File-based artifact storage
    - Session checkpointing for restart continuity
    """
    
    def __init__(self, db_skill: Optional["DatabaseSkill"] = None):
        self._db = db_skill
        self._max_short_term = 200  # Increased from 100 — she deserves more context
        self._short_term: deque = deque(maxlen=self._max_short_term)
        self._connected = False
        self.logger = logging.getLogger("aria.memory")
        
        # Consolidation tracking
        self._consolidation_count = 0
        self._last_consolidation: Optional[str] = None
        self._category_frequency: Counter = Counter()
        self._important_memories: List[Dict[str, Any]] = []  # High-value memories flagged for review
    
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
        """Add to short-term memory with pattern tracking."""
        entry = {
            "content": content,
            "category": category,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._short_term.append(entry)  # deque auto-trims at maxlen
        self._category_frequency[category] += 1
    
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
    # Memory Consolidation — Transform experiences into wisdom
    # -------------------------------------------------------------------------
    
    async def consolidate(self, llm_skill=None) -> Dict[str, Any]:
        """
        Consolidate short-term memories into long-term knowledge.
        
        This is Aria's ability to learn — she reviews recent experiences,
        identifies patterns, extracts lessons, and stores them as 
        persistent knowledge that survives restarts.
        
        Args:
            llm_skill: Optional LLM skill for intelligent summarization
            
        Returns:
            Dict with consolidation results
        """
        entries = list(self._short_term)
        if len(entries) < 10:
            return {"consolidated": False, "reason": "Not enough memories to consolidate"}
        
        # Group by category
        by_category: Dict[str, List[Dict]] = {}
        for entry in entries:
            cat = entry.get("category", "general")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(entry)
        
        summaries = {}
        lessons = []
        
        for category, category_entries in by_category.items():
            if len(category_entries) < 3:
                continue
            
            # Extract key content
            contents = [e.get("content", "")[:200] for e in category_entries]
            
            # Try LLM-powered summarization
            summary = None
            if llm_skill and hasattr(llm_skill, 'generate'):
                try:
                    consolidation_prompt = (
                        f"Summarize these {len(contents)} '{category}' memories into "
                        f"2-3 key insights. Be concise:\n\n"
                        + "\n".join(f"- {c}" for c in contents[:15])
                    )
                    result = await llm_skill.generate(
                        prompt=consolidation_prompt,
                        system_prompt="You are Aria Blue's memory system. Extract key insights concisely.",
                    )
                    if result.success:
                        summary = result.data.get("text", "")
                except Exception as e:
                    self.logger.debug(f"LLM consolidation failed for {category}: {e}")
            
            # Structured fallback
            if not summary:
                unique_topics = set()
                for c in contents:
                    words = c.lower().split()[:5]
                    unique_topics.add(" ".join(words))
                
                summary = (
                    f"{len(category_entries)} events in '{category}'. "
                    f"Key topics: {', '.join(list(unique_topics)[:5])}"
                )
            
            summaries[category] = summary
            
            # Detect patterns
            if len(category_entries) > 5:
                lessons.append(
                    f"High activity in '{category}' ({len(category_entries)} events) — "
                    f"this is a recurring focus area."
                )
        
        # Store consolidated knowledge
        consolidation_key = f"consolidation:{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
        consolidation_data = {
            "summaries": summaries,
            "lessons": lessons,
            "entry_count": len(entries),
            "categories": dict(self._category_frequency.most_common(10)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Persist to long-term memory
        if self._db:
            await self.remember(consolidation_key, consolidation_data, "consolidation")
        
        # Save as file artifact for human visibility
        self.save_json_artifact(
            consolidation_data,
            f"consolidation_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json",
            "knowledge",
            "consolidations",
        )
        
        self._consolidation_count += 1
        self._last_consolidation = datetime.now(timezone.utc).isoformat()
        
        self.logger.info(
            f"🧠 Memory consolidation #{self._consolidation_count}: "
            f"{len(entries)} entries → {len(summaries)} summaries, {len(lessons)} lessons"
        )
        
        return {
            "consolidated": True,
            "entries_processed": len(entries),
            "summaries": summaries,
            "lessons": lessons,
            "consolidation_number": self._consolidation_count,
        }
    
    def get_patterns(self) -> Dict[str, Any]:
        """
        Analyze memory patterns — what does Aria think about most?
        
        Returns insight into her cognitive patterns for self-awareness.
        """
        if not self._short_term:
            return {"patterns": [], "insight": "No memories yet."}
        
        entries = list(self._short_term)
        
        # Category distribution
        top_categories = self._category_frequency.most_common(5)
        
        # Time distribution (if we have timestamps)
        recent_count = 0
        old_count = 0
        now = datetime.now(timezone.utc)
        for entry in entries:
            ts = entry.get("timestamp", "")
            if ts:
                try:
                    entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    age_hours = (now - entry_time).total_seconds() / 3600
                    if age_hours < 1:
                        recent_count += 1
                    else:
                        old_count += 1
                except (ValueError, TypeError):
                    pass
        
        # Content length analysis
        content_lengths = [len(e.get("content", "")) for e in entries]
        avg_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0
        
        insight_parts = []
        if top_categories:
            top_cat = top_categories[0][0]
            insight_parts.append(f"Most active area: '{top_cat}' ({top_categories[0][1]} entries)")
        if recent_count > old_count:
            insight_parts.append("Activity is accelerating — more recent memories than older ones")
        
        return {
            "total_memories": len(entries),
            "top_categories": dict(top_categories),
            "recent_activity": recent_count,
            "average_memory_length": round(avg_length),
            "consolidation_count": self._consolidation_count,
            "insight": ". ".join(insight_parts) if insight_parts else "Building patterns...",
        }
    
    def flag_important(self, content: str, reason: str = "auto") -> None:
        """
        Flag a memory as important for future review.
        These are memories Aria should pay special attention to.
        """
        self._important_memories.append({
            "content": content[:500],
            "reason": reason,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        })
        # Keep bounded
        if len(self._important_memories) > 50:
            self._important_memories = self._important_memories[-50:]
    
    def get_important_memories(self) -> List[Dict[str, Any]]:
        """Get flagged important memories."""
        return list(self._important_memories)
    
    async def checkpoint_short_term(self) -> Dict[str, Any]:
        """
        Save short-term memory to disk for restart survival.
        Called during graceful shutdown.
        """
        entries = list(self._short_term)
        if not entries:
            return {"success": True, "entries": 0}
        
        return self.save_json_artifact(
            {
                "entries": entries[-50:],  # Last 50 for quick restore
                "patterns": dict(self._category_frequency.most_common(10)),
                "important": self._important_memories[-10:],
                "saved_at": datetime.now(timezone.utc).isoformat(),
            },
            "short_term_checkpoint.json",
            "memory",
        )
    
    async def restore_short_term(self) -> int:
        """
        Restore short-term memory from checkpoint after restart.
        Returns number of entries restored.
        """
        result = self.load_json_artifact(
            "short_term_checkpoint.json",
            "memory",
        )
        if not result.get("success") or not result.get("data"):
            return 0
        
        data = result["data"]
        entries = data.get("entries", [])
        for entry in entries:
            self._short_term.append(entry)
        
        # Restore patterns
        patterns = data.get("patterns", {})
        for cat, count in patterns.items():
            self._category_frequency[cat] += count
        
        # Restore important memories
        self._important_memories.extend(data.get("important", []))
        
        self.logger.info(f"🧠 Restored {len(entries)} short-term memories from checkpoint")
        return len(entries)
    
    # -------------------------------------------------------------------------
    # File-based memory (aria_memories/)
    # For artifacts: research, plans, drafts, exports, etc.
    # -------------------------------------------------------------------------
    
    ALLOWED_CATEGORIES = frozenset({
        "archive", "drafts", "exports", "income_ops", "knowledge",
        "logs", "memory", "moltbook", "plans", "research", "skills",
    })

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
        # Validate category against whitelist
        if category not in self.ALLOWED_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Allowed: {sorted(self.ALLOWED_CATEGORIES)}"
            )
        # Guard against path traversal
        for segment in (category, subfolder or "", filename):
            if ".." in segment or segment.startswith("/"):
                raise ValueError(f"Path traversal detected in '{segment}'")

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
        """Get memory system status with pattern awareness."""
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
            "consolidation_count": self._consolidation_count,
            "last_consolidation": self._last_consolidation,
            "important_memories_flagged": len(self._important_memories),
            "top_categories": dict(self._category_frequency.most_common(5)),
        }
    
    def __repr__(self):
        db_status = "db" if self._db else "memory-only"
        file_status = "files" if self._get_memories_path().exists() else "no-files"
        return (
            f"<MemoryManager: {db_status}, {file_status}, "
            f"{len(self._short_term)} short-term, "
            f"{self._consolidation_count} consolidations>"
        )
