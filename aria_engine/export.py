"""
Session Export — JSONL and Markdown transcript export from PostgreSQL.

On-demand JSONL/Markdown transcript
export from the aria_engine session tables.

Formats:
- JSONL: OpenAI-compatible, one JSON object per line
- Markdown: Human-readable conversation transcript

Output:
- Files saved to aria_memories/exports/{agent_id}/{session_id}.{format}
- Also available as API response (streaming download)
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aria_engine.config import EngineConfig
from aria_engine.exceptions import SessionError

logger = logging.getLogger("aria.engine.export")


async def export_session_jsonl(
    session_id: str,
    db_session_factory,
    config: EngineConfig,
    save_to_disk: bool = True,
) -> str:
    """
    Export a session's messages as JSONL (one JSON object per line).

    Each line:
    {
        "role": "user|assistant|system|tool",
        "content": "...",
        "thinking": "..." or null,
        "timestamp": "2026-02-18T12:00:00+00:00",
        "model": "qwen3-30b-mlx" or null,
        "tokens": {"input": 100, "output": 50} or null,
        "tool_calls": [...] or null,
        "tool_results": [...] or null
    }

    Args:
        session_id: UUID string of the session.
        db_session_factory: Async sessionmaker.
        config: EngineConfig instance.
        save_to_disk: Whether to write the file to aria_memories/exports/.

    Returns:
        JSONL string (full content).

    Raises:
        SessionError: If session not found.
    """
    import uuid
    from sqlalchemy import select
    from db.models import EngineChatSession, EngineChatMessage

    sid = uuid.UUID(session_id)

    async with db_session_factory() as db:
        # Verify session exists
        sess_result = await db.execute(
            select(EngineChatSession).where(EngineChatSession.id == sid)
        )
        session = sess_result.scalar_one_or_none()
        if session is None:
            raise SessionError(f"Session {session_id} not found")

        # Load all messages ordered by time
        msg_result = await db.execute(
            select(EngineChatMessage)
            .where(EngineChatMessage.session_id == sid)
            .order_by(EngineChatMessage.created_at.asc())
        )
        messages = msg_result.scalars().all()

    # Build JSONL lines
    lines: list[str] = []

    # Header comment (metadata about the session)
    header = {
        "_session_id": str(session.id),
        "_agent_id": session.agent_id,
        "_title": session.title,
        "_model": session.model,
        "_session_type": session.session_type,
        "_status": session.status,
        "_message_count": session.message_count,
        "_total_tokens": session.total_tokens,
        "_total_cost": float(session.total_cost or 0),
        "_created_at": session.created_at.isoformat() if session.created_at else None,
        "_ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "_exported_at": datetime.now(timezone.utc).isoformat(),
    }
    lines.append(json.dumps(header, ensure_ascii=False))

    for msg in messages:
        line: dict[str, Any] = {
            "role": msg.role,
            "content": msg.content,
            "thinking": msg.thinking,
            "timestamp": msg.created_at.isoformat() if msg.created_at else None,
            "model": msg.model,
            "tokens": None,
            "tool_calls": msg.tool_calls,
            "tool_results": msg.tool_results,
        }

        if msg.tokens_input is not None or msg.tokens_output is not None:
            line["tokens"] = {
                "input": msg.tokens_input or 0,
                "output": msg.tokens_output or 0,
            }

        if msg.cost is not None:
            line["cost"] = float(msg.cost)

        if msg.latency_ms is not None:
            line["latency_ms"] = msg.latency_ms

        lines.append(json.dumps(line, ensure_ascii=False))

    jsonl_content = "\n".join(lines) + "\n"

    # Save to disk if requested
    if save_to_disk:
        agent_id = session.agent_id or "main"
        export_dir = Path(config.memories_path) / "exports" / agent_id
        export_dir.mkdir(parents=True, exist_ok=True)

        export_path = export_dir / f"{session_id}.jsonl"
        export_path.write_text(jsonl_content, encoding="utf-8")

        logger.info(
            "Exported session %s to %s (%d messages, %d bytes)",
            session_id, export_path, len(messages), len(jsonl_content),
        )

    return jsonl_content


async def export_session_markdown(
    session_id: str,
    db_session_factory,
    config: EngineConfig,
    save_to_disk: bool = True,
) -> str:
    """
    Export a session as a human-readable Markdown transcript.

    Args:
        session_id: UUID string of the session.
        db_session_factory: Async sessionmaker.
        config: EngineConfig instance.
        save_to_disk: Whether to write the file to aria_memories/exports/.

    Returns:
        Markdown string.
    """
    import uuid
    from sqlalchemy import select
    from db.models import EngineChatSession, EngineChatMessage

    sid = uuid.UUID(session_id)

    async with db_session_factory() as db:
        sess_result = await db.execute(
            select(EngineChatSession).where(EngineChatSession.id == sid)
        )
        session = sess_result.scalar_one_or_none()
        if session is None:
            raise SessionError(f"Session {session_id} not found")

        msg_result = await db.execute(
            select(EngineChatMessage)
            .where(EngineChatMessage.session_id == sid)
            .order_by(EngineChatMessage.created_at.asc())
        )
        messages = msg_result.scalars().all()

    # Build Markdown
    parts: list[str] = []

    # Header
    title = session.title or "Untitled Session"
    created = session.created_at.strftime("%Y-%m-%d %H:%M UTC") if session.created_at else "Unknown"
    parts.append(f"# Chat Session: {title}")
    parts.append(
        f"**Agent:** {session.agent_id} | "
        f"**Model:** {session.model} | "
        f"**Date:** {created} | "
        f"**Status:** {session.status}"
    )
    parts.append("")
    parts.append("---")
    parts.append("")

    # Messages
    role_labels = {
        "user": "User",
        "assistant": "Assistant",
        "system": "System",
        "tool": "Tool",
    }

    for msg in messages:
        label = role_labels.get(msg.role, msg.role.capitalize())
        timestamp = msg.created_at.strftime("%H:%M:%S") if msg.created_at else ""

        parts.append(f"**{label}** ({timestamp}):")
        parts.append("")

        # Content
        if msg.content:
            parts.append(msg.content)
            parts.append("")

        # Thinking (collapsible)
        if msg.thinking:
            parts.append("<details>")
            parts.append("<summary>Thinking</summary>")
            parts.append("")
            parts.append(msg.thinking)
            parts.append("")
            parts.append("</details>")
            parts.append("")

        # Tool calls
        if msg.tool_calls:
            parts.append("**Tool Calls:**")
            for tc in msg.tool_calls:
                func = tc.get("function", {})
                parts.append(f"- `{func.get('name', '?')}({func.get('arguments', '')})`")
            parts.append("")

        # Tool results
        if msg.role == "tool" and msg.tool_results:
            tool_name = msg.tool_results.get("name", "")
            if tool_name:
                parts.append(f"*Result from `{tool_name}`*")
                parts.append("")

        # Token info
        if msg.tokens_input or msg.tokens_output:
            tokens_in = msg.tokens_input or 0
            tokens_out = msg.tokens_output or 0
            cost_str = f" | ${float(msg.cost):.6f}" if msg.cost else ""
            parts.append(
                f"*Tokens: {tokens_in} in / {tokens_out} out{cost_str}*"
            )
            parts.append("")

        parts.append("---")
        parts.append("")

    # Footer stats
    total_tokens = session.total_tokens or 0
    total_cost = float(session.total_cost or 0)
    msg_count = session.message_count or len(messages)
    ended = session.ended_at.strftime("%Y-%m-%d %H:%M UTC") if session.ended_at else "Active"

    parts.append(
        f"**Session Stats:** {msg_count} messages | "
        f"{total_tokens:,} tokens | "
        f"${total_cost:.4f} | "
        f"Ended: {ended}"
    )
    parts.append("")
    parts.append(f"*Exported at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    md_content = "\n".join(parts)

    # Save to disk if requested
    if save_to_disk:
        agent_id = session.agent_id or "main"
        export_dir = Path(config.memories_path) / "exports" / agent_id
        export_dir.mkdir(parents=True, exist_ok=True)

        export_path = export_dir / f"{session_id}.md"
        export_path.write_text(md_content, encoding="utf-8")

        logger.info(
            "Exported session %s to %s (markdown, %d messages)",
            session_id, export_path, len(messages),
        )

    return md_content


async def export_session(
    session_id: str,
    db_session_factory,
    config: EngineConfig,
    format: str = "jsonl",
    save_to_disk: bool = True,
) -> str:
    """
    Export a session in the requested format.

    Args:
        session_id: UUID string.
        db_session_factory: Async sessionmaker.
        config: EngineConfig.
        format: 'jsonl' or 'markdown'.
        save_to_disk: Whether to save to aria_memories/exports/.

    Returns:
        Export content as string.
    """
    if format == "jsonl":
        return await export_session_jsonl(session_id, db_session_factory, config, save_to_disk)
    elif format in ("markdown", "md"):
        return await export_session_markdown(session_id, db_session_factory, config, save_to_disk)
    else:
        raise ValueError(f"Unsupported export format: {format}. Use 'jsonl' or 'markdown'.")


def parse_jsonl_line(line: str) -> dict[str, Any] | None:
    """
    Parse a single JSONL line back into a message dict.

    Useful for importing/reading exported files.
    Skips lines starting with '_' prefix keys (metadata header).
    """
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
        # Skip metadata header lines
        if isinstance(data, dict) and any(k.startswith("_") for k in data.keys()):
            return None
        return data
    except json.JSONDecodeError:
        return None


def read_jsonl_file(path: str | Path) -> list[dict[str, Any]]:
    """
    Read a JSONL file and return list of message dicts.

    Skips the metadata header line and any malformed lines.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    messages: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            msg = parse_jsonl_line(line)
            if msg is not None:
                messages.append(msg)

    return messages
