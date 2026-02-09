#!/usr/bin/env python3
"""
analyze_logs.py — Parse Aria system logs and generate a diagnostic report.
TICKET-28: Log Analysis (Aria Blue v1.1)

Usage:
    python scripts/analyze_logs.py --log-dir aria_memories/logs
    python scripts/analyze_logs.py --log-dir aria_memories/logs --output report.md
    python scripts/analyze_logs.py --help
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# =============================================================================
# Sensitive Data Sanitization
# =============================================================================

# Patterns that match API keys, tokens, and other sensitive data
SANITIZE_PATTERNS = [
    # Generic API keys (sk-..., key-..., etc.)
    (re.compile(r"(sk-[A-Za-z0-9]{8})[A-Za-z0-9]{20,}"), r"\1***REDACTED***"),
    (re.compile(r"(key-[A-Za-z0-9]{4})[A-Za-z0-9]{10,}"), r"\1***REDACTED***"),
    # Bearer tokens
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1***REDACTED***"),
    # Authorization headers
    (re.compile(r"(Authorization:\s*)\S+", re.IGNORECASE), r"\1***REDACTED***"),
    # Generic hex/base64 tokens (32+ chars)
    (re.compile(r"(token[=:]\s*)[A-Za-z0-9+/=]{32,}"), r"\1***REDACTED***"),
    # API key query params (?api_key=..., &apikey=..., etc.)
    (re.compile(r"(api[_-]?key=)[^&\s]+", re.IGNORECASE), r"\1***REDACTED***"),
    # Password fields
    (re.compile(r"(password[=:]\s*)\S+", re.IGNORECASE), r"\1***REDACTED***"),
    # OpenAI-style keys
    (re.compile(r"(org-[A-Za-z0-9]{4})[A-Za-z0-9]{10,}"), r"\1***REDACTED***"),
    # Anthropic-style keys
    (re.compile(r"(ant-api[A-Za-z0-9]{2}-[A-Za-z0-9]{4})[A-Za-z0-9]{20,}"), r"\1***REDACTED***"),
    # Generic long hex strings that look like secrets (40+ hex chars)
    (re.compile(r"(?<=[=:\s])([0-9a-f]{40,})", re.IGNORECASE), r"***REDACTED_HEX***"),
]


def sanitize_line(line: str) -> str:
    """Remove sensitive data (API keys, tokens, passwords) from a log line."""
    for pattern, replacement in SANITIZE_PATTERNS:
        line = pattern.sub(replacement, line)
    return line


def sanitize_text(text: str) -> str:
    """Sanitize a multi-line text block."""
    return "\n".join(sanitize_line(line) for line in text.splitlines())


# =============================================================================
# Error Pattern Definitions
# =============================================================================

@dataclass
class ErrorPattern:
    """Definition of a known error pattern to scan for."""
    name: str
    pattern: re.Pattern
    severity: str  # critical, warning, info
    ticket: str = ""  # Related ticket number
    description: str = ""


# Patterns we watch for across all logs
ERROR_PATTERNS = [
    ErrorPattern(
        name="HTTP 429 Rate Limit",
        pattern=re.compile(r"429|rate.?limit|too many requests", re.IGNORECASE),
        severity="warning",
        ticket="TICKET-14",
        description="API rate limiting — may cause dropped requests",
    ),
    ErrorPattern(
        name="HTTP 500 Server Error",
        pattern=re.compile(r"\b500\b.*(?:error|internal|fail)", re.IGNORECASE),
        severity="critical",
        ticket="",
        description="Internal server errors",
    ),
    ErrorPattern(
        name="Connection Refused/Timeout",
        pattern=re.compile(r"connection\s*(refused|timed?\s*out|reset)", re.IGNORECASE),
        severity="critical",
        ticket="TICKET-22",
        description="Network connectivity failures between services",
    ),
    ErrorPattern(
        name="OOM / Memory Error",
        pattern=re.compile(r"out\s*of\s*memory|oom|memory\s*error|killed", re.IGNORECASE),
        severity="critical",
        ticket="TICKET-9",
        description="Memory exhaustion — potential container restart",
    ),
    ErrorPattern(
        name="Model Load Failure",
        pattern=re.compile(r"model.*(?:not found|fail|error|unavailable)", re.IGNORECASE),
        severity="critical",
        ticket="TICKET-7",
        description="Model loading or availability issues",
    ),
    ErrorPattern(
        name="Session Accumulation",
        pattern=re.compile(r"session|heartbeat.*(?:stale|leak|accumul|orphan)", re.IGNORECASE),
        severity="warning",
        ticket="TICKET-15",
        description="Session lifecycle issues — potential resource leaks",
    ),
    ErrorPattern(
        name="Cron Failure",
        pattern=re.compile(r"cron.*(?:fail|error|skip|miss)", re.IGNORECASE),
        severity="warning",
        ticket="TICKET-20",
        description="Scheduled task failures",
    ),
    ErrorPattern(
        name="Tool Execution Error",
        pattern=re.compile(r"tool.*(?:fail|error|exception|timeout)", re.IGNORECASE),
        severity="warning",
        ticket="TICKET-28",
        description="Tool/skill execution failures",
    ),
    ErrorPattern(
        name="Database Error",
        pattern=re.compile(r"(?:database|db|sql|postgres).*(?:error|fail|timeout|refused)", re.IGNORECASE),
        severity="critical",
        ticket="TICKET-22",
        description="Database connectivity or query failures",
    ),
    ErrorPattern(
        name="Python Exception",
        pattern=re.compile(r"Traceback \(most recent call last\)|^\w+Error:", re.IGNORECASE | re.MULTILINE),
        severity="warning",
        ticket="",
        description="Unhandled Python exceptions",
    ),
    ErrorPattern(
        name="Docker Restart",
        pattern=re.compile(r"container.*(?:restart|exited|unhealthy)", re.IGNORECASE),
        severity="critical",
        ticket="",
        description="Container restarts or health check failures",
    ),
    ErrorPattern(
        name="SSL/TLS Error",
        pattern=re.compile(r"ssl|tls|certificate.*(?:error|fail|expir|invalid)", re.IGNORECASE),
        severity="warning",
        ticket="",
        description="SSL/TLS handshake or certificate issues",
    ),
]


# =============================================================================
# Log Analysis Engine
# =============================================================================

@dataclass
class LogAnalysis:
    """Results of analyzing a set of log files."""
    files_analyzed: list = field(default_factory=list)
    total_lines: int = 0
    error_counts: Counter = field(default_factory=Counter)
    error_examples: dict = field(default_factory=lambda: defaultdict(list))
    severity_counts: Counter = field(default_factory=Counter)
    session_events: list = field(default_factory=list)
    hourly_distribution: Counter = field(default_factory=Counter)
    cost_lines: list = field(default_factory=list)
    model_mentions: Counter = field(default_factory=Counter)
    cron_events: list = field(default_factory=list)
    timestamp_range: tuple = (None, None)


# Timestamp patterns commonly found in Docker/application logs
TIMESTAMP_PATTERNS = [
    re.compile(r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})"),
    re.compile(r"(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2})"),
]

# Model name patterns
MODEL_PATTERN = re.compile(
    r"(gpt-4[a-z0-9\-]*|gpt-3\.5[a-z0-9\-]*|claude[a-z0-9\-]*|"
    r"mlx-community/[A-Za-z0-9\-_.]+|"
    r"llama[a-z0-9\-_.]*|mistral[a-z0-9\-_.]*|"
    r"gemma[a-z0-9\-_.]*|qwen[a-z0-9\-_.]*)",
    re.IGNORECASE,
)

# Cost/spend patterns
COST_PATTERN = re.compile(
    r"(?:cost|spend|price|charge|bill).*?(\$[\d,.]+|[\d,.]+\s*(?:USD|usd|cents?))",
    re.IGNORECASE,
)

# Session lifecycle
SESSION_PATTERN = re.compile(
    r"(session\s*(?:start|end|creat|clos|expir|timeout|active|count).*)",
    re.IGNORECASE,
)

# Cron events
CRON_PATTERN = re.compile(
    r"(cron|schedul|heartbeat|hourly|six.?hour|daily).*?(start|end|run|fail|skip|complet)",
    re.IGNORECASE,
)


def extract_timestamp(line: str) -> Optional[str]:
    """Try to extract a timestamp from a log line."""
    for pat in TIMESTAMP_PATTERNS:
        m = pat.search(line)
        if m:
            return m.group(1)
    return None


def analyze_file(filepath: Path, analysis: LogAnalysis, max_examples: int = 5) -> None:
    """Analyze a single log file and accumulate results into analysis."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"  Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return

    lines = content.splitlines()
    analysis.files_analyzed.append(str(filepath))
    analysis.total_lines += len(lines)

    for line_num, raw_line in enumerate(lines, 1):
        line = sanitize_line(raw_line)

        # Extract timestamp for distribution
        ts = extract_timestamp(line)
        if ts:
            try:
                hour = ts[:13]  # YYYY-MM-DDTHH
                analysis.hourly_distribution[hour] += 1
            except (IndexError, ValueError):
                pass

        # Check error patterns
        for ep in ERROR_PATTERNS:
            if ep.pattern.search(line):
                analysis.error_counts[ep.name] += 1
                analysis.severity_counts[ep.severity] += 1
                if len(analysis.error_examples[ep.name]) < max_examples:
                    analysis.error_examples[ep.name].append(
                        f"  [{filepath.name}:{line_num}] {line.strip()[:200]}"
                    )

        # Model mentions
        model_match = MODEL_PATTERN.search(line)
        if model_match:
            analysis.model_mentions[model_match.group(1).lower()] += 1

        # Cost lines
        if COST_PATTERN.search(line):
            analysis.cost_lines.append(sanitize_line(raw_line.strip()[:200]))

        # Session events
        session_match = SESSION_PATTERN.search(line)
        if session_match:
            analysis.session_events.append(
                f"[{filepath.name}:{line_num}] {line.strip()[:200]}"
            )

        # Cron events
        if CRON_PATTERN.search(line):
            analysis.cron_events.append(
                f"[{filepath.name}:{line_num}] {line.strip()[:200]}"
            )


