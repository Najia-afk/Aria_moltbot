#!/usr/bin/env python3
"""
Session Management Dashboard

Lightweight CLI dashboard for monitoring OpenClaw sessions.
Uses the session_manager skill or falls back to direct API calls.

Usage:
    python session_dashboard.py           # Show dashboard
    python session_dashboard.py --prune   # Prune stale sessions
    python session_dashboard.py --json    # Output JSON
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Add workspace to path for skill imports
sys.path.insert(0, "/root/.openclaw/workspace")

from aria_skills.session_manager import SessionManagerSkill
from aria_skills.base import SkillConfig


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def format_time(iso_str: str) -> str:
    """Format ISO timestamp to human-readable."""
    if not iso_str:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - dt
        if age.days > 0:
            return f"{age.days}d ago"
        hours = age.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = age.seconds // 60
        return f"{minutes}m ago"
    except:
        return iso_str[:19]


def print_dashboard(stats: Dict[str, Any], sessions: List[Dict[str, Any]]):
    """Print formatted dashboard."""
    print(f"\n{Colors.HEADER}{'═' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  ⚡ Aria Session Dashboard{Colors.END}")
    print(f"{Colors.HEADER}{'═' * 60}{Colors.END}\n")

    # Stats summary
    total = stats.get("total_sessions", 0)
    stale = stats.get("stale_sessions", 0)
    active = stats.get("active_sessions", 0)
    threshold = stats.get("stale_threshold_minutes", 60)

    print(f"  {Colors.BOLD}Summary:{Colors.END}")
    print(f"    Total Sessions: {Colors.CYAN}{total}{Colors.END}")
    print(f"    Active: {Colors.GREEN}{active}{Colors.END}")
    print(f"    Stale (>{threshold}m): {Colors.WARNING if stale > 0 else Colors.GREEN}{stale}{Colors.END}")
    print()

    # By agent breakdown
    by_agent = stats.get("by_agent", {})
    if by_agent:
        print(f"  {Colors.BOLD}By Agent:{Colors.END}")
        for agent, count in sorted(by_agent.items(), key=lambda x: -x[1]):
            color = Colors.GREEN if count < 3 else Colors.WARNING if count < 6 else Colors.FAIL
            print(f"    {agent}: {color}{count}{Colors.END}")
        print()

    # Session list
    if sessions:
        print(f"  {Colors.BOLD}Recent Sessions:{Colors.END}")
        print(f"    {'ID':<28} {'Agent':<15} {'Updated':<12}")
        print(f"    {'─' * 55}")
        for sess in sessions[:10]:  # Show top 10
            sid = sess.get("id", sess.get("session_id", "unknown"))[:26]
            agent = sess.get("agentId", sess.get("agent_id", "unknown"))[:13]
            updated = format_time(
                sess.get("updatedAt") or sess.get("updated_at") or ""
            )
            print(f"    {sid:<28} {agent:<15} {updated:<12}")
        if len(sessions) > 10:
            print(f"    ... and {len(sessions) - 10} more")
        print()

    print(f"{Colors.HEADER}{'═' * 60}{Colors.END}\n")


async def main():
    parser = argparse.ArgumentParser(description="Session Management Dashboard")
    parser.add_argument("--prune", action="store_true", help="Prune stale sessions")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--max-age", type=int, default=60, help="Max age in minutes")
    args = parser.parse_args()

    # Initialize skill
    config = SkillConfig(
        name="session_manager",
        config={"stale_threshold_minutes": args.max_age}
    )
    skill = SessionManagerSkill(config)
    await skill.initialize()

    try:
        if args.prune:
            result = await skill.prune_sessions(
                max_age_minutes=args.max_age,
                dry_run=False
            )
            if args.json:
                print(json.dumps(result.data if result.success else {"error": result.error}, indent=2))
            else:
                if result.success:
                    data = result.data
                    print(f"\n{Colors.GREEN}✓ Pruned {data['pruned_count']} stale sessions{Colors.END}")
                    print(f"  Kept: {data['kept_count']}")
                    if data.get("errors"):
                        print(f"  Errors: {len(data['errors'])}")
                else:
                    print(f"\n{Colors.FAIL}✗ Error: {result.error}{Colors.END}")
        else:
            # Show dashboard
            stats_result = await skill.get_session_stats()
            list_result = await skill.list_sessions()

            if not stats_result.success:
                print(f"{Colors.FAIL}Error getting stats: {stats_result.error}{Colors.END}")
                return

            sessions = list_result.data.get("sessions", []) if list_result.success else []

            if args.json:
                output = {
                    "stats": stats_result.data,
                    "sessions": sessions
                }
                print(json.dumps(output, indent=2, default=str))
            else:
                print_dashboard(stats_result.data, sessions)

    finally:
        await skill.close()


if __name__ == "__main__":
    asyncio.run(main())
