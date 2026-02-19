"""
JSONL export/import backward compatibility tests.

Verifies:
- Legacy JSONL files (OpenClaw era) can be imported
- New JSONL exports maintain backward-compatible schema
- Round-trip: export → reimport produces identical data
- Large files handle streaming correctly
- Corrupt lines are skipped gracefully
"""
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Legacy JSONL formats (pre-migration, OpenClaw era)
# ---------------------------------------------------------------------------

LEGACY_CONVERSATION_JSONL = """\
{"role": "user", "content": "Hello Aria!", "timestamp": "2026-01-15T10:30:00Z", "session_id": "sess-001"}
{"role": "assistant", "content": "Hello! How can I help?", "timestamp": "2026-01-15T10:30:05Z", "session_id": "sess-001", "model": "qwen3:32b"}
{"role": "user", "content": "Tell me about Python", "timestamp": "2026-01-15T10:31:00Z", "session_id": "sess-001"}
{"role": "assistant", "content": "Python is a versatile programming language...", "timestamp": "2026-01-15T10:31:08Z", "session_id": "sess-001", "model": "qwen3:32b", "tokens": {"input": 15, "output": 42}}
"""

LEGACY_MEMORY_JSONL = """\
{"type": "memory", "key": "user_preference_language", "value": "Python", "created": "2026-01-10T08:00:00Z", "source": "conversation", "confidence": 0.9}
{"type": "memory", "key": "user_name", "value": "Developer", "created": "2026-01-10T08:00:00Z", "source": "introduction", "confidence": 1.0}
{"type": "memory", "key": "project_context", "value": "Building an AI agent platform", "created": "2026-01-12T14:00:00Z", "source": "conversation", "confidence": 0.85}
"""

LEGACY_AGENT_LOG_JSONL = """\
{"agent_id": "researcher", "action": "search", "query": "Python 3.13 features", "timestamp": "2026-01-20T12:00:00Z", "duration_ms": 1500, "result": "success"}
{"agent_id": "coder", "action": "execute", "code": "print('hello')", "timestamp": "2026-01-20T12:05:00Z", "duration_ms": 200, "result": "success", "output": "hello"}
{"agent_id": "coordinator", "action": "route", "message": "Research AI safety", "timestamp": "2026-01-20T12:10:00Z", "duration_ms": 50, "result": "routed_to_researcher"}
"""

