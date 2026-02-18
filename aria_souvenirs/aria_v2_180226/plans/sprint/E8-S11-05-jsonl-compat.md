# S11-05: JSONL Export/Import Backward Compatibility
**Epic:** E8 — Quality & Testing | **Priority:** P1 | **Points:** 2 | **Phase:** 11

## Problem
Aria stores conversation history, memory snapshots, and agent logs as JSONL files in `aria_memories/`. The OpenClaw→aria_engine migration changes the internal data structures (session format, message schema, agent metadata). We need integration tests that verify the new engine can read legacy JSONL files AND that newly exported JSONL is importable by both old and new formats.

## Root Cause
JSONL files are the durable persistence layer — they survive database wipes, container rebuilds, and system restarts. If the migration breaks JSONL compatibility, we lose the ability to restore from backups or import historical data. Backward compatibility is non-negotiable.

## Fix
### `tests/integration/test_jsonl_compat.py`
```python
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
# Tests
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
        """Legacy ISO timestamps are parsed correctly."""
        from aria_engine.jsonl_io import import_conversations

        records = await import_conversations(legacy_conversation_file)

        for record in records:
            assert "timestamp" in record
            # Should be parseable as datetime
            ts = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
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
        # Optional fields should get defaults
        assert "timestamp" in records[0] or "session_id" not in records[0]


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
            assert "timestamp" in record

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
                    "timestamp": f"2026-01-01T{i // 3600:02d}:{(i % 3600) // 60:02d}:{i % 60:02d}Z",
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
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer architecture | ❌ | IO utility layer |
| 2 | .env for secrets | ❌ | No secrets |
| 3 | models.yaml single source | ❌ | No LLM calls |
| 4 | Docker-first testing | ❌ | File-only tests |
| 5 | aria_memories only writable path | ✅ | JSONL files in aria_memories/ |
| 6 | No soul modification | ❌ | No soul access |

## Dependencies
- `aria_engine/jsonl_io.py` module must exist (created in Sprint 6)
- Legacy JSONL files from `aria_memories/` for reference

## Verification
```bash
# 1. Run JSONL compatibility tests:
pytest tests/integration/test_jsonl_compat.py -v --timeout=30

# 2. Test large file handling:
pytest tests/integration/test_jsonl_compat.py::TestLargeFiles -v -s

# 3. Test backward compatibility:
pytest tests/integration/test_jsonl_compat.py::TestSchemaCompatibility -v

# 4. Test corrupt file handling:
pytest tests/integration/test_jsonl_compat.py::TestCorruptFileHandling -v
```

## Prompt for Agent
```
Create JSONL export/import backward compatibility tests.

FILES TO READ FIRST:
- aria_engine/jsonl_io.py (JSONL IO module)
- aria_memories/ (existing JSONL file examples)
- aria_mind/memory.py (current memory persistence)
- tests/integration/conftest.py (shared fixtures)

STEPS:
1. Create tests/integration/test_jsonl_compat.py
2. Define legacy JSONL formats as test constants (conversations, memories, agent logs)
3. Test: import legacy, export new, round-trip, corrupt handling, large files
4. Verify new schema is backward-compatible with simple parsers

CONSTRAINTS:
- Legacy format: {role, content, timestamp, session_id, model, tokens}
- New format adds: {engine_version, thinking_content, tool_calls, agent_id, pheromone_score}
- Legacy readers must be able to read new format (extra fields ignored)
- Corrupt JSONL lines must be skipped, not crash
- Large files (10K+ lines) must stream, not load into memory
```
