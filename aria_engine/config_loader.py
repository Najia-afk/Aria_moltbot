"""
Config loader using stdlib tomllib (Python 3.11+).

Replaces third-party tomli/toml with stdlib tomllib for
reading pyproject.toml and any .toml configuration files.
"""
import logging
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger("aria.engine.config_loader")


def load_toml(path: str | Path) -> dict[str, Any]:
    """
    Load a TOML file using stdlib tomllib.

    Args:
        path: Path to .toml file

    Returns:
        Parsed TOML as dict

    Raises:
        FileNotFoundError: If path doesn't exist
        tomllib.TOMLDecodeError: If TOML is malformed
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"TOML file not found: {path}")

    with open(path, "rb") as f:
        data = tomllib.load(f)

    logger.debug("Loaded TOML config: %s (%d keys)", path.name, len(data))
    return data


def load_pyproject() -> dict[str, Any]:
    """
    Load pyproject.toml from project root.

    Walks up from current file to find pyproject.toml.
    Returns the full parsed config.
    """
    # Search from current file up to root
    search = Path(__file__).resolve().parent
    for _ in range(10):  # max depth
        candidate = search / "pyproject.toml"
        if candidate.exists():
            return load_toml(candidate)
        search = search.parent

    raise FileNotFoundError("pyproject.toml not found in parent directories")


def get_project_version() -> str:
    """Get project version from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("version", "0.0.0")


def get_project_name() -> str:
    """Get project name from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("name", "aria-blue")


def get_python_requirement() -> str:
    """Get requires-python from pyproject.toml."""
    config = load_pyproject()
    return config.get("project", {}).get("requires-python", ">=3.13")


def load_engine_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """
    Load engine-specific TOML config if it exists.

    Looks for `aria_engine.toml` in standard locations:
    1. Explicit path (if provided)
    2. ./aria_engine.toml
    3. ./config/aria_engine.toml
    4. /app/config/aria_engine.toml (Docker)

    Returns empty dict if no config file found (uses env vars as fallback).
    """
    if config_path:
        return load_toml(config_path)

    candidates = [
        Path("aria_engine.toml"),
        Path("config/aria_engine.toml"),
        Path("/app/config/aria_engine.toml"),
    ]

    for candidate in candidates:
        if candidate.exists():
            logger.info("Found engine config: %s", candidate)
            return load_toml(candidate)

    logger.debug("No aria_engine.toml found — using environment variables only")
    return {}
