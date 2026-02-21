#!/usr/bin/env python3
"""
Session Management Dashboard
Lightweight CLI dashboard for monitoring OpenClaw sessions.
"""

import json
import subprocess
from datetime import datetime
from typing import Dict, List, Any

class SessionDashboard:
    """Dashboard for viewing and managing OpenClaw sessions."""
    
    def __init__(self):
        self.sessions: List[Dict] = []
        self.stats: Dict = {}
    
    def fetch_sessions(self, active_only: bool = True) -> List[Dict]:
        """Fetch sessions using session_manager skill."""
        try:
            result = subprocess.run(
                ['python3', '/root/.openclaw/workspace/skills/run_skill.py',
                 'session_manager', 'list_sessions', '{}'],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            sessions = data.get('data', {}).get('sessions', [])
            if active_only:
                sessions = [s for s in sessions if s.get('status') == 'active']
            self.sessions = sessions
            return sessions
        except Exception as e:
            print(f"⚠️  Error fetching sessions: {e}")
            return []
    
    def get_session_stats(self) -> Dict:
        """Get aggregated session statistics."""
        try:
            result = subprocess.run(
                ['python3', '/root/.openclaw/workspace/skills/run_skill.py',
                 'session_manager', 'get_session_stats', '{}'],
                capture_output=True, text=True, timeout=10
            )
            data = json.loads(result.stdout)
            self.stats = data.get('data', {})
            return self.stats
        except Exception as e:
            print(f"⚠️  Error fetching stats: {e}")
            return {}
    
    def prune_stale(self, max_age_minutes: int = 60) -> int:
        """Prune stale sessions. Returns count pruned."""
        try:
            result = subprocess.run(
                ['python3', '/root/.openclaw/workspace/skills/run_skill.py',
                 'session_manager', 'prune_sessions',
                 json.dumps({"max_age_minutes": max_age_minutes})],
                capture_output=True, text=True, timeout=30
            )
            data = json.loads(result.stdout)
            return data.get('data', {}).get('pruned_count', 0)
        except Exception as e:
            print(f"⚠️  Error pruning: {e}")
            return 0
    
    def display(self):
        """Display dashboard in terminal."""
        print("\n" + "="*60)
        print(f"⚡ OpenClaw Session Dashboard — {datetime.utcnow().strftime('%H:%M:%S')} UTC")
        print("="*60)
        
        # Stats
        stats = self.get_session_stats()
        if stats:
            print(f"\n📊  Sessions: {stats.get('total', 0)} total | "
                  f"{stats.get('active', 0)} active | "
                  f"{stats.get('idle', 0)} idle | "
                  f"{stats.get('stale', 0)} stale")
        
        # Session list
        sessions = self.fetch_sessions(active_only=True)
        if sessions:
            print(f"\n🟢 Active Sessions ({len(sessions)}):")
            print("-" * 60)
            for s in sessions[:10]:  # Limit to 10
                age = s.get('age_minutes', 0)
                agent = s.get('agent_id', 'unknown')[:20]
                print(f"  {s.get('id', 'N/A')[:8]}...  {agent:20}  {age:5.1f}m  {s.get('status', '?'):8}")
            if len(sessions) > 10:
                print(f"  ... and {len(sessions) - 10} more")
        else:
            print("\n  No active sessions found.")
        
        print("\n" + "="*60)
        print("Commands: refresh | prune [minutes] | exit")
        print("="*60 + "\n")


def main():
    """Run dashboard in loop or once."""
    import sys
    
    dash = SessionDashboard()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        dash.display()
        return
    
    # Single run for now (can add interactive loop later)
    dash.display()
    
    # Auto-prune stale sessions > 60 min
    pruned = dash.prune_stale(max_age_minutes=60)
    if pruned:
        print(f"🧹 Pruned {pruned} stale session(s)")


if __name__ == "__main__":
    main()
