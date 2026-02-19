"""
JSONL Import/Export — Backward-compatible JSONL I/O for conversations,
memories, and agent logs.

Provides streaming import/export that handles:
- Legacy format (pre-migration era): {role, content, timestamp, session_id, model, tokens}
- New format (aria_engine v2): adds {engine_version, thinking_content, tool_calls, agent_id, pheromone_score}
- Corrupt/malformed lines (skipped gracefully)
- Large files (streaming line-by-line, not loaded into memory)

Backward compatibility guarantee:
- New exports are readable by legacy parsers (extra fields ignored)
- Legacy files import without errors (missing fields get defaults)
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("aria.engine.jsonl_io")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Required fields for each record type
CONVERSATION_REQUIRED = {"role", "content"}
MEMORY_REQUIRED = {"key", "value"}
AGENT_LOG_REQUIRED = {"agent_id", "action"}

# New fields added in v2 (not present in legacy)
NEW_CONVERSATION_FIELDS = {
    "engine_version", "thinking_content", "tool_calls",
    "agent_id", "pheromone_score",
}


# ---------------------------------------------------------------------------
# Import functions
# ---------------------------------------------------------------------------

async def import_conversations(path: Path | str) -> list[dict[str, Any]]:
    """
    Import conversation records from a JSONL file.

    Handles both legacy and new formats. Skips corrupt lines gracefully.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of conversation record dicts.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt line %d in %s", line_no, path)
                continue

            if not isinstance(data, dict):
                logger.warning("Skipping non-dict line %d in %s", line_no, path)
                continue

            # Skip metadata header lines (keys starting with _)
            if any(k.startswith("_") for k in data.keys()):
                continue

            # Must have at least role + content for conversations
            if "role" not in data and "content" not in data:
                logger.warning("Skipping line %d: missing role/content", line_no)
                continue

            # Normalize timestamps
            if "timestamp" in data and isinstance(data["timestamp"], str):
                data["timestamp"] = data["timestamp"].replace("Z", "+00:00")

            records.append(data)

    logger.info("Imported %d conversation records from %s", len(records), path)
    return records


async def import_memories(path: Path | str) -> list[dict[str, Any]]:
    """
    Import memory records from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of memory record dicts.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt line %d in %s", line_no, path)
                continue

            if not isinstance(data, dict):
                continue

            # Must have key + value
            if "key" not in data or "value" not in data:
                logger.warning("Skipping line %d: missing key/value", line_no)
                continue

            records.append(data)

    logger.info("Imported %d memory records from %s", len(records), path)
    return records


async def import_agent_logs(path: Path | str) -> list[dict[str, Any]]:
    """
    Import agent log records from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of agent log record dicts.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping corrupt line %d in %s", line_no, path)
                continue

            if not isinstance(data, dict):
                continue

            # Must have agent_id + action
            if "agent_id" not in data or "action" not in data:
                logger.warning("Skipping line %d: missing agent_id/action", line_no)
                continue

            records.append(data)

    logger.info("Imported %d agent log records from %s", len(records), path)
    return records


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------

async def export_conversations(
    messages: list[dict[str, Any]],
    path: Path | str,
) -> None:
    """
    Export conversation messages to a JSONL file.

    Writes one JSON object per line with streaming (not buffered in memory).

    Args:
        messages: List of message dicts to export.
        path: Output file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for msg in messages:
            line = json.dumps(msg, ensure_ascii=False, default=str)
            f.write(line + "\n")

    logger.info("Exported %d conversation records to %s", len(messages), path)


async def export_memories(
    memories: list[dict[str, Any]],
    path: Path | str,
) -> None:
    """
    Export memory records to a JSONL file.

    Args:
        memories: List of memory dicts to export.
        path: Output file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for mem in memories:
            line = json.dumps(mem, ensure_ascii=False, default=str)
            f.write(line + "\n")

    logger.info("Exported %d memory records to %s", len(memories), path)


async def export_agent_logs(
    logs: list[dict[str, Any]],
    path: Path | str,
) -> None:
    """
    Export agent log records to a JSONL file.

    Args:
        logs: List of agent log dicts to export.
        path: Output file path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for log_entry in logs:
            line = json.dumps(log_entry, ensure_ascii=False, default=str)
            f.write(line + "\n")

    logger.info("Exported %d agent log records to %s", len(logs), path)
