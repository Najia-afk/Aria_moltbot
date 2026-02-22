#!/usr/bin/env python3
"""
Batch-retitle sessions that have no meaningful title.

Finds interactive/roundtable sessions where title is NULL, blank, or looks like
a UUID, then sets the title to the first 8 words of the first user message.

Run on the server:
    python3 /tmp/retitle_sessions.py
"""
import asyncio
import re
import httpx

BASE = "http://localhost:8000"
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)

def needs_title(s: dict) -> bool:
    """Return True if session has no meaningful title."""
    t = (s.get("title") or "").strip()
    if not t:
        return True
    if UUID_RE.match(t):
        return True
    if t.lower().startswith("untitled"):
        return True
    return False

def make_title(text: str) -> str:
    """First 8 words from text, max 60 chars."""
    words = text.split()[:8]
    title = " ".join(words)
    if len(title) > 60:
        title = title[:60] + "…"
    return title

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        # Fetch all sessions (up to 500 recent)
        resp = await client.get(f"{BASE}/api/engine/sessions?limit=200&sort=updated_at&order=desc")
        resp.raise_for_status()
        sessions = resp.json().get("sessions") or resp.json().get("items") or []

        candidates = [
            s for s in sessions
            if needs_title(s)
            and (s.get("message_count") or 0) > 0
            and s.get("session_type") in (None, "interactive", "roundtable", "cron")
        ]

        print(f"Found {len(sessions)} sessions total, {len(candidates)} need retitling")
        if not candidates:
            print("Nothing to do.")
            return

        ok = 0
        skipped = 0
        for s in candidates:
            sid = s["id"]
            try:
                msgs_resp = await client.get(
                    f"{BASE}/api/engine/sessions/{sid}/messages"
                )
                if msgs_resp.status_code == 404:
                    skipped += 1
                    continue
                msgs_resp.raise_for_status()
                msgs = msgs_resp.json().get("messages", [])
                # Find first user message
                first_user = next(
                    (m for m in msgs if (m.get("role") or "").lower() == "user"),
                    None
                )
                if not first_user:
                    skipped += 1
                    continue

                content = (first_user.get("content") or "").strip()
                if not content:
                    skipped += 1
                    continue

                title = make_title(content)
                patch = await client.patch(
                    f"{BASE}/api/engine/sessions/{sid}/title",
                    json={"title": title},
                    timeout=10,
                )
                if patch.status_code in (200, 204):
                    print(f"  ✓ {sid[:8]}…  →  {title!r}")
                    ok += 1
                else:
                    print(f"  ✗ {sid[:8]}… PATCH {patch.status_code}: {patch.text[:80]}")
                    skipped += 1
            except Exception as e:
                print(f"  ✗ {sid[:8]}… error: {e}")
                skipped += 1

        print(f"\nDone: {ok} retitled, {skipped} skipped")

if __name__ == "__main__":
    asyncio.run(main())