# New format includes additional fields
NEW_CONVERSATION_FIELDS = {
    "engine_version", "thinking_content", "tool_calls",
    "agent_id", "pheromone_score",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def legacy_conversation_file(tmp_path: Path) -> Path:
    """Create a legacy conversation JSONL file."""
    path = tmp_path / "legacy_conversation.jsonl"
    path.write_text(LEGACY_CONVERSATION_JSONL, encoding="utf-8")
    return path


@pytest.fixture
def legacy_memory_file(tmp_path: Path) -> Path:
    """Create a legacy memory JSONL file."""
    path = tmp_path / "legacy_memory.jsonl"
    path.write_text(LEGACY_MEMORY_JSONL, encoding="utf-8")
    return path


@pytest.fixture
def legacy_agent_log_file(tmp_path: Path) -> Path:
    """Create a legacy agent log JSONL file."""
    path = tmp_path / "legacy_agent_log.jsonl"
    path.write_text(LEGACY_AGENT_LOG_JSONL, encoding="utf-8")
    return path


@pytest.fixture
def corrupt_jsonl_file(tmp_path: Path) -> Path:
    """Create a JSONL file with some corrupt lines."""
    content = """\
{"role": "user", "content": "Valid line 1", "timestamp": "2026-01-15T10:00:00Z"}
this is not json at all
{"role": "assistant", "content": "Valid line 2", "timestamp": "2026-01-15T10:00:05Z"}

{"incomplete": true
{"role": "user", "content": "Valid line 3", "timestamp": "2026-01-15T10:01:00Z"}
"""
    path = tmp_path / "corrupt.jsonl"
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests — Legacy import
# ---------------------------------------------------------------------------

class TestLegacyImport:
    """Test importing legacy JSONL files."""

    @pytest.mark.integration
    async def test_import_legacy_conversations(self, legacy_conversation_file):
        """Legacy conversation JSONL imports successfully."""
        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(legacy_conversation_file)

        assert len(records) == 4
        assert records[0]["role"] == "user"
        assert records[0]["content"] == "Hello Aria!"
        assert records[1]["role"] == "assistant"
        assert "session_id" in records[0]

    @pytest.mark.integration
    async def test_import_legacy_memories(self, legacy_memory_file):
        """Legacy memory JSONL imports successfully."""
        from aria_engine.jsonl_io import import_memories

        records = await import_memories(legacy_memory_file)

        assert len(records) == 3
        assert records[0]["key"] == "user_preference_language"
        assert records[0]["value"] == "Python"
        assert records[0]["confidence"] == 0.9

    @pytest.mark.integration
    async def test_import_legacy_agent_logs(self, legacy_agent_log_file):
        """Legacy agent log JSONL imports successfully."""
        from aria_engine.jsonl_io import import_agent_logs

        records = await import_agent_logs(legacy_agent_log_file)

        assert len(records) == 3
        assert records[0]["agent_id"] == "researcher"
        assert records[0]["action"] == "search"

    @pytest.mark.integration
    async def test_legacy_timestamps_parsed(self, legacy_conversation_file):
        """Legacy ISO timestamps are preserved correctly."""
        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(legacy_conversation_file)

        for record in records:
            assert "timestamp" in record
            # Timestamps should be parseable (Z replaced with +00:00)
            ts = datetime.fromisoformat(record["timestamp"])
            assert ts.year == 2026

    @pytest.mark.integration
    async def test_legacy_missing_optional_fields(self, tmp_path):
        """Legacy records with missing optional fields import with defaults."""
        minimal_jsonl = '{"role": "user", "content": "Bare minimum"}\n'
        path = tmp_path / "minimal.jsonl"
        path.write_text(minimal_jsonl, encoding="utf-8")

        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(path)
        assert len(records) == 1
        assert records[0]["role"] == "user"
        assert records[0]["content"] == "Bare minimum"


# ---------------------------------------------------------------------------
# Tests — New export
# ---------------------------------------------------------------------------

class TestNewExport:
    """Test new-format JSONL export."""

    @pytest.mark.integration
    async def test_export_conversations(self, tmp_path):
        """New conversation export produces valid JSONL."""
        from aria_engine.jsonl_io import export_conversations

        messages = [
            {
                "role": "user",
                "content": "Hello!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "export-test-001",
            },
            {
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "export-test-001",
                "model": "qwen3:32b",
                "engine_version": "2.0.0",
                "agent_id": "coordinator",
            },
        ]

        output_path = tmp_path / "exported.jsonl"
        await export_conversations(messages, output_path)

        # Verify output
        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            record = json.loads(line)
            assert "role" in record
            assert "content" in record

    @pytest.mark.integration
    async def test_export_includes_new_fields(self, tmp_path):
        """New export includes engine-specific fields."""
        from aria_engine.jsonl_io import export_conversations

        messages = [
            {
                "role": "assistant",
                "content": "Response with metadata",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "meta-test-001",
                "model": "qwen3:32b",
                "engine_version": "2.0.0",
                "thinking_content": "Let me think about this...",
                "agent_id": "researcher",
                "pheromone_score": 0.85,
                "tool_calls": [{"name": "search", "args": {"q": "test"}}],
            },
        ]

        output_path = tmp_path / "with_meta.jsonl"
        await export_conversations(messages, output_path)

        line = output_path.read_text(encoding="utf-8").strip()
        record = json.loads(line)
        assert record["engine_version"] == "2.0.0"
        assert record["thinking_content"] == "Let me think about this..."
        assert record["agent_id"] == "researcher"

    @pytest.mark.integration
    async def test_export_memories(self, tmp_path):
        """Memory export produces valid JSONL."""
        from aria_engine.jsonl_io import export_memories

        memories = [
            {
                "type": "memory",
                "key": "test_value",
                "value": "test",
                "confidence": 0.9,
            },
        ]

        output_path = tmp_path / "memories.jsonl"
        await export_memories(memories, output_path)

        lines = output_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["key"] == "test_value"


# ---------------------------------------------------------------------------
# Tests — Round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Test export → reimport round-trip fidelity."""

    @pytest.mark.integration
    async def test_conversation_round_trip(self, tmp_path):
        """Export then reimport produces identical records."""
        from aria_engine.jsonl_io import export_conversations, import_conversations

        original = [
            {
                "role": "user",
                "content": "Round trip test",
                "timestamp": "2026-03-01T12:00:00+00:00",
                "session_id": "roundtrip-001",
            },
            {
                "role": "assistant",
                "content": "I am the response",
                "timestamp": "2026-03-01T12:00:05+00:00",
                "session_id": "roundtrip-001",
                "model": "qwen3:32b",
                "engine_version": "2.0.0",
            },
        ]

        path = tmp_path / "roundtrip.jsonl"
        await export_conversations(original, path)
        reimported = await import_conversations(path)

        assert len(reimported) == len(original)
        for orig, reimp in zip(original, reimported):
            assert orig["role"] == reimp["role"]
            assert orig["content"] == reimp["content"]
            assert orig["session_id"] == reimp["session_id"]

    @pytest.mark.integration
    async def test_memory_round_trip(self, tmp_path):
        """Memory export → reimport preserves all fields."""
        from aria_engine.jsonl_io import export_memories, import_memories

        original = [
            {
                "type": "memory",
                "key": "test_key",
                "value": "test_value",
                "created": "2026-03-01T12:00:00+00:00",
                "source": "test",
                "confidence": 0.95,
            },
        ]

        path = tmp_path / "memory_roundtrip.jsonl"
        await export_memories(original, path)
        reimported = await import_memories(path)

        assert len(reimported) == 1
        assert reimported[0]["key"] == "test_key"
        assert reimported[0]["confidence"] == 0.95


# ---------------------------------------------------------------------------
# Tests — Corrupt file handling
# ---------------------------------------------------------------------------

class TestCorruptFileHandling:
    """Test graceful handling of corrupt JSONL files."""

    @pytest.mark.integration
    async def test_corrupt_lines_skipped(self, corrupt_jsonl_file):
        """Corrupt lines are skipped without crashing."""
        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(corrupt_jsonl_file)

        # Should get the 3 valid lines, skip the corrupt ones
        assert len(records) == 3
        assert records[0]["content"] == "Valid line 1"
        assert records[1]["content"] == "Valid line 2"
        assert records[2]["content"] == "Valid line 3"

    @pytest.mark.integration
    async def test_empty_file_returns_empty_list(self, tmp_path):
        """Empty JSONL file returns empty list."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")

        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(path)
        assert records == []

    @pytest.mark.integration
    async def test_nonexistent_file_raises(self, tmp_path):
        """Importing from nonexistent file raises FileNotFoundError."""
        from aria_engine.jsonl_io import import_conversations

        with pytest.raises(FileNotFoundError):
            await import_conversations(tmp_path / "does_not_exist.jsonl")

    @pytest.mark.integration
    async def test_blank_lines_skipped(self, tmp_path):
        """Blank lines in JSONL are skipped."""
        content = '{"role": "user", "content": "Line 1"}\n\n\n{"role": "assistant", "content": "Line 2"}\n\n'
        path = tmp_path / "blanks.jsonl"
        path.write_text(content, encoding="utf-8")

        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(path)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# Tests — Large files
# ---------------------------------------------------------------------------

class TestLargeFiles:
    """Test handling of large JSONL files."""

    @pytest.mark.integration
    async def test_streaming_import_large_file(self, tmp_path):
        """Large files are imported via streaming (not loaded into memory)."""
        from aria_engine.jsonl_io import import_conversations

        # Create a file with 10,000 lines
        path = tmp_path / "large.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for i in range(10_000):
                record = {
                    "role": "user" if i % 2 == 0 else "assistant",
                    "content": f"Message {i}",
                    "timestamp": f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}+00:00",
                    "session_id": f"large-{i // 100}",
                }
                f.write(json.dumps(record) + "\n")

        records = await import_conversations(path)
        assert len(records) == 10_000

    @pytest.mark.integration
    async def test_export_large_dataset(self, tmp_path):
        """Large datasets export without memory issues."""
        from aria_engine.jsonl_io import export_conversations

        messages = [
            {
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message number {i}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": f"large-export-{i // 100}",
            }
            for i in range(10_000)
        ]

        path = tmp_path / "large_export.jsonl"
        await export_conversations(messages, path)

        # Verify file
        line_count = sum(1 for _ in open(path, encoding="utf-8"))
        assert line_count == 10_000


# ---------------------------------------------------------------------------
# Tests — Schema compatibility
# ---------------------------------------------------------------------------

class TestSchemaCompatibility:
    """Verify new schema is backward-compatible with legacy readers."""

    @pytest.mark.integration
    async def test_new_export_readable_by_legacy_parser(self, tmp_path):
        """New export format can be read by a simple legacy-style parser."""
        from aria_engine.jsonl_io import export_conversations

        messages = [
            {
                "role": "assistant",
                "content": "New format message",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "compat-001",
                "engine_version": "2.0.0",
                "thinking_content": "I'm thinking...",
                "agent_id": "researcher",
                "pheromone_score": 0.85,
            },
        ]

        path = tmp_path / "new_format.jsonl"
        await export_conversations(messages, path)

        # Legacy parser: only reads role, content, timestamp, session_id
        with open(path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                # Legacy required fields must exist
                assert "role" in record
                assert "content" in record
                # New fields should not break legacy parser
                legacy_record = {
                    k: v for k, v in record.items()
                    if k in {"role", "content", "timestamp", "session_id", "model"}
                }
                assert len(legacy_record) >= 2

    @pytest.mark.integration
    async def test_export_import_read_jsonl_file_compat(self, tmp_path):
        """New export is compatible with export.py's read_jsonl_file()."""
        from aria_engine.jsonl_io import export_conversations
        from aria_engine.export import read_jsonl_file

        messages = [
            {
                "role": "user",
                "content": "Test message",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "compat-002",
            },
            {
                "role": "assistant",
                "content": "Test response",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "session_id": "compat-002",
                "engine_version": "2.0.0",
                "agent_id": "main",
            },
        ]

        path = tmp_path / "compat_test.jsonl"
        await export_conversations(messages, path)

        # read_jsonl_file from export.py should parse these
        parsed = read_jsonl_file(path)
        assert len(parsed) == 2
        assert parsed[0]["role"] == "user"
        assert parsed[1]["role"] == "assistant"

    @pytest.mark.integration
    async def test_parse_jsonl_line_handles_new_fields(self):
        """export.py's parse_jsonl_line handles new-format lines."""
        from aria_engine.export import parse_jsonl_line

        line = json.dumps({
            "role": "assistant",
            "content": "Hello",
            "engine_version": "2.0.0",
            "agent_id": "researcher",
            "pheromone_score": 0.85,
        })

        result = parse_jsonl_line(line)
        assert result is not None
        assert result["role"] == "assistant"
        assert result["engine_version"] == "2.0.0"

    @pytest.mark.integration
    async def test_metadata_header_skipped(self):
        """Lines starting with _ prefix keys are skipped."""
        from aria_engine.export import parse_jsonl_line

        header = json.dumps({
            "_session_id": "test",
            "_exported_at": "2026-01-01T00:00:00Z",
        })

        result = parse_jsonl_line(header)
        assert result is None

    @pytest.mark.integration
    async def test_empty_line_skipped(self):
        """Empty lines return None."""
        from aria_engine.export import parse_jsonl_line

        assert parse_jsonl_line("") is None
        assert parse_jsonl_line("   ") is None
        assert parse_jsonl_line("\n") is None