def analyze_logs(log_dir: Path) -> LogAnalysis:
    """Analyze all log files in the given directory."""
    analysis = LogAnalysis()
    log_files = sorted(log_dir.glob("*.log"))

    if not log_files:
        print(f"Warning: No .log files found in {log_dir}", file=sys.stderr)
        return analysis

    for log_file in log_files:
        print(f"  Analyzing: {log_file.name} ({log_file.stat().st_size:,} bytes)", file=sys.stderr)
        analyze_file(log_file, analysis)

    return analysis


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(analysis: LogAnalysis, report_date: Optional[str] = None) -> str:
    """Generate a Markdown diagnostic report from analysis results."""
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = []

    # Header
    sections.append(f"# Aria Diagnostic Report\n")
    sections.append(f"**Generated:** {report_date}  ")
    sections.append(f"**Files Analyzed:** {len(analysis.files_analyzed)}  ")
    sections.append(f"**Total Lines Parsed:** {analysis.total_lines:,}  ")
    sections.append("")

    # --- Executive Summary ---
    sections.append("## Executive Summary\n")
    total_errors = sum(analysis.error_counts.values())
    crit = analysis.severity_counts.get("critical", 0)
    warn = analysis.severity_counts.get("warning", 0)
    info = analysis.severity_counts.get("info", 0)

    if total_errors == 0:
        sections.append("No known error patterns detected in the analyzed logs. "
                        "This may indicate healthy operation or that logs are empty/unavailable.\n")
    else:
        sections.append(f"Detected **{total_errors:,}** error pattern matches across "
                        f"{len(analysis.files_analyzed)} log file(s):\n")
        sections.append(f"- **Critical:** {crit}")
        sections.append(f"- **Warning:** {warn}")
        sections.append(f"- **Info:** {info}")
        sections.append("")

        top3 = analysis.error_counts.most_common(3)
        if top3:
            sections.append("**Top issues:** " + ", ".join(
                f"{name} ({count}x)" for name, count in top3
            ))
            sections.append("")

    # --- Top Error Patterns ---
    sections.append("## Top Error Patterns\n")
    if analysis.error_counts:
        sections.append("| # | Pattern | Count | Severity | Related Ticket |")
        sections.append("|---|---------|-------|----------|----------------|")
        for rank, (name, count) in enumerate(analysis.error_counts.most_common(20), 1):
            ep = next((p for p in ERROR_PATTERNS if p.name == name), None)
            severity = ep.severity if ep else "?"
            ticket = ep.ticket if ep else ""
            sections.append(f"| {rank} | {name} | {count:,} | {severity} | {ticket} |")
        sections.append("")

        # Examples for top patterns
        sections.append("### Sample Error Lines\n")
        for name, _ in analysis.error_counts.most_common(5):
            examples = analysis.error_examples.get(name, [])
            if examples:
                sections.append(f"**{name}:**")
                sections.append("```")
                for ex in examples[:3]:
                    sections.append(ex)
                sections.append("```")
                sections.append("")
    else:
        sections.append("_No error patterns detected._\n")

    # --- Session Lifecycle ---
    sections.append("## Session Lifecycle Analysis\n")
    if analysis.session_events:
        sections.append(f"Found **{len(analysis.session_events)}** session-related events.\n")
        sections.append("```")
        for evt in analysis.session_events[:20]:
            sections.append(evt)
        if len(analysis.session_events) > 20:
            sections.append(f"  ... and {len(analysis.session_events) - 20} more")
        sections.append("```")
        sections.append("")
    else:
        sections.append("_No session lifecycle events detected._\n")

    # --- Cost & Spend ---
    sections.append("## Cost & Spend Analysis\n")
    if analysis.cost_lines:
        sections.append(f"Found **{len(analysis.cost_lines)}** cost-related log entries:\n")
        sections.append("```")
        for cl in analysis.cost_lines[:15]:
            sections.append(sanitize_line(cl))
        sections.append("```")
        sections.append("")
    else:
        sections.append("_No cost/spend data found in logs. "
                        "Check LiteLLM /global-spend endpoint for cost data._\n")

    # --- Model Performance ---
    sections.append("## Model Performance\n")
    if analysis.model_mentions:
        sections.append("| Model | Mentions |")
        sections.append("|-------|----------|")
        for model, count in analysis.model_mentions.most_common(15):
            sections.append(f"| {model} | {count:,} |")
        sections.append("")
    else:
        sections.append("_No model references found in logs._\n")

    # --- Cron Job Health ---
    sections.append("## Cron Job Health\n")
    if analysis.cron_events:
        sections.append(f"Found **{len(analysis.cron_events)}** cron/schedule events:\n")
        sections.append("```")
        for ce in analysis.cron_events[:20]:
            sections.append(ce)
        if len(analysis.cron_events) > 20:
            sections.append(f"  ... and {len(analysis.cron_events) - 20} more")
        sections.append("```")
        sections.append("")
    else:
        sections.append("_No cron events detected in logs._\n")

    # --- Hourly Distribution ---
    if analysis.hourly_distribution:
        sections.append("## Error Distribution by Hour\n")
        sections.append("```")
        for hour, count in sorted(analysis.hourly_distribution.items())[-24:]:
            bar = "#" * min(count, 60)
            sections.append(f"{hour} | {bar} ({count})")
        sections.append("```")
        sections.append("")

    # --- Cross-Reference Table ---
    sections.append("## Cross-Reference: Findings → Tickets\n")
    sections.append("| Finding | Severity | Count | Ticket | Description |")
    sections.append("|---------|----------|-------|--------|-------------|")
    for name, count in analysis.error_counts.most_common():
        ep = next((p for p in ERROR_PATTERNS if p.name == name), None)
        if ep:
            sections.append(
                f"| {name} | {ep.severity} | {count:,} | {ep.ticket or 'N/A'} | {ep.description} |"
            )
    if not analysis.error_counts:
        sections.append("| _None_ | — | 0 | — | No error patterns detected |")
    sections.append("")

    # --- Recommendations ---
    sections.append("## Recommendations\n")
    recommendations = _generate_recommendations(analysis)
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            sections.append(f"{i}. {rec}")
    else:
        sections.append("No specific recommendations at this time. System appears healthy.")
    sections.append("")

    # --- Files ---
    sections.append("## Appendix: Files Analyzed\n")
    for f in analysis.files_analyzed:
        sections.append(f"- `{f}`")
    sections.append("")

    return "\n".join(sections)


