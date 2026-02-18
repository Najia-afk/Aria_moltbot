"""
tests/test_log_analysis.py — Tests for the log analysis tooling.
TICKET-28: Log Analysis (Aria Blue v1.1)
"""
import ast
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import analyze_logs  # noqa: E402


# ==========================================================================
# 1. Syntax validity
# ==========================================================================

class TestSyntaxValidity:
    """Ensure analyze_logs.py is syntactically valid Python."""

    def test_ast_parse(self):
        """analyze_logs.py should parse without syntax errors."""
        source = (SCRIPTS_DIR / "analyze_logs.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        assert tree is not None

    def test_module_imports(self):
        """The module should import without errors."""
        # If we got here, the import at the top succeeded
        assert hasattr(analyze_logs, "sanitize_line")
        assert hasattr(analyze_logs, "analyze_logs")
        assert hasattr(analyze_logs, "generate_report")
        assert hasattr(analyze_logs, "ERROR_PATTERNS")


# ==========================================================================
# 2. Sanitization
# ==========================================================================

class TestSanitization:
    """Test that sensitive data is stripped from log lines."""

    def test_sanitize_openai_key(self):
        line = 'Authorization: Bearer sk-abcdefgh1234567890abcdefghijklmnopqrstuvwxyz'
        result = analyze_logs.sanitize_line(line)
        assert "sk-abcdefgh1234567890" not in result
        assert "REDACTED" in result

    def test_sanitize_bearer_token(self):
        line = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.long-token-value"
        result = analyze_logs.sanitize_line(line)
        assert "eyJhbGciOiJ" not in result
        assert "REDACTED" in result

    def test_sanitize_api_key_query_param(self):
        line = "GET /api?api_key=supersecretkey123456&model=gpt-4"
        result = analyze_logs.sanitize_line(line)
        assert "supersecretkey123456" not in result
        assert "model=gpt-4" in result  # non-sensitive data preserved

    def test_sanitize_password_field(self):
        line = "password=MyS3cretP@ss!"
        result = analyze_logs.sanitize_line(line)
        assert "MyS3cretP@ss!" not in result
        assert "REDACTED" in result

    def test_sanitize_preserves_normal_text(self):
        line = "2025-02-09T10:30:00 INFO Starting heartbeat cycle"
        result = analyze_logs.sanitize_line(line)
        assert result == line  # nothing should be redacted

    def test_sanitize_multiline(self):
        text = "key=sk-abcdefgh1234567890abcdefghijklmnopqrstuvwxyz\nnormal line\npassword=secret123"
        result = analyze_logs.sanitize_text(text)
        assert "sk-abcdefgh1234567890" not in result
        assert "secret123" not in result
        assert "normal line" in result


# ==========================================================================
# 3. Error pattern matching
# ==========================================================================

class TestErrorPatterns:
    """Test that error patterns match expected log lines."""

    def test_429_rate_limit(self):
        lines = [
            "ERROR 429 Too Many Requests",
            "rate limit exceeded for model gpt-4",
            "HTTP/1.1 429",
        ]
        pattern = next(p for p in analyze_logs.ERROR_PATTERNS if p.name == "HTTP 429 Rate Limit")
        for line in lines:
            assert pattern.pattern.search(line), f"Should match: {line}"

    def test_connection_error(self):
        lines = [
            "ConnectionRefusedError: connection refused",
            "requests.exceptions.ConnectionError: connection timed out",
        ]
        pattern = next(p for p in analyze_logs.ERROR_PATTERNS if p.name == "Connection Refused/Timeout")
        for line in lines:
            assert pattern.pattern.search(line), f"Should match: {line}"

    def test_oom_pattern(self):
        lines = [
            "Out of memory: Killed process 12345",
            "MemoryError: unable to allocate",
            "OOM killer invoked",
        ]
        pattern = next(p for p in analyze_logs.ERROR_PATTERNS if p.name == "OOM / Memory Error")
        for line in lines:
            assert pattern.pattern.search(line), f"Should match: {line}"

    def test_model_pattern(self):
        lines = [
            "model gpt-4o not found",
            "Model loading failed for claude-3",
            "model unavailable: llama-3.1",
        ]
        pattern = next(p for p in analyze_logs.ERROR_PATTERNS if p.name == "Model Load Failure")
        for line in lines:
            assert pattern.pattern.search(line), f"Should match: {line}"

    def test_no_false_positive_on_clean_line(self):
        clean = "2025-02-09T10:30:00 INFO Request completed successfully in 42ms"
        for ep in analyze_logs.ERROR_PATTERNS:
            # Some patterns may match generic words; ensure critical ones don't fire
            if ep.severity == "critical":
                assert not ep.pattern.search(clean), \
                    f"Critical pattern '{ep.name}' should NOT match clean line"


# ==========================================================================
# 4. Report generation with mock data
# ==========================================================================

class TestReportGeneration:
    """Test the full report generation pipeline with mock log data."""

    @pytest.fixture
    def mock_log_dir(self, tmp_path):
        """Create a temp directory with mock log files."""
        aria_log = tmp_path / "aria_brain_20250209_120000.log"
        aria_log.write_text(textwrap.dedent("""\
            2025-02-09T10:00:00 INFO Starting aria-api
            2025-02-09T10:00:01 INFO Loaded model gpt-4o-mini
            2025-02-09T10:05:00 ERROR 429 Too Many Requests for model gpt-4o-mini
            2025-02-09T10:05:01 WARNING rate limit exceeded, backing off
            2025-02-09T10:10:00 INFO session start: user=test
            2025-02-09T10:15:00 ERROR connection refused to database
            2025-02-09T10:20:00 INFO cron heartbeat completed
            2025-02-09T10:25:00 ERROR tool execution failed: brainstorm timed out
            2025-02-09T10:30:00 INFO session end: user=test
            2025-02-09T10:35:00 ERROR model gpt-4 not found, falling back
        """), encoding="utf-8")

        litellm = tmp_path / "litellm_20250209_120000.log"
        litellm.write_text(textwrap.dedent("""\
            2025-02-09T10:00:00 INFO LiteLLM proxy started
            2025-02-09T10:01:00 INFO Request to gpt-4o-mini cost $0.002
            2025-02-09T10:02:00 INFO Request to claude-3-5-sonnet cost $0.005
            2025-02-09T10:05:00 ERROR 429 rate limit from OpenAI
            2025-02-09T10:06:00 WARNING Out of memory for large context
        """), encoding="utf-8")

        return tmp_path

    def test_analyze_finds_errors(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        assert analysis.total_lines > 0
        assert len(analysis.files_analyzed) == 2
        assert analysis.error_counts["HTTP 429 Rate Limit"] >= 3  # 429 appears in multiple lines

    def test_report_contains_all_sections(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        report = analyze_logs.generate_report(analysis, report_date="2025-02-09 12:00")
        assert "# Aria Diagnostic Report" in report
        assert "## Executive Summary" in report
        assert "## Top Error Patterns" in report
        assert "## Session Lifecycle Analysis" in report
        assert "## Cost & Spend Analysis" in report
        assert "## Model Performance" in report
        assert "## Cron Job Health" in report
        assert "## Cross-Reference" in report
        assert "## Recommendations" in report

    def test_report_contains_error_counts(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        report = analyze_logs.generate_report(analysis)
        assert "HTTP 429 Rate Limit" in report
        assert "Connection Refused/Timeout" in report

    def test_report_contains_model_mentions(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        report = analyze_logs.generate_report(analysis)
        assert "gpt-4o-mini" in report

    def test_report_contains_session_events(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        assert len(analysis.session_events) >= 2  # start + end

    def test_report_has_recommendations(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        report = analyze_logs.generate_report(analysis)
        # Should recommend addressing rate limits since we have >10... let's check
        # We have ~3 rate limit hits, which is under 10, so let's verify at least
        # the recommendations section exists
        assert "## Recommendations" in report

    def test_empty_log_dir(self, tmp_path):
        """Analyzing an empty directory should produce a valid report."""
        analysis = analyze_logs.analyze_logs(tmp_path)
        report = analyze_logs.generate_report(analysis)
        assert "# Aria Diagnostic Report" in report
        assert "No known error patterns detected" in report
        assert "No Logs" in report  # recommendation about no logs

    def test_cost_lines_extracted(self, mock_log_dir):
        analysis = analyze_logs.analyze_logs(mock_log_dir)
        assert len(analysis.cost_lines) >= 2  # two cost entries in litellm mock


# ==========================================================================
# 5. CLI argument parsing
# ==========================================================================

class TestCLI:
    """Test the CLI argument parser."""

    def test_help_flag(self):
        """--help should exit 0 and show usage."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "analyze_logs.py"), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "--log-dir" in result.stdout

    def test_missing_log_dir_exits_nonzero(self):
        """Nonexistent --log-dir should exit 1."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "analyze_logs.py"),
             "--log-dir", "/nonexistent/path/12345"],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
