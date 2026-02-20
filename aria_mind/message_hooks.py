"""
Message Hook System for OpenClaw Integration.

Provides pre-processor and post-processor hooks for message interception,
enabling context layer loading and response compression.

Middleware pattern: Message → Pre-hook → Process → Post-hook → Output
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger("aria.message_hooks")


@dataclass
class MessageContext:
    """Context passed through the message pipeline."""
    message_id: str
    content: str
    source: str  # 'telegram', 'discord', 'internal', etc.
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    context_layer: Optional[Dict[str, Any]] = None  # Loaded by pre-processor
    compressed: bool = False  # Set by post-processor


@dataclass  
class HookResult:
    """Result from a hook execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    modified_context: Optional[MessageContext] = None


class MessageHook(ABC):
    """Base class for message hooks."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Hook identifier."""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Execution priority (lower = earlier)."""
        pass
    
    @abstractmethod
    async def process(self, context: MessageContext) -> HookResult:
        """Process the message context."""
        pass


class ContextLayerPreprocessor(MessageHook):
    """
    Pre-processor: Load context layer for incoming messages.
    
    Queries working memory and long-term memory to enrich
    the message context before processing.
    """
    
    @property
    def name(self) -> str:
        return "context_layer_preprocessor"
    
    @property
    def priority(self) -> int:
        return 10  # Early in pipeline
    
    async def process(self, context: MessageContext) -> HookResult:
        """Load context layer from memory systems."""
        try:
            # Import here to avoid circular deps
            from aria_mind.memory import MemoryManager
            
            memory = MemoryManager()
            
            # Build context layer
            context_layer = {
                "working_memory": [],
                "relevant_memories": [],
                "session_context": {},
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Get recent working memory
            try:
                working_mem = memory.recall_short(limit=5, sort_by="importance")
                context_layer["working_memory"] = [
                    {"key": m.get("key"), "value": m.get("value")}
                    for m in working_mem
                ]
            except Exception as e:
                logger.debug(f"Working memory load skipped: {e}")
            
            # Search for relevant long-term memories
            try:
                # Use message content to find relevant memories
                search_results = memory.recall_long(
                    query=context.content[:100],  # First 100 chars
                    limit=3
                )
                context_layer["relevant_memories"] = search_results
            except Exception as e:
                logger.debug(f"Long-term memory search skipped: {e}")
            
            # Update context
            context.context_layer = context_layer
            context.metadata["context_loaded"] = True
            
            logger.info(
                f"Context layer loaded for message {context.message_id}",
                extra={
                    "message_id": context.message_id,
                    "working_mem_count": len(context_layer["working_memory"]),
                    "relevant_mem_count": len(context_layer["relevant_memories"]),
                }
            )
            
            return HookResult(
                success=True,
                modified_context=context
            )
            
        except Exception as e:
            logger.error(f"Context layer load failed: {e}")
            # Fail open - message still processes without context
            return HookResult(
                success=True,  # Don't block message
                modified_context=context,
                error=f"Context load failed: {e}"
            )


class CompressionPostprocessor(MessageHook):
    """
    Post-processor: Compress responses to medium size.
    
    Applies intelligent compression to reduce token usage
    while preserving meaning.
    """
    
    @property
    def name(self) -> str:
        return "compression_postprocessor"
    
    @property
    def priority(self) -> int:
        return 20  # Late in pipeline
    
    def __init__(self, max_length: int = 800, compression_threshold: int = 1200):
        self.max_length = max_length
        self.compression_threshold = compression_threshold
    
    async def process(self, context: MessageContext) -> HookResult:
        """Compress response content if needed."""
        content = context.content
        original_length = len(content)
        
        # Skip if already small enough
        if original_length <= self.max_length:
            return HookResult(success=True, modified_context=context)
        
        try:
            compressed = self._compress_content(content)
            context.content = compressed
            context.compressed = True
            context.metadata["compression"] = {
                "original_length": original_length,
                "compressed_length": len(compressed),
                "ratio": round(len(compressed) / original_length, 2) if original_length > 0 else 1.0,
            }
            
            logger.info(
                f"Compressed message {context.message_id}",
                extra={
                    "message_id": context.message_id,
                    "original_length": original_length,
                    "compressed_length": len(compressed),
                }
            )
            
            return HookResult(success=True, modified_context=context)
            
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            return HookResult(
                success=True,
                modified_context=context,
                error=f"Compression failed: {e}"
            )
    
    def _compress_content(self, content: str) -> str:
        """Apply compression strategies."""
        # Strategy 1: Remove redundant whitespace
        compressed = " ".join(content.split())
        
        # Strategy 2: Truncate if still too long
        if len(compressed) > self.max_length:
            compressed = compressed[:self.max_length - 3] + "..."
        
        return compressed


class MessageHookManager:
    """
    Manager for message hook pipeline.
    
    Implements middleware pattern for message processing.
    """
    
    def __init__(self):
        self._pre_hooks: List[MessageHook] = []
        self._post_hooks: List[MessageHook] = []
        self._logger = logging.getLogger("aria.message_hooks.manager")
    
    def register_pre_hook(self, hook: MessageHook) -> None:
        """Register a pre-processing hook."""
        self._pre_hooks.append(hook)
        self._pre_hooks.sort(key=lambda h: h.priority)
        self._logger.info(f"Registered pre-hook: {hook.name}")
    
    def register_post_hook(self, hook: MessageHook) -> None:
        """Register a post-processing hook."""
        self._post_hooks.append(hook)
        self._post_hooks.sort(key=lambda h: h.priority)
        self._logger.info(f"Registered post-hook: {hook.name}")
    
    def unregister_hook(self, name: str) -> bool:
        """Unregister a hook by name."""
        for hook_list in [self._pre_hooks, self._post_hooks]:
            for i, hook in enumerate(hook_list):
                if hook.name == name:
                    hook_list.pop(i)
                    self._logger.info(f"Unregistered hook: {name}")
                    return True
        return False
    
    async def process_incoming(
        self, 
        message_id: str,
        content: str,
        source: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MessageContext:
        """Process incoming message through pre-hooks."""
        context = MessageContext(
            message_id=message_id,
            content=content,
            source=source,
            metadata=metadata or {}
        )
        
        for hook in self._pre_hooks:
            try:
                result = await hook.process(context)
                if result.modified_context:
                    context = result.modified_context
                if not result.success:
                    self._logger.warning(f"Pre-hook {hook.name} failed: {result.error}")
            except Exception as e:
                self._logger.error(f"Pre-hook {hook.name} exception: {e}")
                # Continue processing - don't block on hook failure
        
        return context
    
    async def process_outgoing(self, context: MessageContext) -> MessageContext:
        """Process outgoing message through post-hooks."""
        for hook in self._post_hooks:
            try:
                result = await hook.process(context)
                if result.modified_context:
                    context = result.modified_context
                if not result.success:
                    self._logger.warning(f"Post-hook {hook.name} failed: {result.error}")
            except Exception as e:
                self._logger.error(f"Post-hook {hook.name} exception: {e}")
        
        return context
    
    def get_registered_hooks(self) -> Dict[str, List[str]]:
        """Get list of registered hooks."""
        return {
            "pre_hooks": [h.name for h in self._pre_hooks],
            "post_hooks": [h.name for h in self._post_hooks],
        }


# Singleton instance
_hook_manager: Optional[MessageHookManager] = None


def get_hook_manager() -> MessageHookManager:
    """Get or create the global hook manager."""
    global _hook_manager
    if _hook_manager is None:
        _hook_manager = MessageHookManager()
        # Register default hooks
        _hook_manager.register_pre_hook(ContextLayerPreprocessor())
        _hook_manager.register_post_hook(CompressionPostprocessor())
    return _hook_manager


def reset_hook_manager() -> None:
    """Reset the global hook manager (for testing)."""
    global _hook_manager
    _hook_manager = None