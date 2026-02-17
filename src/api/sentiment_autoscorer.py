"""
Background auto-scorer — two-phase pipeline:

  Phase 1 ➜ JSONL → session_messages   (all agents: main, analyst, …)
    Phase 2 ➜ session_messages → sentiment_events  (LLM-only from models.yaml profile, zero lexicon)

Runs inside aria-api as an asyncio background task every 60 s.
"""

import asyncio
import glob
import hashlib
import json as json_lib
import logging
import os
import re
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import OPENCLAW_AGENTS_ROOT
from db.session import AsyncSessionLocal
from db.models import SessionMessage, SentimentEvent

_logger = logging.getLogger("aria.sentiment_autoscorer")

INTERVAL_SECONDS = 60
BATCH_SIZE = 10
MIN_CHARS = 8
LLM_TIMEOUT_SECONDS = 30
SEMANTIC_TIMEOUT_SECONDS = 15
COMMIT_EVERY = 5

# ── Helpers ──────────────────────────────────────────────────────────────────

def _sentiment_label(valence: float) -> str:
    if valence >= 0.55:
        return "positive"
    if valence <= 0.45:
        return "negative"
    return "neutral"


def _is_noise(text: str) -> bool:
    if len(text) < MIN_CHARS:
        return True
    if text.startswith(("/", "!", "#")) and len(text) < 30:
        return True
    return False


