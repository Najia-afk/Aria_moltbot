"""
Hooks module - OpenClaw message interception and middleware.

This module provides pre-processor and post-processor hooks for
message handling, enabling context loading and output compression.

Part of: [CM-P4-D24] Implement Message Hook Integration
"""
from hooks.message_hooks import (
    # Core types
    HookType,
    MessageContext,
    MessageHook,
    MessageHookRegistry,
    
    # Hook implementations
    ContextLoaderHook,
    CompressionHook,
    ErrorHandlerHook,
    
    # Utilities
    get_hook_registry,
    register_hook,
    create_default_hooks,
    process_with_hooks,
    reset_registry,
)

__all__ = [
    "HookType",
    "MessageContext",
    "MessageHook",
    "MessageHookRegistry",
    "ContextLoaderHook",
    "CompressionHook",
    "ErrorHandlerHook",
    "get_hook_registry",
    "register_hook",
    "create_default_hooks",
    "process_with_hooks",
    "reset_registry",
]
