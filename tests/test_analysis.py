"""Analysis endpoint tests (sentiment, patterns, compression)."""
import pytest


class TestSentimentAnalysis:
    def test_analyze_message(self, api):
        r = api.post("/analysis/sentiment/message", json={
            "content": "I love this feature, it works great!",
        })
        assert r.status_code in (200, 422)

    def test_backfill_sessions(self, api):
        r = api.post("/analysis/sentiment/backfill-sessions", json={"max_sessions": 5, "dry_run": True})
        assert r.status_code in (200, 422)

    def test_analyze_conversation(self, api):
        r = api.post("/analysis/sentiment/conversation", json={
            "messages": [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        })
        assert r.status_code in (200, 422)

    def test_analyze_reply(self, api):
        r = api.post("/analysis/sentiment/reply", json={
            "user_message": "I'm frustrated with this bug",
            "assistant_reply": "I understand, let me help fix that",
        })
        assert r.status_code in (200, 422)

    def test_backfill_messages(self, api):
        r = api.post("/analysis/sentiment/backfill-messages", json={"limit": 5, "dry_run": True})
        assert r.status_code in (200, 422)

    def test_sentiment_history(self, api):
        r = api.get("/analysis/sentiment/history")
        assert r.status_code == 200

    def test_seed_references(self, api):
        r = api.post("/analysis/sentiment/seed-references")
        assert r.status_code == 200

    def test_feedback(self, api):
        r = api.post("/analysis/sentiment/feedback", json={
            "event_id": "00000000-0000-0000-0000-000000000001",
            "message_id": "test-msg-id",
            "feedback": "positive",
        })
        assert r.status_code in (400, 404)

    def test_auto_promote(self, api):
        r = api.post("/analysis/sentiment/auto-promote")
        assert r.status_code == 200

    def test_cleanup_placeholders(self, api):
        r = api.post("/analysis/sentiment/cleanup-placeholders")
        assert r.status_code == 200


class TestPatternAnalysis:
    def test_detect_patterns(self, api):
        r = api.post("/analysis/patterns/detect", json={
            "window_hours": 24,
        })
        assert r.status_code in (200, 422)

    def test_pattern_history(self, api):
        r = api.get("/analysis/patterns/history")
        assert r.status_code == 200


class TestCompression:
    def test_run_compression(self, api):
        r = api.post("/analysis/compression/run", json={
            "memories": [
                {"key": "m1", "content": "First memory item"},
                {"key": "m2", "content": "Second memory item"},
                {"key": "m3", "content": "Third memory item"},
                {"key": "m4", "content": "Fourth memory item"},
                {"key": "m5", "content": "Fifth memory item"},
            ]
        })
        assert r.status_code in (200, 422)

    def test_compression_history(self, api):
        r = api.get("/analysis/compression/history")
        assert r.status_code == 200

    def test_auto_compression(self, api):
        r = api.post("/analysis/compression/auto-run", json={"raw_limit": 5, "dry_run": True})
        assert r.status_code in (200, 422)

    def test_seed_memories(self, api):
        r = api.post("/analysis/seed-memories")
        assert r.status_code == 200