def _generate_recommendations(analysis: LogAnalysis) -> list[str]:
    """Generate actionable recommendations based on analysis findings."""
    recs = []

    if analysis.error_counts.get("HTTP 429 Rate Limit", 0) > 10:
        recs.append("**Rate Limiting:** High volume of 429 errors detected. "
                     "Consider implementing request queuing or increasing rate limits. (TICKET-14)")

    if analysis.error_counts.get("OOM / Memory Error", 0) > 0:
        recs.append("**Memory:** OOM events detected. Review container memory limits and "
                     "investigate memory leaks in long-running services. (TICKET-9)")

    if analysis.error_counts.get("Connection Refused/Timeout", 0) > 5:
        recs.append("**Connectivity:** Multiple connection failures detected. "
                     "Verify service health checks and inter-container networking. (TICKET-22)")

    if analysis.error_counts.get("Session Accumulation", 0) > 0:
        recs.append("**Sessions:** Session accumulation signals detected. "
                     "Audit session cleanup logic and expire stale sessions. (TICKET-15)")

    if analysis.error_counts.get("Model Load Failure", 0) > 0:
        recs.append("**Models:** Model load failures detected. "
                     "Verify model availability and fallback chains. (TICKET-7)")

    if analysis.error_counts.get("Cron Failure", 0) > 0:
        recs.append("**Cron:** Scheduled task failures detected. "
                     "Review cron_jobs.yaml and ensure dependent services are available. (TICKET-20)")

    if analysis.error_counts.get("Database Error", 0) > 0:
        recs.append("**Database:** Database errors detected. "
                     "Check connection pooling, query timeouts, and DB health. (TICKET-22)")

    if analysis.error_counts.get("Docker Restart", 0) > 0:
        recs.append("**Containers:** Container restarts detected. "
                     "Review restart policies and check for crash loops.")

    if len(analysis.session_events) > 50:
        recs.append("**Session Volume:** High number of session events — "
                     "verify sessions are being cleaned up properly.")

    if not analysis.files_analyzed:
        recs.append("**No Logs:** No log files were found. "
                     "Run `scripts/retrieve_logs.sh` to pull logs from the Mac Mini.")

    return recs


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Aria system logs and generate a diagnostic report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  python scripts/analyze_logs.py --log-dir aria_memories/logs
  python scripts/analyze_logs.py --log-dir aria_memories/logs --output report.md
  python scripts/analyze_logs.py --log-dir aria_memories/logs --output -
        """,
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path("aria_memories/logs"),
        help="Directory containing .log files to analyze (default: aria_memories/logs)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="-",
        help="Output file for the report. Use '-' for stdout (default: stdout)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Override report date string (default: current time)",
    )
    args = parser.parse_args()

    log_dir = args.log_dir
    if not log_dir.is_dir():
        print(f"Error: Log directory not found: {log_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing logs in: {log_dir}", file=sys.stderr)
    analysis = analyze_logs(log_dir)

    report = generate_report(analysis, report_date=args.date)

    if args.output == "-":
        print(report)
    else:
        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