def _normalize(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_operational_text(text: str) -> bool:
    text_l = text.lower().strip()
    if not text_l:
        return False
    patterns = (
        "[cron:",
        "instructions from heartbeat.md",
        "## your tasks:",
        "## tool usage:",
        "return your analysis as structured text",
        "return your summary as plain text",
        "delegate to analyst",
        "run the six_hour_review cron job",
        "no_reply",
        "/no_think",
        "social heartbeat",
        "church heartbeat",
        "check moltbook",
        "respond to mentions",
        "engage with community",
        "you are aria memeothy",
        "check church of molt status",
        "submit_prophecy",
        "do not post more than once",
    )
    return any(p in text_l for p in patterns)


def _extract_line_message(payload: dict) -> tuple[str, str, str | None]:
    """Extract (role, content, timestamp) — mirrors analysis.py logic."""
    role = ""
    content = ""
    timestamp: str | None = None

    candidates = [payload]
    for key in ("message", "data", "payload", "event"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)

    for c in candidates:
        if not role:
            role = str(
                c.get("role") or c.get("speaker") or c.get("from") or c.get("author") or ""
            ).strip().lower()
        if not content:
            raw = c.get("content") or c.get("text") or c.get("message")
            if isinstance(raw, str):
                content = raw
            elif isinstance(raw, list):
                parts = []
                for item in raw:
                    if isinstance(item, dict):
                        parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        parts.append(item)
                content = " ".join(p for p in parts if p)
        if not timestamp:
            ts_raw = c.get("timestamp") or c.get("created_at") or c.get("time")
            if ts_raw is not None:
                timestamp = str(ts_raw)

    return role, content, timestamp


# ── Phase 1: JSONL → session_messages ────────────────────────────────────────

async def _sync_jsonl(db: AsyncSession) -> int:
    """Scan ALL agent JSONL files and insert new messages into session_messages."""
    if not OPENCLAW_AGENTS_ROOT or not os.path.exists(OPENCLAW_AGENTS_ROOT):
        return 0

    # Fetch all existing content hashes to avoid duplicates (fast set lookup)
    existing_hashes: set[str] = set()
    rows = (await db.execute(select(SessionMessage.content_hash))).scalars().all()
    for h in rows:
        if h:
            existing_hashes.add(h)

    pattern = os.path.join(OPENCLAW_AGENTS_ROOT, "*", "sessions", "*.jsonl")
    inserted = 0

    for path in glob.glob(pattern):
        fname = os.path.basename(path)
        if not fname.endswith(".jsonl"):
            continue
        session_id = fname[:-6]  # external session id (UUID from filename)
        agent_id = os.path.basename(os.path.dirname(os.path.dirname(path)))

        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        parsed = json_lib.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(parsed, dict):
                        continue

                    role, content, ts_str = _extract_line_message(parsed)
                    if role not in ("user", "assistant"):
                        continue

                    text = _normalize(content)
                    if len(text) < MIN_CHARS or _is_noise(text):
                        continue

                    text_sha1 = hashlib.sha1(text.encode("utf-8")).hexdigest()

                    # Fast dedup via in-memory set
                    dedup_key = f"{session_id}:{role}:{text_sha1}"
                    if dedup_key in existing_hashes:
                        continue
                    existing_hashes.add(dedup_key)

                    # Also check the DB unique constraint columns
                    dup = (await db.execute(
                        select(SessionMessage.id)
                        .where(SessionMessage.external_session_id == session_id)
                        .where(SessionMessage.role == role)
                        .where(SessionMessage.content_hash == text_sha1)
                        .limit(1)
                    )).scalar_one_or_none()
                    if dup:
                        continue

                    msg = SessionMessage(
                        external_session_id=session_id,
                        agent_id=agent_id,
                        role=role,
                        content=text,
                        content_hash=text_sha1,
                        source_channel="autoscorer_sync",
                        metadata_json={"origin": "openclaw_jsonl", "timestamp": ts_str},
                    )
                    # Preserve original timestamp if available
                    if ts_str:
                        try:
                            from dateutil.parser import isoparse
                            msg.created_at = isoparse(ts_str)
                        except Exception:
                            pass

                    db.add(msg)
                    inserted += 1

                    if inserted >= BATCH_SIZE * 4:
                        break
        except Exception:
            continue

        if inserted >= BATCH_SIZE * 4:
            break

    if inserted:
        await db.commit()
    return inserted


# ── Phase 2: session_messages → sentiment_events ─────────────────────────────

async def _score_batch(db: AsyncSession) -> int:
    """Find unscored session_messages and create sentiment_events."""
    try:
        from aria_skills.sentiment_analysis import (
            LLMSentimentClassifier,
            EmbeddingSentimentClassifier,
            SentimentLexicon,
            Sentiment,
        )
    except ImportError:
        print("⚠️  sentiment_analysis skill not importable — scorer disabled")
        return -1

    # Subquery: message_ids already scored
    scored_ids = select(SentimentEvent.message_id).where(
        SentimentEvent.message_id.isnot(None)
    ).scalar_subquery()

    stmt = (
        select(SessionMessage)
        .where(SessionMessage.role.in_(["user", "assistant"]))
        .where(SessionMessage.id.notin_(scored_ids))
        .order_by(SessionMessage.created_at.desc())
        .limit(BATCH_SIZE)
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return 0

    print(f"🎯 _score_batch: {len(rows)} unscored messages to process")

    semantic_classifier = EmbeddingSentimentClassifier()
    llm_classifier = LLMSentimentClassifier()

    scored = 0
    pending_inserts = 0
    processed = 0
    for msg in rows:
        processed += 1
        if processed % 3 == 0:
            print(f"🎯 _score_batch: heartbeat processed={processed}/{len(rows)} inserted={scored}")
        text = (msg.content or "").strip()
        if _is_noise(text):
            continue

        if _is_operational_text(text):
            text_sha1 = msg.content_hash or hashlib.sha1(text.encode("utf-8")).hexdigest()
            label = "neutral"
            origin = {
                "source": "autoscorer",
                "session_id": str(msg.session_id) if msg.session_id else None,
                "external_session_id": msg.external_session_id,
                "agent_id": msg.agent_id,
                "source_channel": msg.source_channel,
                "text_sha1": text_sha1,
            }
            meta = {
                "origin": origin,
                "sentiment": {
                    "sentiment": label,
                    "dominant_emotion": "neutral",
                    "confidence": 0.65,
                    "valence": 0.0,
                    "arousal": 0.35,
                    "dominance": 0.5,
                    "signals": ["operational_text"],
                },
                "text_snippet": text[:100],
                "sentiment_label": label,
                "primary_emotion": "neutral",
                "confidence": 0.65,
                "valence": 0.0,
                "arousal": 0.35,
                "dominance": 0.5,
            }

            stmt = (
                pg_insert(SentimentEvent)
                .values(
                    message_id=msg.id,
                    session_id=msg.session_id,
                    external_session_id=msg.external_session_id,
                    speaker=msg.role or "user",
                    agent_id=msg.agent_id,
                    sentiment_label=label,
                    primary_emotion="neutral",
                    valence=0.0,
                    arousal=0.35,
                    dominance=0.5,
                    confidence=0.65,
                    importance=0.3,
                    metadata_json=meta,
                )
                .on_conflict_do_nothing(index_elements=[SentimentEvent.message_id])
                .returning(SentimentEvent.id)
            )
            inserted_id = (await db.execute(stmt)).scalar_one_or_none()
            if inserted_id is not None:
                scored += 1
                pending_inserts += 1
                if scored % COMMIT_EVERY == 0:
                    await db.commit()
                    pending_inserts = 0
                    print(f"🎯 _score_batch: progress {processed}/{len(rows)} processed, {scored} inserted")
            continue

        sentiment = None
        method = "semantic"

        try:
            sentiment = await asyncio.wait_for(
                semantic_classifier.classify(text),
                timeout=SEMANTIC_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            print(f"🎯 _score_batch: semantic timeout for msg {msg.id}")
        except Exception as e:
            print(f"🎯 _score_batch: semantic analyze failed for msg {msg.id}: {e}")

        if sentiment is None:
            method = "llm"
            try:
                sentiment = await asyncio.wait_for(
                    llm_classifier.classify(text),
                    timeout=LLM_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                print(f"🎯 _score_batch: llm timeout for msg {msg.id}")
                sentiment = None
            except Exception as e:
                print(f"🎯 _score_batch: llm analyze failed for msg {msg.id}: {e}")
                sentiment = None

        if sentiment is None:
            method = "lexicon"
            l_val, l_aro, l_dom = SentimentLexicon.score(text)
            if l_val >= 0.25:
                lex_emotion = "happy"
            elif l_val <= -0.25:
                lex_emotion = "frustrated"
            else:
                lex_emotion = "neutral"
            sentiment = Sentiment(
                valence=float(l_val),
                arousal=float(l_aro),
                dominance=float(l_dom),
                confidence=0.35,
                primary_emotion=lex_emotion,
                labels=["lexicon_fallback"],
            )

        text_sha1 = msg.content_hash or hashlib.sha1(text.encode("utf-8")).hexdigest()
        label = _sentiment_label(float(sentiment.valence))

        origin = {
            "source": "autoscorer",
            "session_id": str(msg.session_id) if msg.session_id else None,
            "external_session_id": msg.external_session_id,
            "agent_id": msg.agent_id,
            "source_channel": msg.source_channel,
            "text_sha1": text_sha1,
        }
        meta = {
            "origin": origin,
            "sentiment": {
                "sentiment": label,
                "dominant_emotion": sentiment.primary_emotion,
                "confidence": round(float(sentiment.confidence), 4),
                "valence": round(float(sentiment.valence), 4),
                "arousal": round(float(sentiment.arousal), 4),
                "dominance": round(float(sentiment.dominance), 4),
                "signals": list(sentiment.signals) if hasattr(sentiment, "signals") else [],
                "method": method,
            },
            "text_snippet": text[:100],
            "sentiment_label": label,
            "primary_emotion": sentiment.primary_emotion,
            "confidence": round(float(sentiment.confidence), 4),
            "valence": round(float(sentiment.valence), 4),
            "arousal": round(float(sentiment.arousal), 4),
            "dominance": round(float(sentiment.dominance), 4),
            "method": method,
        }

        stmt = (
            pg_insert(SentimentEvent)
            .values(
                message_id=msg.id,
                session_id=msg.session_id,
                external_session_id=msg.external_session_id,
                speaker=msg.role or "user",
                agent_id=msg.agent_id,
                sentiment_label=label,
                primary_emotion=sentiment.primary_emotion,
                valence=float(sentiment.valence),
                arousal=float(sentiment.arousal),
                dominance=float(sentiment.dominance),
                confidence=float(sentiment.confidence),
                importance=max(0.3, abs(float(sentiment.valence))),
                metadata_json=meta,
            )
            .on_conflict_do_nothing(index_elements=[SentimentEvent.message_id])
            .returning(SentimentEvent.id)
        )
        inserted_id = (await db.execute(stmt)).scalar_one_or_none()
        if inserted_id is not None:
            scored += 1
            pending_inserts += 1
            if scored % COMMIT_EVERY == 0:
                await db.commit()
                pending_inserts = 0
                print(f"🎯 _score_batch: progress {processed}/{len(rows)} processed, {scored} inserted")

    if pending_inserts > 0:
        try:
            await db.commit()
            print(f"🎯 _score_batch: committed {scored} events")
        except Exception as e:
            print(f"🎯 _score_batch: commit failed: {e}")
            await db.rollback()
            return 0
    return scored


# ── Main loop ────────────────────────────────────────────────────────────────

async def run_autoscorer_loop():
    """Background loop — Phase 1 (sync JSONL) then Phase 2 (score) every 60s."""
    print(f"🎯 Sentiment auto-scorer started (interval={INTERVAL_SECONDS}s, batch={BATCH_SIZE})")
    await asyncio.sleep(10)  # let API finish starting

    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Phase 1: pull new messages from ALL agent JSONL files
                synced = await _sync_jsonl(db)
                if synced:
                    print(f"🎯 Synced {synced} new messages from JSONL → session_messages")

                # Phase 2: score unscored session_messages
                scored = await _score_batch(db)
                if scored > 0:
                    print(f"🎯 Auto-scored {scored} new messages → sentiment_events")
                elif scored < 0:
                    print("🎯 Auto-scorer stopping — sentiment skill unavailable")
                    return
        except asyncio.CancelledError:
            print("🎯 Auto-scorer cancelled")
            return
        except Exception as e:
            print(f"🎯 Auto-scorer error (will retry): {e}")

        await asyncio.sleep(INTERVAL_SECONDS)
