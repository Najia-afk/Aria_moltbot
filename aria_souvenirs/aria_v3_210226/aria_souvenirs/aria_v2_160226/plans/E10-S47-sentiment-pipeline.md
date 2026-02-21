# S-47: Sentiment Pipeline — End-to-End Persistence & Time Series
**Epic:** E10 — Sentiment Pipeline | **Priority:** P0 | **Points:** 8 | **Phase:** 1

## Problem
The sentiment dashboard at `/sentiment` (served by `src/web/templates/sentiment.html`) shows **empty data** because no sentiment events are ever written to the `sentiment_events` table. There are 5 disconnected gaps forming a broken pipeline:

1. **`aria_mind/cognition.py` line 200–221**: Sentiment is analyzed on every `process()` call but the result is injected into the transient `context` dict and **never persisted** to any DB table.

2. **`aria_skills/api_client/__init__.py`** (1463 lines): No `store_sentiment_event()` method exists. The only sentiment storage path is `store_memory_semantic()` (line 1214), which writes to `semantic_memories` — the **wrong table**.

3. **`aria_skills/sentiment_analysis/__init__.py` line 202**: `"model": "kimi"` is hardcoded — Moonshot K2.5 is a paid model ($0.56/$2.94 per MTok). Violates Constraint #3 (models.yaml single source of truth).

4. **`aria_models/models.yaml` profiles (line 497–504)**: No `"sentiment"` profile exists. Available profiles: routing, analysis, creative, code, social.

5. **`src/api/alembic/versions/`**: Only 4 migrations exist (s37, s42, s44, s46). No migration for `sentiment_events` table — relies on `create_all()` which may silently skip.

6. **`aria_mind/cron_jobs.yaml`**: No cron job for sentiment backfill. Existing `memory_bridge` job (line 155) seeds `semantic_memories` but not `sentiment_events`.

## Root Cause
The sentiment system was built in 3 separate pieces that were never connected:

1. **Cognition** (line 127–137) creates `SentimentAnalyzer()` without `LLMSentimentClassifier` — lexicon-only, fire-and-forget into context dict. Has no `self._api` or `self._api_client` attribute to persist anything.

2. **Skill** (line 517–540) stores via `self._api.store_memory_semantic()` → writes to `semantic_memories` table (category="sentiment"). Dashboard reads from `sentiment_events` first.

3. **API router** (`analysis.py` line 523, `analyze_realtime_user_reply_sentiment`) can persist to `sentiment_events` but nothing calls it automatically — it's a manual POST endpoint.

Result: Cognition analyzes → discards. Skill stores → wrong table. API can persist → never triggered. Dashboard reads → finds nothing.

## Fix

### Fix 1: Add `store_sentiment_event()` to api_client

**File:** `aria_skills/api_client/__init__.py`
**Location:** After `store_memory_semantic` (after line 1232)

AFTER:
```python
    # ========================================
    # Sentiment Events (S-47)
    # ========================================
    async def store_sentiment_event(
        self, message: str, session_id: str = None,
        external_session_id: str = None, agent_id: str = None,
        source_channel: str = None, store_semantic: bool = True,
        metadata: Optional[Dict] = None,
    ) -> SkillResult:
        """Analyze and persist sentiment for a user message via /analysis/sentiment/reply."""
        try:
            data = {
                "message": message,
                "store_semantic": store_semantic,
            }
            if session_id:
                data["session_id"] = session_id
            if external_session_id:
                data["external_session_id"] = external_session_id
            if agent_id:
                data["agent_id"] = agent_id
            if source_channel:
                data["source_channel"] = source_channel
            if metadata:
                data["metadata"] = metadata
            resp = await self._client.post("/analysis/sentiment/reply", json=data)
            resp.raise_for_status()
            return SkillResult.ok(resp.json())
        except Exception as e:
            return SkillResult.fail(f"Failed to store sentiment event: {e}")
```

### Fix 2: Persist sentiment in cognition.py after analysis

**File:** `aria_mind/cognition.py`
**Location:** Lines 200–221, replace Step 2.1 block

BEFORE (lines 200–221):
```python
        # Step 2.1: Sentiment analysis for adaptive tone
        if self._sentiment_analyzer:
            try:
                recent_context = [m.get("content", "") for m in self.memory.recall_short(limit=3) if isinstance(m, dict)]
                sentiment = await self._sentiment_analyzer.analyze(prompt, recent_context)
                context["user_sentiment"] = sentiment.to_dict()
                context["derived_sentiment"] = {
                    "frustration": round(sentiment.frustration, 3),
                    "satisfaction": round(sentiment.satisfaction, 3),
                    "confusion": round(sentiment.confusion, 3),
                }
                if self._response_tuner:
                    context["tone_recommendation"] = self._response_tuner.select_tone(sentiment)
            except Exception as e:
                self.logger.debug(f"Sentiment analysis skipped: {e}")
```

