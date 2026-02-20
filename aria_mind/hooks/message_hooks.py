"""
Message Hooks - OpenClaw Message Interception Middleware

Implements pre-processor and post-processor hooks for message handling:
- Pre-processor: Load context layer before processing
- Post-processor: Compress output to medium
- Middleware pattern for extensibility

Part of: [CM-P4-D24] Implement Message Hook Integration
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol
from dataclasses import dataclass, field
from enum import Enum
import time

logger = logging.getLogger("aria.message_hooks")


class HookType(Enum):
    """Types of message hooks."""
    PRE_PROCESS = "pre_process"    # Before message processing
    POST_PROCESS = "post_process"  # After message processing
    ON_ERROR = "on_error"          # On processing error


@dataclass
class MessageContext:
    """Context passed through hook chain."""
    message: str
    session_key: Optional[str] = None
    user_id: Optional[str] = None
    channel: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    context_loaded: bool = False
    compression_applied: bool = False
    processing_time_ms: float = 0.0
    
    def copy(self) -> "MessageContext":
        """Create a shallow copy of context."""
        return MessageContext(
            message=self.message,
            session_key=self.session_key,
            user_id=self.user_id,
            channel=self.channel,
            metadata=self.metadata.copy(),
            context_loaded=self.context_loaded,
            compression_applied=self.compression_applied,
            processing_time_ms=self.processing_time_ms,
        )


class MessageHook(Protocol):
    """Protocol for message hook implementations."""
    
    hook_type: HookType
    priority: int = 100  # Lower = higher priority
    
    async def process(self, context: MessageContext) -> MessageContext:
        """Process the message context."""
        ...


class ContextLoaderHook:
    """
    Pre-processor hook: Load context layer before processing.
    
    Loads relevant memories, goals, and working context to enrich
    the message with background information.
    """
    
    hook_type = HookType.PRE_PROCESS
    priority = 10  # High priority - load early
    
    def __init__(self, memory_manager=None):
        self.memory = memory_manager
        self._cache: Dict[str, Any] = {}
        
    async def process(self, context: MessageContext) -> MessageContext:
        """Load context layer into message metadata."""
        start_time = time.time()
        
        try:
            # Load recent memories if memory manager available
            if self.memory:
                recent = await self._load_recent_memories(context)
                context.metadata["recent_memories"] = recent
                
            # Load active goals
            goals = await self._load_active_goals(context)
            context.metadata["active_goals"] = goals
            
            # Load user preferences if user_id known
            if context.user_id:
                prefs = await self._load_user_preferences(context)
                context.metadata["user_preferences"] = prefs
            
            context.context_loaded = True
            context.metadata["context_load_time_ms"] = (time.time() - start_time) * 1000
            
            logger.debug(f"Context loaded for session {context.session_key}")
            
        except Exception as e:
            logger.warning(f"Context load failed: {e}")
            # Don't fail the chain - continue without context
            context.metadata["context_load_error"] = str(e)
        
        return context
    
    async def _load_recent_memories(self, context: MessageContext) -> List[Dict]:
        """Load recent relevant memories."""
        # Placeholder - integrate with memory system
        return []
    
    async def _load_active_goals(self, context: MessageContext) -> List[Dict]:
        """Load active goals for context."""
        # Placeholder - integrate with goals system
        return []
    
    async def _load_user_preferences(self, context: MessageContext) -> Dict:
        """Load user-specific preferences."""
        # Placeholder - integrate with user profile
        return {}


class CompressionHook:
    """
    Post-processor hook: Compress output to medium.
    
    Compresses verbose outputs to be more concise while preserving
    key information. Applied selectively based on message length
    and channel constraints.
    """
    
    hook_type = HookType.POST_PROCESS
    priority = 20  # Medium priority
    
    # Compression thresholds
    COMPRESS_THRESHOLD_CHARS = 1000  # Compress if response > this
    TARGET_RATIO = 0.6  # Target 60% of original length
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        
    async def process(self, context: MessageContext) -> MessageContext:
        """Compress message content if needed."""
        message = context.message
        
        # Skip if already short
        if len(message) < self.COMPRESS_THRESHOLD_CHARS:
            return context
        
        # Skip for certain channels that need detail
        if context.channel in ("api", "webhook"):
            return context
        
        try:
            compressed = await self._compress(message)
            context.message = compressed
            context.compression_applied = True
            context.metadata["compression_ratio"] = len(compressed) / len(message)
            context.metadata["original_length"] = len(message)
            context.metadata["compressed_length"] = len(compressed)
            
            logger.debug(f"Compressed message: {len(message)} -> {len(compressed)} chars")
            
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            # Keep original on failure
            context.metadata["compression_error"] = str(e)
        
        return context
    
    async def _compress(self, text: str) -> str:
        """Compress text while preserving key information."""
        # Simple heuristic compression first
        lines = text.split("\n")
        
        # Remove empty lines and excessive whitespace
        compressed_lines = []
        prev_empty = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if not prev_empty:
                    compressed_lines.append("")
                    prev_empty = True
            else:
                compressed_lines.append(stripped)
                prev_empty = False
        
        result = "\n".join(compressed_lines)
        
        # If still too long, use LLM compression if available
        if len(result) > self.COMPRESS_THRESHOLD_CHARS * self.TARGET_RATIO and self.llm:
            result = await self._llm_compress(result)
        
        return result
    
    async def _llm_compress(self, text: str) -> str:
        """Use LLM for intelligent compression."""
        # Placeholder - integrate with LLM
        # For now, truncate with ellipsis
        max_len = int(len(text) * self.TARGET_RATIO)
        return text[:max_len] + "..." if len(text) > max_len else text


class ErrorHandlerHook:
    """
    Error hook: Handle processing errors gracefully.
    
    Catches and formats errors, potentially retrying or
    providing user-friendly error messages.
    """
    
    hook_type = HookType.ON_ERROR
    priority = 5  # Highest priority for errors
    
    async def process(self, context: MessageContext) -> MessageContext:
        """Process error state."""
        error = context.metadata.get("error")
        
        if error:
            logger.error(f"Message processing error: {error}")
            context.metadata["error_handled"] = True
            context.metadata["error_timestamp"] = time.time()
        
        return context


class MessageHookRegistry:
    """
    Registry for message hooks.
    
    Manages hook registration, ordering by priority, and execution.
    """
    
    def __init__(self):
        self._hooks: Dict[HookType, List[MessageHook]] = {
            hook_type: [] for hook_type in HookType
        }
        self.logger = logging.getLogger("aria.message_hooks.registry")
    
    def register(self, hook: MessageHook) -> None:
        """Register a hook."""
        hook_list = self._hooks[hook.hook_type]
        hook_list.append(hook)
        # Sort by priority (lower = higher priority)
        hook_list.sort(key=lambda h: getattr(h, "priority", 100))
        self.logger.info(f"Registered {hook.hook_type.value} hook: {hook.__class__.__name__}")
    
    def unregister(self, hook_class: type) -> bool:
        """Unregister a hook by class."""
        for hook_type, hooks in self._hooks.items():
            for i, hook in enumerate(hooks):
                if isinstance(hook, hook_class):
                    hooks.pop(i)
                    self.logger.info(f"Unregistered {hook_class.__name__}")
                    return True
        return False
    
    async def execute(
        self,
        hook_type: HookType,
        context: MessageContext,
    ) -> MessageContext:
        """Execute all hooks of a given type."""
        hooks = self._hooks.get(hook_type, [])
        
        for hook in hooks:
            try:
                context = await hook.process(context)
            except Exception as e:
                self.logger.error(f"Hook {hook.__class__.__name__} failed: {e}")
                # Continue with other hooks
        
        return context
    
    def get_hooks(self, hook_type: Optional[HookType] = None) -> List[MessageHook]:
        """Get registered hooks, optionally filtered by type."""
        if hook_type:
            return self._hooks.get(hook_type, []).copy()
        return [
            hook for hooks in self._hooks.values() for hook in hooks
        ]


# Global registry instance
_registry: Optional[MessageHookRegistry] = None


def get_hook_registry() -> MessageHookRegistry:
    """Get or create the global hook registry."""
    global _registry
    if _registry is None:
        _registry = MessageHookRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _registry
    _registry = None


# Convenience functions
def register_hook(hook: MessageHook) -> None:
    """Register a hook with the global registry."""
    get_hook_registry().register(hook)


def create_default_hooks(memory_manager=None, llm_client=None) -> List[MessageHook]:
    """Create the default set of message hooks."""
    return [
        ContextLoaderHook(memory_manager),
        CompressionHook(llm_client),
        ErrorHandlerHook(),
    ]


async def process_with_hooks(
    message: str,
    session_key: Optional[str] = None,
    user_id: Optional[str] = None,
    channel: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> MessageContext:
    """
    Process a message through the full hook chain.
    
    Usage:
        context = await process_with_hooks("Hello", session_key="abc123")
        # Process context.message...
        context = await execute_hooks(HookType.POST_PROCESS, context)
    """
    registry = get_hook_registry()
    
    context = MessageContext(
        message=message,
        session_key=session_key,
        user_id=user_id,
        channel=channel,
        metadata=metadata or {},
    )
    
    # Pre-processing
    context = await registry.execute(HookType.PRE_PROCESS, context)
    
    return context
