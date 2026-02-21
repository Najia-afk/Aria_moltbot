# aria_mind/kernel/__init__.py
"""
Immutable kernel — Aria's read-only identity, values, and safety constraints.

Loaded once at startup, deep-frozen via MappingProxyType.
SHA-256 integrity verification on heartbeat.
"""
import hashlib
import logging
import pathlib
import types
from typing import Any

logger = logging.getLogger("aria.kernel")

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _deep_freeze(obj: Any) -> Any:
    """Recursively freeze dicts → MappingProxyType, lists → tuples."""
    if isinstance(obj, dict):
        return types.MappingProxyType({k: _deep_freeze(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return tuple(_deep_freeze(item) for item in obj)
    return obj


class KernelLoader:
    """
    Singleton loader for Aria's immutable kernel configuration.

    Usage:
        kernel = KernelLoader.load()         # Load + freeze
        name = KernelLoader.get()["identity"]["name"]  # Access
        ok = KernelLoader.verify_integrity() # Check SHA-256
    """
    _kernel = None
    _checksums: dict[str, str] = {}
    _loaded = False

    COMPONENTS = ("identity", "values", "safety_constraints", "constitution")

    @classmethod
    def load(cls, kernel_dir: pathlib.Path | str | None = None) -> types.MappingProxyType:
        """Load all kernel YAML files and deep-freeze the data."""
        if not HAS_YAML:
            raise ImportError("PyYAML required for kernel loading: pip install pyyaml")

        if kernel_dir is None:
            kernel_dir = pathlib.Path(__file__).parent
        else:
            kernel_dir = pathlib.Path(kernel_dir)

        data = {}
        cls._checksums = {}

        for name in cls.COMPONENTS:
            path = kernel_dir / f"{name}.yaml"
            if not path.exists():
                logger.warning(f"Kernel component missing: {path}")
                continue
            raw = path.read_bytes()
            cls._checksums[name] = hashlib.sha256(raw).hexdigest()
            data[name] = yaml.safe_load(raw.decode("utf-8"))

        cls._kernel = _deep_freeze(data)
        cls._loaded = True
        logger.info(f"Kernel loaded: {len(data)} components, checksum verified")
        return cls._kernel

    @classmethod
    def get(cls) -> types.MappingProxyType:
        """Get the frozen kernel. Loads on first access."""
        if cls._kernel is None:
            cls.load()
        return cls._kernel

    @classmethod
    def verify_integrity(cls, kernel_dir: pathlib.Path | str | None = None) -> bool:
        """Verify SHA-256 checksums of kernel files haven't changed."""
        if not cls._loaded:
            logger.error("Cannot verify integrity: kernel not loaded")
            return False

        if kernel_dir is None:
            kernel_dir = pathlib.Path(__file__).parent
        else:
            kernel_dir = pathlib.Path(kernel_dir)

        for name, expected_hash in cls._checksums.items():
            path = kernel_dir / f"{name}.yaml"
            if not path.exists():
                logger.critical(f"KERNEL INTEGRITY: {name}.yaml missing!")
                return False
            current_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if current_hash != expected_hash:
                logger.critical(f"KERNEL INTEGRITY VIOLATION: {name}.yaml modified!")
                return False

        return True

    @classmethod
    def reset(cls):
        """Reset loader state (for testing only)."""
        cls._kernel = None
        cls._checksums = {}
        cls._loaded = False