AFTER:
```python
        # Step 2.1: Sentiment analysis for adaptive tone + persistence
        if self._sentiment_analyzer:
            try:
                recent_context = [m.get("content", "") for m in self.memory.recall_short(limit=3) if isinstance(m, dict)]
                sentiment = await self._sentiment_analyzer.analyze(prompt, recent_context)
                context["user_sentiment"] = sentiment.to_dict()
                context["derived_sentiment"] = {
                    "frustration": round(sentiment.frustration, 3),
                    "satisfaction": round(sentiment.satisfaction, 3),
                    "confusion": round(sentiment.confusion, 3),
                }
                if self._response_tuner:
                    context["tone_recommendation"] = self._response_tuner.select_tone(sentiment)

                # Persist sentiment to sentiment_events via api_client (S-47)
                if self._skills:
                    api = self._skills.get("api_client")
                    if api and api.is_available:
                        try:
                            await api.store_sentiment_event(
                                message=prompt,
                                source_channel="cognition",
                                store_semantic=True,
                            )
                        except Exception:
                            pass  # non-blocking — don't break cognition for persistence
            except Exception as e:
                self.logger.debug(f"Sentiment analysis skipped: {e}")
```

### Fix 3: Replace hardcoded "kimi" with models.yaml routing

**File:** `aria_skills/sentiment_analysis/__init__.py`
**Location:** Lines 182–210

BEFORE (line 184–188):
```python
class LLMSentimentClassifier:
    """LLM-based sentiment classification for higher accuracy."""

    def __init__(self):
        self._litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
        self._litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")
```

AFTER:
```python
class LLMSentimentClassifier:
    """LLM-based sentiment classification for higher accuracy."""

    def __init__(self, model: str = None):
        self._litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
        self._litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")
        # Resolve model from models.yaml (Constraint #3) — fallback to free model
        if model:
            self._model = model
        else:
            try:
                from aria_models import load_config
                cfg = load_config()
                profiles = cfg.get("profiles", {})
                self._model = profiles.get("sentiment", profiles.get("routing", {})).get("model", "gpt-oss-small-free")
            except Exception:
                self._model = "gpt-oss-small-free"
```

BEFORE (line 202):
```python
                    "model": "kimi",
```

AFTER:
```python
                    "model": self._model,
```

### Fix 4: Add "sentiment" profile to models.yaml

**File:** `aria_models/models.yaml`
**Location:** Line 501 (profiles section)

BEFORE:
```yaml
    "social":   { "model": "trinity-free",     "temperature": 0.8, "max_tokens": 1024 }
```

AFTER:
```yaml
    "social":     { "model": "trinity-free",     "temperature": 0.8, "max_tokens": 1024 },
    "sentiment":  { "model": "gpt-oss-small-free", "temperature": 0.2, "max_tokens": 256 }
```

### Fix 5: Add Alembic migration for sentiment_events

**File:** `src/api/alembic/versions/s47_create_sentiment_events.py` (new)

```python
"""S-47: Ensure sentiment_events table and indexes exist.

The table was defined in ORM models but had no dedicated migration.
This migration creates it idempotently for production reliability.

Revision ID: s47_create_sentiment_events
Revises: s46_openclaw_sid_idx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "s47_create_sentiment_events"
down_revision = "s46_openclaw_sid_idx"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            message_id UUID NOT NULL REFERENCES session_messages(id) ON DELETE CASCADE,
            session_id UUID REFERENCES agent_sessions(id) ON DELETE SET NULL,
            external_session_id VARCHAR(120),
            sentiment_label VARCHAR(20) NOT NULL,
            primary_emotion VARCHAR(50),
            valence FLOAT NOT NULL,
            arousal FLOAT NOT NULL,
            dominance FLOAT NOT NULL,
            confidence FLOAT NOT NULL,
            importance FLOAT DEFAULT 0.3,
            metadata JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_sentiment_event_message UNIQUE (message_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_message ON sentiment_events (message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_session ON sentiment_events (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_external ON sentiment_events (external_session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_label ON sentiment_events (sentiment_label)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_created ON sentiment_events (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_session_created ON sentiment_events (session_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_events_label_created ON sentiment_events (sentiment_label, created_at DESC)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS sentiment_events CASCADE")
```

### Fix 6: Add sentiment backfill cron job

**File:** `aria_mind/cron_jobs.yaml`
**Location:** After `memory_bridge` job (end of file)

