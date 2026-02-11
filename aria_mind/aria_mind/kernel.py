"""Immutable kernel — Aria's core identity, values, and safety constraints.

The kernel is loaded once at startup, frozen to prevent modification,
and verified via SHA-256 checksums. Any tampering is detected immediately.
"""
import hashlib
import types
from pathlib import Path
from typing import Any

import yaml


# Singleton state
_loaded: bool = False
_kernel: dict[str, Any] | None = None
_checksums: dict[str, str] = {}


def _deep_freeze(obj: Any) -> Any:
    """Recursively freeze mutable containers into immutable equivalents.
    
    - dict → MappingProxyType
    - list → tuple
    - scalars pass through unchanged
    """
    if isinstance(obj, dict):
        return types.MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


def _compute_checksum(path: Path) -> str:
    """Compute SHA-256 checksum of file contents."""
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest()


class KernelLoader:
    """Loads and manages the immutable kernel."""
    
    @staticmethod
    def load(kernel_dir: Path | None = None) -> types.MappingProxyType:
        """Load kernel from YAML files and freeze them.
        
        Args:
            kernel_dir: Directory containing kernel YAML files.
                       Defaults to aria_mind/kernel/ relative to this file.
        
        Returns:
            Frozen MappingProxyType containing all kernel components.
        """
        global _loaded, _kernel, _checksums
        
        if _loaded and _kernel is not None:
            return _deep_freeze(_kernel)
        
        if kernel_dir is None:
            kernel_dir = Path(__file__).parent / "kernel"
        
        components = ["identity", "values", "safety_constraints", "constitution"]
        _kernel = {}
        _checksums = {}
        
        for name in components:
            path = kernel_dir / f"{name}.yaml"
            if path.exists():
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                _kernel[name] = data
                _checksums[name] = _compute_checksum(path)
            else:
                # Log missing but don't crash — partial kernel is better than no kernel
                print(f"[kernel] Warning: Missing component {name}.yaml")
        
        _loaded = True
        return _deep_freeze(_kernel)
    
    @staticmethod
    def get() -> types.MappingProxyType | None:
        """Get the loaded kernel (auto-loads if needed from default path)."""
        global _loaded, _kernel
        if not _loaded or _kernel is None:
            return KernelLoader.load()
        return _deep_freeze(_kernel)
    
    @staticmethod
    def verify_integrity(kernel_dir: Path | None = None) -> bool:
        """Verify kernel files haven't been modified since loading.
        
        Returns True if all checksums match, False if any file was modified
        or if the kernel hasn't been loaded yet.
        """
        global _loaded, _checksums
        
        if not _loaded or _checksums is None:
            return False
        
        if kernel_dir is None:
            kernel_dir = Path(__file__).parent / "kernel"
        
        for name, expected_hash in _checksums.items():
            path = kernel_dir / f"{name}.yaml"
            if not path.exists():
                return False
            current_hash = _compute_checksum(path)
            if current_hash != expected_hash:
                return False
        
        return True
    
    @staticmethod
    def reset() -> None:
        """Reset loader state (primarily for testing)."""
        global _loaded, _kernel, _checksums
        _loaded = False
        _kernel = None
        _checksums = {}