AFTER last job:
```yaml
  # ── Sentiment Backfill (S-47: score unscored session messages) ──

  - name: sentiment_backfill
    cron: "0 30 */6 * * *"
    text: "Backfill sentiment scores for unscored session messages. Call POST /api/analysis/sentiment/backfill-messages?dry_run=false&batch_size=50 via api_client. This ensures any messages that bypassed real-time scoring get sentiment events. Log result to activity_log via api_client activity action='cron_execution' with details {'job':'sentiment_backfill','estimated_tokens':100}."
    agent: main
    session: isolated
    delivery: none
    best_effort_deliver: true
```

## Constraints
| # | Constraint | Applies | Notes |
|---|-----------|---------|-------|
| 1 | 5-layer (DB→ORM→API→api_client→Skills→Agents) | ✅ | Cognition persists via api_client→API (Fix 2). New api_client method (Fix 1) POSTs to API. No direct DB access from skill/cognition. |
| 2 | .env for secrets (zero in code) | ✅ | LiteLLM URL/key already read from env vars. No new secrets added. |
| 3 | models.yaml single source of truth | ✅ | Fix 3 removes hardcoded "kimi", resolves model from models.yaml profiles. Fix 4 adds "sentiment" profile. |
| 4 | Docker-first testing | ✅ | All changes work in Docker Compose. Alembic migration runs on container startup. |
| 5 | aria_memories only writable path | ✅ | No file writes. All persistence through API→DB. |
| 6 | No soul modification | ❌ | Does not touch soul files. |

## Dependencies
None — this is the first ticket in a fresh sprint. All referenced modules exist.

## Verification
```bash
# 1. api_client has store_sentiment_event method
grep -n "async def store_sentiment_event" aria_skills/api_client/__init__.py
# EXPECTED: line ~1236: async def store_sentiment_event(

# 2. cognition.py persists sentiment via api_client
grep -n "store_sentiment_event" aria_mind/cognition.py
# EXPECTED: line ~218: await api.store_sentiment_event(

# 3. No hardcoded "kimi" in sentiment skill
grep -n '"kimi"' aria_skills/sentiment_analysis/__init__.py
# EXPECTED: no output (0 matches)

# 4. models.yaml has sentiment profile
grep -n "sentiment" aria_models/models.yaml
# EXPECTED: line with "sentiment": { "model": "gpt-oss-small-free", ...

# 5. Alembic migration exists
ls src/api/alembic/versions/s47_create_sentiment_events.py
# EXPECTED: file exists

# 6. Cron job exists
grep -n "sentiment_backfill" aria_mind/cron_jobs.yaml
# EXPECTED: line with name: sentiment_backfill

# 7. Python syntax check
python -c "import ast; ast.parse(open('aria_mind/cognition.py').read()); print('cognition.py: OK')"
python -c "import ast; ast.parse(open('aria_skills/api_client/__init__.py').read()); print('api_client: OK')"
python -c "import ast; ast.parse(open('aria_skills/sentiment_analysis/__init__.py').read()); print('sentiment: OK')"
# EXPECTED: all OK

# 8. Full test suite
pytest tests/ -x -q 2>&1 | tail -5
# EXPECTED: tests pass or existing failures only (no new failures)
```

## Prompt for Agent
```
You are implementing S-47: Sentiment Pipeline End-to-End Persistence.

### Files to read first:
1. aria_skills/api_client/__init__.py (lines 1210-1240 — store_memory_semantic pattern)
2. aria_mind/cognition.py (lines 127-137 — sentiment init, lines 195-230 — Step 2.1)
3. aria_skills/sentiment_analysis/__init__.py (lines 182-210 — LLMSentimentClassifier)
4. aria_models/models.yaml (lines 495-510 — profiles section)
5. src/api/alembic/versions/s46_openclaw_sid_idx.py (migration pattern)
6. aria_mind/cron_jobs.yaml (full file — add new job at end)

### Constraints to obey:
- Constraint #1: All persistence through api_client → API. No direct DB imports.
- Constraint #3: No hardcoded model names. Resolve from models.yaml.
- Constraint #4: Must work in Docker Compose.

### Steps:
1. Add `store_sentiment_event()` method to api_client after `store_memory_semantic()`
2. In cognition.py Step 2.1, add persistence call after sentiment analysis
3. In LLMSentimentClassifier.__init__, accept `model` param, resolve from models.yaml
4. Replace `"model": "kimi"` with `"model": self._model`
5. Add "sentiment" profile to models.yaml profiles section
6. Create s47_create_sentiment_events.py Alembic migration
7. Add sentiment_backfill cron job to cron_jobs.yaml

### Verification:
Run all verification commands from the ticket's Verification section.
```
