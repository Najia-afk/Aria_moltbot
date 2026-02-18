"""
Analysis endpoints — Sentiment, Patterns, Compression.

Provides REST endpoints that integrate with
aria_skills/{sentiment_analysis,pattern_recognition,memory_compression}.
All heavy lifting is done in the skills; these endpoints serve as a thin
HTTP façade for the web dashboard and external callers.
"""

import os
import glob
import hashlib
import json as json_lib
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ARIA_AGENTS_ROOT
from db.models import (
    ActivityLog,
    AgentSession,
    SemanticMemory,
    SentimentEvent,
    SessionMessage,
    Thought,
)
from deps import get_db

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

router = APIRouter(prefix="/analysis", tags=["Analysis"])

_TEST_TEXT_PATTERN = re.compile(
    r"\b(dummy|abc123|lorem ipsum|live test post|post 42|sample data|placeholder|test_message|test_post)\b",
    re.IGNORECASE,
)
_TRANSCRIPT_SPEAKER_RE = re.compile(
    r"(?mi)^\s*(system|assistant|user|you|aria|bot|human|operator)\s*:\s+"
)
_TRANSCRIPT_JSON_ROLE_RE = re.compile(
    r'"role"\s*:\s*"(system|assistant|user)"',
    re.IGNORECASE,
)
_TRANSCRIPT_TIME_RE = re.compile(
    r"(?mi)^\s*(?:\[?\w{3}\s+\d{4}-\d{2}-\d{2}.*\]?|\d{1,2}:\d{2})\s*$"
)


async def _generate_embedding(text: str) -> list[float]:
    """Generate embedding via LiteLLM embedding endpoint.
    Falls back to zero-vector if Ollama/LiteLLM is unreachable (timeout 5s).
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/embeddings",
            json={"model": "nomic-embed-text", "input": text},
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


def _sentiment_label_from_valence(valence: float) -> str:
    if valence >= 0.25:
        return "positive"
    if valence <= -0.25:
        return "negative"
    return "neutral"


# Attribution prefix injected by gateway:
# [Telegram Test Toust (@TestToust) id:1643801012 2026-02-16 16:10 UTC] ...
# [Mon 2026-02-16 21:21 UTC] You said ...
# System: [2026-02-16 20:05:34 UTC] Cron: ...
_ATTRIBUTION_PREFIX_RE = re.compile(
    r"^(?:"
    r"\[(?:Telegram|Discord|Webchat|IRC|Slack)\s[^\]]+\]\s*"  # [Telegram ... UTC]
    r"|\[(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s[^\]]+\]\s*"       # [Mon 2026-... UTC]
    r"|\[\d{4}-\d{2}-\d{2}[^\]]*\]\s*"                     # [2026-02-16 ...]
    r"|System:\s*\[[^\]]+\]\s*(?:Cron:\s*)?"                  # System: [...] Cron:
    r"|\[cron:[^\]]+\]\s*"                                    # [cron:uuid ...]
    r"|\[message_id:\s*\d+\]\s*"                              # [message_id: 421]
    r")",
    re.IGNORECASE,
)


def _strip_attribution(text: str) -> str:
    """Remove gateway attribution prefix(es) from user text."""
    t = text.strip()
    for _ in range(5):  # up to 5 nested prefixes
        m = _ATTRIBUTION_PREFIX_RE.match(t)
        if not m:
            break
        t = t[m.end():].strip()
    # Also strip trailing [message_id: NNN]
    t = re.sub(r"\s*\[message_id:\s*\d+\]\s*$", "", t).strip()
    return t


def _normalize_user_text(text: str) -> str:
    stripped = _strip_attribution(text)
    return re.sub(r"\s+", " ", stripped).strip()


# Cron/system prompt patterns — these are automated instructions, not user sentiment
_CRON_SYSTEM_RE = re.compile(
    r"^(?:"
    r"read heartbeat\.md"
    r"|check moltbook"
    r"|bridge activity data"
    r"|\/no_think"
    r"|run (full |)health check"
    r"|cron[: ]"
    r"|a background task"
    r"|summarize this naturally"
    r"|ping litellm"
    r"|seed.memor"
    r")",
    re.IGNORECASE,
)


def _is_noise_text(text: str) -> bool:
    lowered = _strip_attribution(text or "").lower().strip()
    if not lowered:
        return True
    if _TEST_TEXT_PATTERN.search(lowered):
        return True
    if len(lowered) > 8 and lowered[0] in "[{" and '"role"' in lowered and '"content"' in lowered:
        return True
    # Cron/system prompts: automated instructions, not user sentiment
    if _CRON_SYSTEM_RE.search(lowered):
        return True
    return False


def _looks_like_transcript(text: str) -> bool:
    sample = str(text or "").replace("\r\n", "\n")
    if not sample:
        return False

    speaker_hits = len(_TRANSCRIPT_SPEAKER_RE.findall(sample))
    json_role_hits = len(_TRANSCRIPT_JSON_ROLE_RE.findall(sample))
    time_hits = len(_TRANSCRIPT_TIME_RE.findall(sample))
    line_count = sample.count("\n") + 1

    if speaker_hits >= 2:
        return True
    if json_role_hits >= 2:
        return True
    if speaker_hits >= 1 and time_hits >= 1 and line_count >= 3:
        return True
    return False


def _extract_line_message(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """Extract (role, content, timestamp) from various JSONL shapes."""
    role = ""
    content = ""
    timestamp: str | None = None

    candidates: list[dict[str, Any]] = [payload]
    for key in ("message", "data", "payload", "event"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)

    for candidate in candidates:
        if not role:
            role = str(
                candidate.get("role")
                or candidate.get("speaker")
                or candidate.get("from")
                or candidate.get("author")
                or ""
            ).strip().lower()

        if not content:
            raw_content = candidate.get("content") or candidate.get("text") or candidate.get("message")
            if isinstance(raw_content, str):
                content = raw_content
            elif isinstance(raw_content, list):
                # Content may be stored as [{"type":"text","text":"..."},...]
                parts = []
                for item in raw_content:
                    if isinstance(item, dict):
                        parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        parts.append(item)
                content = " ".join(p for p in parts if p)

        if not timestamp:
            ts_raw = candidate.get("timestamp") or candidate.get("created_at") or candidate.get("time")
            if ts_raw is not None:
                timestamp = str(ts_raw)

    return role, content, timestamp


def _extract_user_messages_from_jsonl(
    session_ids: set[str],
    max_messages: int,
    min_chars: int,
) -> list[dict[str, Any]]:
    extracted: list[dict[str, Any]] = []
    if not ARIA_AGENTS_ROOT or not os.path.exists(ARIA_AGENTS_ROOT):
        return extracted

    pattern = os.path.join(ARIA_AGENTS_ROOT, "*", "sessions", "*.jsonl")
    for path in glob.glob(pattern):
        if len(extracted) >= max_messages:
            break

        file_name = os.path.basename(path)
        if not file_name.endswith(".jsonl"):
            continue

        session_id = file_name[:-6]
        if session_ids and session_id not in session_ids:
            continue

        agent_id = os.path.basename(os.path.dirname(os.path.dirname(path)))

        try:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    if len(extracted) >= max_messages:
                        break

                    raw = line.strip()
                    if not raw:
                        continue

                    try:
                        parsed = json_lib.loads(raw)
                    except Exception:
                        continue
                    if not isinstance(parsed, dict):
                        continue

                    role, content, timestamp = _extract_line_message(parsed)
                    if role not in ("user", "assistant"):
                        continue

                    text = _normalize_user_text(content)
                    if len(text) < min_chars or _is_noise_text(text):
                        continue

                    extracted.append(
                        {
                            "session_id": session_id,
                            "agent_id": agent_id,
                            "role": role,
                            "text": text,
                            "timestamp": timestamp,
                            "origin": "legacy_jsonl",
                        }
                    )
        except Exception:
            continue

    return extracted


def _build_sentiment_metadata(sentiment: Any, text: str, origin: dict[str, Any]) -> dict[str, Any]:
    sentiment_label = _sentiment_label_from_valence(float(sentiment.valence))
    return {
        "sentiment": {
            "sentiment": sentiment_label,
            "dominant_emotion": sentiment.primary_emotion,
            "confidence": sentiment.confidence,
            "signals": sentiment.labels or [],
            "valence": sentiment.valence,
            "arousal": sentiment.arousal,
            "dominance": sentiment.dominance,
        },
        "sentiment_label": sentiment_label,
        "valence": sentiment.valence,
        "arousal": sentiment.arousal,
        "dominance": sentiment.dominance,
        "confidence": sentiment.confidence,
        "labels": sentiment.labels or [],
        "primary_emotion": sentiment.primary_emotion,
        "text_snippet": text[:200],
        "origin": origin,
    }


def _is_placeholder_sentiment_row(content: str, importance: float | None, metadata: dict[str, Any] | None) -> bool:
    meta = metadata or {}
    sent = meta.get("sentiment") if isinstance(meta.get("sentiment"), dict) else {}

    label = str(sent.get("sentiment") or meta.get("sentiment_label") or "").lower()
    valence = sent.get("valence", meta.get("valence"))
    confidence = sent.get("confidence", meta.get("confidence", 0))
    text_snippet = meta.get("text_snippet")

    try:
        valence_num = float(valence)
    except (TypeError, ValueError):
        valence_num = 0.0
    try:
        confidence_num = float(confidence)
    except (TypeError, ValueError):
        confidence_num = 0.0
    try:
        importance_num = float(importance or 0)
    except (TypeError, ValueError):
        importance_num = 0.0

    content_text = str(content or "")
    snippet_text = text_snippet if isinstance(text_snippet, str) else str(text_snippet)

    is_known_template = content_text.startswith("Sentiment: neutral (v=0.00, a=0.00, d=0.00)")
    looks_structured_payload = snippet_text.strip().startswith("{") or snippet_text.strip().startswith("[")

    return (
        label == "neutral"
        and abs(valence_num) < 1e-9
        and confidence_num <= 0.05
        and importance_num <= 0.3
        and is_known_template
        and looks_structured_payload
    )


# ── Request / Response Schemas ──────────────────────────────────────────────

class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    context: list[str] | None = None
    store: bool = True


class ConversationSentimentRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(..., min_items=1)
    store: bool = True


class PatternDetectionRequest(BaseModel):
    memories: list[dict[str, Any]] | None = None
    min_confidence: float = Field(0.3, ge=0, le=1)
    store: bool = True


class CompressionRequest(BaseModel):
    memories: list[dict[str, Any]] = Field(..., min_items=5)
    store_semantic: bool = True


class SessionCompressionRequest(BaseModel):
    hours_back: int = Field(6, ge=1, le=48)


class SentimentBackfillRequest(BaseModel):
    max_sessions: int = Field(200, ge=1, le=5000)
    max_messages: int = Field(300, ge=1, le=5000)
    min_chars: int = Field(8, ge=1, le=500)
    dry_run: bool = True
    store_semantic: bool = True


class RealtimeSentimentRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10_000)
    session_id: str | None = None
    conversation_id: str | None = None
    external_session_id: str | None = None
    agent_id: str | None = None
    source_channel: str | None = None
    metadata: dict[str, Any] | None = None
    store_semantic: bool = True


class SentimentBackfillMessagesRequest(BaseModel):
    limit: int = Field(500, ge=1, le=5000)
    dry_run: bool = True
    store_semantic: bool = False


# ── Sentiment Endpoints ────────────────────────────────────────────────────

@router.post("/sentiment/message")
async def analyze_message_sentiment(req: SentimentRequest, db: AsyncSession = Depends(get_db)):
    """Analyze sentiment of a single message."""
    try:
        from aria_skills.sentiment_analysis import (
            SentimentAnalyzer, LLMSentimentClassifier, EmbeddingSentimentClassifier, ResponseTuner,
        )

        classifier = LLMSentimentClassifier()
        emb_classifier = EmbeddingSentimentClassifier()
        analyzer = SentimentAnalyzer(
            llm_classifier=classifier,
            embedding_classifier=emb_classifier,
        )
        sentiment = await analyzer.analyze(req.text, req.context)
        tuner = ResponseTuner()
        tone = tuner.select_tone(sentiment)

        result = {
            "sentiment": sentiment.to_dict(),
            "derived": {
                "frustration": round(sentiment.frustration, 3),
                "satisfaction": round(sentiment.satisfaction, 3),
                "confusion": round(sentiment.confusion, 3),
            },
            "tone_recommendation": tone,
        }

        if req.store:
            content_text = (f"Sentiment: {sentiment.primary_emotion} "
                            f"(v={sentiment.valence:.2f}, a={sentiment.arousal:.2f}, d={sentiment.dominance:.2f})")

            try:
                embedding = await _generate_embedding(content_text)
            except Exception:
                embedding = [0.0] * 768
            mem = SemanticMemory(
                content=content_text,
                summary=content_text[:100],
                category="sentiment",
                embedding=embedding,
                importance=max(0.3, abs(sentiment.valence)),
                source="analysis_api",
                metadata_json=_build_sentiment_metadata(sentiment, req.text, {"source": "analysis_api"}),
            )
            db.add(mem)
            await db.commit()
            await db.refresh(mem)
            result["stored_id"] = str(mem.id)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/backfill-sessions")
async def backfill_sentiment_from_sessions(
    req: SentimentBackfillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Retro-populate sentiment memories from real user messages in session JSONL."""
    try:
        from aria_skills.sentiment_analysis import (
            SentimentAnalyzer, LLMSentimentClassifier, EmbeddingSentimentClassifier,
        )

        session_stmt = (
            select(AgentSession)
            .where(AgentSession.session_type.like("legacy%"))
            .where(AgentSession.session_type != "legacy_heartbeat")
            .order_by(AgentSession.started_at.desc())
            .limit(req.max_sessions)
        )
        sessions = (await db.execute(session_stmt)).scalars().all()

        session_ids: set[str] = set()
        for sess in sessions:
            meta = sess.metadata_json or {}
            sid = str(meta.get("aria_session_id") or meta.get("session_id") or "").strip()
            if sid:
                session_ids.add(sid)

        messages = _extract_user_messages_from_jsonl(
            session_ids=session_ids,
            max_messages=req.max_messages,
            min_chars=req.min_chars,
        )

        if not messages:
            return {
                "dry_run": req.dry_run,
                "sessions_scanned": len(sessions),
                "session_ids_found": len(session_ids),
                "messages_found": 0,
                "stored": 0,
                "skipped": 0,
                "note": "No user messages found in session JSONL (check ARIA_AGENTS_ROOT mount and session files).",
            }

        classifier = LLMSentimentClassifier()
        emb_classifier = EmbeddingSentimentClassifier()
        analyzer = SentimentAnalyzer(
            llm_classifier=classifier,
            embedding_classifier=emb_classifier,
        )

        stored = 0
        skipped = 0
        sample: list[dict[str, Any]] = []

        for msg in messages:
            text = msg["text"]
            text_sha1 = hashlib.sha1(text.encode("utf-8")).hexdigest()
            session_id = msg.get("session_id")
            agent_id = msg.get("agent_id")
            msg_role = msg.get("role", "user")

            # Dedup by content hash in session_messages
            existing_msg = (await db.execute(
                select(SessionMessage)
                .where(SessionMessage.content_hash == text_sha1)
                .where(SessionMessage.role == msg_role)
                .limit(1)
            )).scalar_one_or_none()

            if existing_msg:
                # Check if sentiment_event already exists for this message
                existing_event = (await db.execute(
                    select(SentimentEvent.id)
                    .where(SentimentEvent.message_id == existing_msg.id)
                    .limit(1)
                )).scalar_one_or_none()
                if existing_event:
                    skipped += 1
                    continue

            sentiment = await analyzer.analyze(text)
            sentiment_label = _sentiment_label_from_valence(float(sentiment.valence))

            if len(sample) < 5:
                sample.append(
                    {
                        "session_id": session_id,
                        "sentiment": sentiment_label,
                        "emotion": sentiment.primary_emotion,
                        "confidence": round(float(sentiment.confidence), 3),
                        "text": text[:120],
                    }
                )

            if req.dry_run:
                stored += 1
                continue

            # Resolve internal session_id from external session id
            parsed_session_id: uuid.UUID | None = None
            if session_id:
                session_match = (await db.execute(
                    select(AgentSession.id)
                    .where(
                        (AgentSession.metadata_json["aria_session_id"].astext == session_id)
                        | (AgentSession.metadata_json["external_session_id"].astext == session_id)
                    )
                    .order_by(AgentSession.started_at.desc())
                    .limit(1)
                )).scalar_one_or_none()
                if session_match:
                    parsed_session_id = session_match

            # Parse original timestamp from JSONL
            original_ts: datetime | None = None
            raw_ts = msg.get("timestamp")
            if raw_ts:
                try:
                    from dateutil.parser import isoparse
                    original_ts = isoparse(raw_ts)
                except Exception:
                    pass

            # Create SessionMessage if not exists
            if existing_msg is None:
                existing_msg = SessionMessage(
                    session_id=parsed_session_id,
                    external_session_id=session_id,
                    agent_id=agent_id,
                    role=msg_role,
                    content=text,
                    content_hash=text_sha1,
                    source_channel="legacy_backfill",
                    metadata_json={"origin": "legacy_jsonl", "timestamp": msg.get("timestamp")},
                )
                if original_ts:
                    existing_msg.created_at = original_ts
                db.add(existing_msg)
                await db.flush()

            # Create SentimentEvent
            origin = {
                "source": "session_backfill",
                "session_id": session_id,
                "agent_id": agent_id,
                "timestamp": msg.get("timestamp"),
                "text_sha1": text_sha1,
            }
            event = SentimentEvent(
                message_id=existing_msg.id,
                session_id=parsed_session_id,
                external_session_id=session_id,
                speaker=msg_role,
                agent_id=agent_id,
                sentiment_label=sentiment_label,
                primary_emotion=sentiment.primary_emotion,
                valence=float(sentiment.valence),
                arousal=float(sentiment.arousal),
                dominance=float(sentiment.dominance),
                confidence=float(sentiment.confidence),
                importance=max(0.3, abs(float(sentiment.valence))),
                metadata_json=_build_sentiment_metadata(sentiment, text, origin),
            )
            if original_ts:
                event.created_at = original_ts
            db.add(event)

            # Also store semantic memory for search
            if req.store_semantic:
                try:
                    embedding = await _generate_embedding(text)
                except Exception:
                    embedding = [0.0] * 768

                db.add(SemanticMemory(
                    content=text,
                    summary=text[:100],
                    category="sentiment",
                    embedding=embedding,
                    importance=max(0.3, abs(float(sentiment.valence))),
                    source="session_backfill",
                    metadata_json=_build_sentiment_metadata(sentiment, text, origin),
                ))

            stored += 1

        if not req.dry_run and stored:
            await db.commit()

        return {
            "dry_run": req.dry_run,
            "sessions_scanned": len(sessions),
            "session_ids_found": len(session_ids),
            "messages_found": len(messages),
            "stored": 0 if req.dry_run else stored,
            "skipped": skipped,
            "sample": sample,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/conversation")
async def analyze_conversation_sentiment(req: ConversationSentimentRequest,
                                          db: AsyncSession = Depends(get_db)):
    """Analyze sentiment trajectory of a full conversation."""
    try:
        from aria_skills.sentiment_analysis import (
            SentimentAnalyzer, LLMSentimentClassifier, EmbeddingSentimentClassifier,
            ConversationAnalyzer,
        )

        classifier = LLMSentimentClassifier()
        emb_classifier = EmbeddingSentimentClassifier()
        analyzer = SentimentAnalyzer(
            llm_classifier=classifier,
            embedding_classifier=emb_classifier,
        )
        conv = ConversationAnalyzer(analyzer)
        result = await conv.analyze_conversation(req.messages)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/reply")
async def analyze_realtime_user_reply_sentiment(
    req: RealtimeSentimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Analyze and persist sentiment for a single user reply in real time."""
    try:
        from aria_skills.sentiment_analysis import (
            LLMSentimentClassifier, EmbeddingSentimentClassifier, ResponseTuner, SentimentAnalyzer,
        )

        text = _normalize_user_text(req.message)
        if not text:
            raise HTTPException(status_code=400, detail="message is empty")
        if _is_noise_text(text):
            raise HTTPException(status_code=400, detail="message looks like test/noise payload")
        if _looks_like_transcript(text):
            raise HTTPException(status_code=400, detail="message looks like a multi-speaker transcript; send one user reply at a time")

        parsed_session_id: uuid.UUID | None = None
        if req.session_id:
            try:
                parsed_session_id = uuid.UUID(req.session_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid session_id") from exc

        conversation_id = (req.conversation_id or req.external_session_id or "").strip() or None

        # Resolve missing internal session_id from provider-agnostic conversation id
        if parsed_session_id is None and conversation_id:
            session_match_stmt = (
                select(AgentSession.id)
                .where(
                    (AgentSession.metadata_json["external_session_id"].astext == conversation_id)
                    | (AgentSession.metadata_json["aria_session_id"].astext == conversation_id)
                )
                .order_by(AgentSession.started_at.desc())
                .limit(1)
            )
            parsed_session_id = (await db.execute(session_match_stmt)).scalar_one_or_none()

        message_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()

        dedupe_stmt = (
            select(SessionMessage)
            .where(SessionMessage.role == "user")
            .where(SessionMessage.content_hash == message_hash)
            .order_by(SessionMessage.created_at.desc())
            .limit(1)
        )
        if conversation_id:
            dedupe_stmt = dedupe_stmt.where(SessionMessage.external_session_id == conversation_id)
        elif parsed_session_id is not None:
            dedupe_stmt = dedupe_stmt.where(SessionMessage.session_id == parsed_session_id)

        message_row = (await db.execute(dedupe_stmt)).scalar_one_or_none()
        if message_row is None:
            message_row = SessionMessage(
                session_id=parsed_session_id,
                external_session_id=conversation_id,
                agent_id=req.agent_id,
                role="user",
                content=text,
                content_hash=message_hash,
                source_channel=req.source_channel,
                metadata_json=req.metadata or {},
            )
            db.add(message_row)
            await db.flush()

        existing_event = (
            await db.execute(
                select(SentimentEvent)
                .where(SentimentEvent.message_id == message_row.id)
                .limit(1)
            )
        ).scalar_one_or_none()

        if existing_event:
            await db.commit()
            return {
                "stored": False,
                "deduped": True,
                "message_id": str(message_row.id),
                "event_id": str(existing_event.id),
                "sentiment": {
                    "sentiment": existing_event.sentiment_label,
                    "dominant_emotion": existing_event.primary_emotion,
                    "confidence": existing_event.confidence,
                    "valence": existing_event.valence,
                    "arousal": existing_event.arousal,
                    "dominance": existing_event.dominance,
                },
            }

        classifier = LLMSentimentClassifier()
        emb_classifier = EmbeddingSentimentClassifier()
        analyzer = SentimentAnalyzer(
            llm_classifier=classifier,
            embedding_classifier=emb_classifier,
        )
        sentiment = await analyzer.analyze(text)
        tone = ResponseTuner().select_tone(sentiment)

        sentiment_label = _sentiment_label_from_valence(float(sentiment.valence))
        metadata = _build_sentiment_metadata(
            sentiment,
            text,
            {
                "source": "realtime_reply",
                "session_id": str(parsed_session_id) if parsed_session_id else None,
                "conversation_id": conversation_id,
                "external_session_id": conversation_id,
                "agent_id": req.agent_id,
                "source_channel": req.source_channel,
                "text_sha1": message_hash,
            },
        )

        event = SentimentEvent(
            message_id=message_row.id,
            session_id=parsed_session_id,
            external_session_id=conversation_id,
            speaker=message_row.role or "user",
            agent_id=req.agent_id or message_row.agent_id,
            sentiment_label=sentiment_label,
            primary_emotion=sentiment.primary_emotion,
            valence=float(sentiment.valence),
            arousal=float(sentiment.arousal),
            dominance=float(sentiment.dominance),
            confidence=float(sentiment.confidence),
            importance=max(0.3, abs(float(sentiment.valence))),
            metadata_json=metadata,
        )
        db.add(event)

        semantic_id: str | None = None
        if req.store_semantic:
            content_text = (
                f"Sentiment: {sentiment.primary_emotion} "
                f"(v={sentiment.valence:.2f}, a={sentiment.arousal:.2f}, d={sentiment.dominance:.2f})"
            )
            try:
                embedding = await _generate_embedding(text)
            except Exception:
                embedding = [0.0] * 768
            mem = SemanticMemory(
                content=content_text,
                summary=content_text[:100],
                category="sentiment",
                embedding=embedding,
                importance=max(0.3, abs(float(sentiment.valence))),
                source="realtime_reply",
                metadata_json=metadata,
            )
            db.add(mem)
            await db.flush()
            semantic_id = str(mem.id)

        await db.commit()

        return {
            "stored": True,
            "message_id": str(message_row.id),
            "event_id": str(event.id),
            "semantic_id": semantic_id,
            "tone_recommendation": tone,
            "sentiment": {
                "sentiment": sentiment_label,
                "dominant_emotion": sentiment.primary_emotion,
                "confidence": round(float(sentiment.confidence), 4),
                "valence": round(float(sentiment.valence), 4),
                "arousal": round(float(sentiment.arousal), 4),
                "dominance": round(float(sentiment.dominance), 4),
            },
            "conversation_id": conversation_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/backfill-messages")
async def backfill_sentiment_from_session_messages(
    req: SentimentBackfillMessagesRequest,
    db: AsyncSession = Depends(get_db),
):
    """Backfill sentiment_events from existing user session_messages (provider-agnostic)."""
    try:
        from aria_skills.sentiment_analysis import (
            LLMSentimentClassifier, EmbeddingSentimentClassifier, SentimentAnalyzer,
        )

        stmt = (
            select(SessionMessage)
            .where(SessionMessage.role == "user")
            .order_by(SessionMessage.created_at.desc())
            .limit(req.limit)
        )
        messages = (await db.execute(stmt)).scalars().all()

        if not messages:
            return {
                "dry_run": req.dry_run,
                "messages_scanned": 0,
                "scored": 0,
                "skipped_existing": 0,
            }

        classifier = LLMSentimentClassifier()
        emb_classifier = EmbeddingSentimentClassifier()
        analyzer = SentimentAnalyzer(
            llm_classifier=classifier,
            embedding_classifier=emb_classifier,
        )

        scored = 0
        skipped_existing = 0
        sample: list[dict[str, Any]] = []

        for message_row in messages:
            existing_event = (
                await db.execute(
                    select(SentimentEvent.id)
                    .where(SentimentEvent.message_id == message_row.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_event:
                skipped_existing += 1
                continue

            text = _normalize_user_text(message_row.content)
            if not text or _is_noise_text(text):
                continue

            sentiment = await analyzer.analyze(text)
            sentiment_label = _sentiment_label_from_valence(float(sentiment.valence))
            text_sha1 = message_row.content_hash or hashlib.sha1(text.encode("utf-8")).hexdigest()
            origin = {
                "source": "backfill_session_messages",
                "session_id": str(message_row.session_id) if message_row.session_id else None,
                "conversation_id": message_row.external_session_id,
                "external_session_id": message_row.external_session_id,
                "agent_id": message_row.agent_id,
                "source_channel": message_row.source_channel,
                "text_sha1": text_sha1,
            }

            if len(sample) < 5:
                sample.append(
                    {
                        "message_id": str(message_row.id),
                        "sentiment": sentiment_label,
                        "emotion": sentiment.primary_emotion,
                        "confidence": round(float(sentiment.confidence), 3),
                        "text": text[:100],
                    }
                )

            if req.dry_run:
                scored += 1
                continue

            event = SentimentEvent(
                message_id=message_row.id,
                session_id=message_row.session_id,
                external_session_id=message_row.external_session_id,
                speaker=message_row.role or "user",
                agent_id=message_row.agent_id,
                sentiment_label=sentiment_label,
                primary_emotion=sentiment.primary_emotion,
                valence=float(sentiment.valence),
                arousal=float(sentiment.arousal),
                dominance=float(sentiment.dominance),
                confidence=float(sentiment.confidence),
                importance=max(0.3, abs(float(sentiment.valence))),
                metadata_json=_build_sentiment_metadata(sentiment, text, origin),
            )
            db.add(event)

            if req.store_semantic:
                content_text = (
                    f"Sentiment: {sentiment.primary_emotion} "
                    f"(v={sentiment.valence:.2f}, a={sentiment.arousal:.2f}, d={sentiment.dominance:.2f})"
                )
                try:
                    embedding = await _generate_embedding(text)
                except Exception:
                    embedding = [0.0] * 768
                db.add(
                    SemanticMemory(
                        content=content_text,
                        summary=content_text[:100],
                        category="sentiment",
                        embedding=embedding,
                        importance=max(0.3, abs(float(sentiment.valence))),
                        source="backfill_session_messages",
                        metadata_json=_build_sentiment_metadata(sentiment, text, origin),
                    )
                )

            scored += 1

        if not req.dry_run and scored:
            await db.commit()

        return {
            "dry_run": req.dry_run,
            "messages_scanned": len(messages),
            "scored": scored,
            "skipped_existing": skipped_existing,
            "sample": sample,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/history")
async def get_sentiment_history(category: str = "sentiment",
                                 limit: int = 50,
                                 exclude_noise: bool = True,
                                 speaker: str | None = None,
                                 agent_id: str | None = None,
                                 db: AsyncSession = Depends(get_db)):
    """Get stored sentiment events, preferring structured sentiment_events table.

    Optional filters (non-mandatory):
      - speaker: "user", "assistant", or "system"
      - agent_id: e.g. "main", "coder", etc.
    """
    if category == "sentiment":
        fetch_limit = min(max(limit * 5, limit), 1000) if exclude_noise else limit
        event_stmt = (
            select(SentimentEvent, SessionMessage)
            .join(SessionMessage, SessionMessage.id == SentimentEvent.message_id, isouter=True)
            .order_by(SentimentEvent.created_at.desc())
            .limit(fetch_limit)
        )
        # Apply optional speaker / agent_id filters
        if speaker:
            event_stmt = event_stmt.where(SentimentEvent.speaker == speaker)
        if agent_id:
            event_stmt = event_stmt.where(SentimentEvent.agent_id == agent_id)

        event_rows = (await db.execute(event_stmt)).all()

        items = []
        for event, message in event_rows:
            metadata = event.metadata_json or {}
            if exclude_noise and _is_placeholder_sentiment_row(
                f"Sentiment: {event.primary_emotion} (v={event.valence:.2f}, a={event.arousal:.2f}, d={event.dominance:.2f})",
                event.importance,
                metadata,
            ):
                continue

            content = (message.content if message and message.content else "").strip()
            if _looks_like_transcript(content):
                continue
            if not content:
                content = (
                    f"Sentiment: {event.primary_emotion or event.sentiment_label} "
                    f"(v={event.valence:.2f}, a={event.arousal:.2f}, d={event.dominance:.2f})"
                )

            items.append(
                {
                    "id": str(event.id),
                    "content": content,
                    "category": "sentiment",
                    "source": "sentiment_events",
                    "importance": event.importance,
                    "metadata": metadata,
                    "speaker": event.speaker or (message.role if message else "user"),
                    "agent_id": event.agent_id or (message.agent_id if message else None),
                    "source_channel": message.source_channel if message else None,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                }
            )
            if len(items) >= limit:
                break

        if items:
            return {"items": items, "total": len(items)}

        # If speaker/agent_id filters were used, return empty — don't fall through
        if speaker or agent_id:
            return {"items": [], "total": 0}

    fetch_limit = min(max(limit * 5, limit), 1000) if exclude_noise else limit
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.category == category)
        .order_by(SemanticMemory.created_at.desc())
        .limit(fetch_limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()

    if exclude_noise:
        items = [
            m for m in items
            if not _is_placeholder_sentiment_row(m.content, m.importance, m.metadata_json)
            and not _looks_like_transcript(m.content)
        ]

    items = items[:limit]

    return {
        "items": [
            {
                "id": str(m.id),
                "content": m.content,
                "category": m.category,
                "source": m.source,
                "importance": m.importance,
                "metadata": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
        "total": len(items),
    }


# ═══════════════════════════════════════════════════════════════════
# Embedding Reference Seeding & Feedback  (S-47 pgvector integration)
# ═══════════════════════════════════════════════════════════════════

# ~100 labelled reference sentences covering 8 emotions × 3 sentiment labels.
# Each entry: (text, sentiment_label, primary_emotion, valence, arousal, dominance)
# ── Sentiment reference corpus (loaded from external file) ──────────

_REFERENCES_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sentiment_references.json")

def _load_reference_sentences() -> list[tuple[str, str, str, float, float, float]]:
    """Load labelled reference sentences from the external JSON file."""
    with open(_REFERENCES_JSON_PATH, encoding="utf-8") as f:
        data = json_lib.load(f)
    return [
        (r["text"], r["label"], r["emotion"], r["valence"], r["arousal"], r["dominance"])
        for r in data
    ]


@router.post("/sentiment/seed-references")
async def seed_sentiment_references(
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """Seed labelled sentiment reference sentences into semantic_memories.

    These references power the EmbeddingSentimentClassifier which uses
    pgvector cosine distance to classify new messages by comparing them
    to this labelled corpus.

    Set ``force=true`` to delete existing references and re-seed.
    """
    import logging
    logger = logging.getLogger("aria.analysis.seed_refs")

    # Optionally clear old references
    if force:
        await db.execute(
            delete(SemanticMemory).where(SemanticMemory.category == "sentiment_reference")
        )
        await db.commit()
        logger.info("Cleared existing sentiment_reference rows (force=true)")

    # Check how many already exist
    existing_count = (
        await db.execute(
            select(func.count()).select_from(SemanticMemory).where(
                SemanticMemory.category == "sentiment_reference"
            )
        )
    ).scalar() or 0

    references = _load_reference_sentences()

    if existing_count >= len(references) and not force:
        return {
            "seeded": 0,
            "skipped": existing_count,
            "message": f"Already {existing_count} references seeded. Use force=true to re-seed.",
        }

    seeded = 0
    errors = 0

    for text, label, emotion, valence, arousal, dominance in references:
        # Skip duplicates by content
        dup = await db.execute(
            select(func.count()).select_from(SemanticMemory).where(
                SemanticMemory.category == "sentiment_reference",
                SemanticMemory.content == text,
            )
        )
        if (dup.scalar() or 0) > 0:
            continue

        try:
            embedding = await _generate_embedding(text)
        except Exception as e:
            logger.warning("Embedding failed for ref '%s': %s", text[:40], e)
            errors += 1
            continue

        mem = SemanticMemory(
            content=text,
            summary=f"{label}/{emotion}",
            category="sentiment_reference",
            embedding=embedding,
            importance=0.9,  # references are high-importance
            source="seed_sentiment_references",
            metadata_json={
                "sentiment_label": label,
                "primary_emotion": emotion,
                "valence": valence,
                "arousal": arousal,
                "dominance": dominance,
                "is_reference": True,
            },
        )
        db.add(mem)
        seeded += 1

        # Commit in batches of 10
        if seeded % 10 == 0:
            await db.commit()

    await db.commit()
    logger.info("Seeded %d sentiment references (%d errors, corpus=%d)", seeded, errors, len(references))
    return {"seeded": seeded, "errors": errors, "total_references": existing_count + seeded, "corpus_size": len(references)}


@router.post("/sentiment/feedback")
async def sentiment_feedback_loop(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reinforcement learning loop: promote high-confidence events to references.

    When a sentiment event has been classified with high confidence (>= 0.75)
    and is confirmed correct (or simply accumulates), add the original message
    text as a new reference sentence — making the embedding classifier smarter
    over time.

    Body: { "event_id": str, "confirmed": bool (optional, default true) }
    """
    import logging
    logger = logging.getLogger("aria.analysis.feedback")

    data = await request.json()
    event_id_str = data.get("event_id")
    confirmed = data.get("confirmed", True)

    if not event_id_str:
        raise HTTPException(status_code=400, detail="event_id is required")

    try:
        event_uuid = uuid.UUID(event_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event_id")

    # Fetch the event + original message
    event = (
        await db.execute(
            select(SentimentEvent).where(SentimentEvent.id == event_uuid)
        )
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Sentiment event not found")

    msg = (
        await db.execute(
            select(SessionMessage).where(SessionMessage.id == event.message_id)
        )
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Original message not found")

    if not confirmed:
        return {"promoted": False, "reason": "unconfirmed"}

    content = (msg.content or "").strip()
    if len(content) < 5:
        return {"promoted": False, "reason": "message_too_short"}

    # Check if already a reference
    dup = await db.execute(
        select(func.count()).select_from(SemanticMemory).where(
            SemanticMemory.category == "sentiment_reference",
            SemanticMemory.content == content,
        )
    )
    if (dup.scalar() or 0) > 0:
        return {"promoted": False, "reason": "already_reference"}

    try:
        embedding = await _generate_embedding(content)
    except Exception as e:
        logger.warning("Embedding failed for feedback: %s", e)
        return {"promoted": False, "reason": f"embedding_failed: {e}"}

    ref = SemanticMemory(
        content=content,
        summary=f"{event.sentiment_label}/{event.primary_emotion}",
        category="sentiment_reference",
        embedding=embedding,
        importance=0.8,
        source="feedback_loop",
        metadata_json={
            "sentiment_label": event.sentiment_label,
            "primary_emotion": event.primary_emotion or "neutral",
            "valence": float(event.valence),
            "arousal": float(event.arousal),
            "dominance": float(event.dominance),
            "confidence": float(event.confidence),
            "is_reference": True,
            "source_event_id": str(event.id),
        },
    )
    db.add(ref)
    await db.commit()

    logger.info("Promoted event %s → sentiment_reference (label=%s, emotion=%s)",
                event_id_str, event.sentiment_label, event.primary_emotion)
    return {
        "promoted": True,
        "reference_id": str(ref.id),
        "sentiment_label": event.sentiment_label,
        "primary_emotion": event.primary_emotion,
    }


@router.post("/sentiment/auto-promote")
async def auto_promote_high_confidence_events(
    min_confidence: float = 0.75,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Batch-promote high-confidence sentiment events to reference corpus.

    Scans recent events with confidence >= min_confidence whose messages
    are not yet in the reference corpus and promotes them.
    """
    import logging
    logger = logging.getLogger("aria.analysis.auto_promote")

    # Find high-confidence events not yet promoted
    stmt = (
        select(SentimentEvent, SessionMessage)
        .join(SessionMessage, SentimentEvent.message_id == SessionMessage.id)
        .where(SentimentEvent.confidence >= min_confidence)
        .order_by(SentimentEvent.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    promoted = 0
    skipped = 0

    for event, msg in rows:
        content = (msg.content or "").strip()
        if len(content) < 5:
            skipped += 1
            continue

        # Dedup
        dup = await db.execute(
            select(func.count()).select_from(SemanticMemory).where(
                SemanticMemory.category == "sentiment_reference",
                SemanticMemory.content == content,
            )
        )
        if (dup.scalar() or 0) > 0:
            skipped += 1
            continue

        try:
            embedding = await _generate_embedding(content)
        except Exception:
            skipped += 1
            continue

        ref = SemanticMemory(
            content=content,
            summary=f"{event.sentiment_label}/{event.primary_emotion}",
            category="sentiment_reference",
            embedding=embedding,
            importance=0.8,
            source="auto_promote",
            metadata_json={
                "sentiment_label": event.sentiment_label,
                "primary_emotion": event.primary_emotion or "neutral",
                "valence": float(event.valence),
                "arousal": float(event.arousal),
                "dominance": float(event.dominance),
                "confidence": float(event.confidence),
                "is_reference": True,
                "source_event_id": str(event.id),
            },
        )
        db.add(ref)
        promoted += 1

    await db.commit()
    logger.info("Auto-promoted %d events to references (skipped %d)", promoted, skipped)
    return {"promoted": promoted, "skipped": skipped, "checked": len(rows)}


@router.post("/sentiment/cleanup-placeholders")
async def cleanup_sentiment_placeholders(
    dry_run: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Remove placeholder neutral sentiment rows generated from non-user structured payloads."""
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.category == "sentiment")
        .order_by(SemanticMemory.created_at.desc())
        .limit(5000)
    )
    rows = (await db.execute(stmt)).scalars().all()
    targets = [
        m for m in rows
        if _is_placeholder_sentiment_row(m.content, m.importance, m.metadata_json)
    ]

    if dry_run:
        return {
            "dry_run": True,
            "candidates": len(targets),
            "sample_ids": [str(m.id) for m in targets[:10]],
        }

    target_ids = [m.id for m in targets]
    deleted = 0
    if target_ids:
        result = await db.execute(
            delete(SemanticMemory)
            .where(SemanticMemory.id.in_(target_ids))
        )
        await db.commit()
        deleted = int(result.rowcount or 0)

    return {
        "dry_run": False,
        "deleted": deleted,
    }


# ── Pattern Endpoints ──────────────────────────────────────────────────────

@router.post("/patterns/detect")
async def detect_patterns(req: PatternDetectionRequest, db: AsyncSession = Depends(get_db)):
    """Run pattern detection on memories."""
    from aria_skills.pattern_recognition import PatternRecognizer, MemoryItem

    memories = req.memories
    if not memories:
        # Fetch from semantic memory
        stmt = (
            select(SemanticMemory)
            .order_by(SemanticMemory.created_at.desc())
            .limit(200)
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        memories = [
            {
                "id": str(m.id),
                "content": m.content,
                "category": m.category,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
                "metadata": m.metadata_json or {},
            }
            for m in items
        ]

    if len(memories) < 10:
        return {"patterns_found": 0, "patterns": [],
                "message": "Need >= 10 memories for pattern detection"}

    recognizer = PatternRecognizer(window_days=30)
    mem_items = [MemoryItem.from_dict(m) for m in memories]
    detection = await recognizer.analyze(mem_items, min_confidence=req.min_confidence)

    # Store in semantic memory if requested (dedup: update existing patterns)
    stored_ids = []
    if req.store:
        for p in detection.patterns_found[:20]:
            content_text = (f"Pattern: {p.type.value} — {p.subject} "
                           f"(confidence={p.confidence:.2f})")
            new_meta = {
                "pattern_type": p.type.value,
                "subject": p.subject,
                "confidence": p.confidence,
                "evidence": p.evidence[:5],
            }
            try:
                embedding = await _generate_embedding(content_text)
            except Exception:
                embedding = [0.0] * 768

            # Check for existing pattern with same type+subject
            existing_stmt = (
                select(SemanticMemory)
                .where(SemanticMemory.category == "pattern_detection")
                .where(SemanticMemory.metadata_json["pattern_type"].astext == p.type.value)
                .where(SemanticMemory.metadata_json["subject"].astext == p.subject)
                .limit(1)
            )
            existing = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing:
                existing.content = content_text
                existing.summary = content_text[:100]
                existing.importance = p.confidence
                existing.metadata_json = new_meta
                existing.embedding = embedding
            else:
                mem = SemanticMemory(
                    content=content_text,
                    summary=content_text[:100],
                    category="pattern_detection",
                    embedding=embedding,
                    importance=p.confidence,
                    source="analysis_api",
                    metadata_json=new_meta,
                )
                db.add(mem)
        await db.commit()

    return {
        "patterns_found": len(detection.patterns_found),
        "patterns": [p.to_dict() for p in detection.patterns_found],
        "new_patterns": detection.new_patterns,
        "persistent_patterns": detection.persistent_patterns,
        "memories_analyzed": detection.total_memories_analyzed,
    }


@router.get("/patterns/history")
async def get_pattern_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get stored pattern detections from semantic memory."""
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.category == "pattern_detection")
        .order_by(SemanticMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": str(m.id),
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
                "metadata": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
        "total": len(items),
    }


# ── Compression Endpoints ──────────────────────────────────────────────────

@router.post("/compression/run")
async def run_compression(req: CompressionRequest, db: AsyncSession = Depends(get_db)):
    """Run memory compression on provided memories."""
    from aria_skills.memory_compression import (
        MemoryEntry, MemoryCompressor, CompressionManager)

    mem_objects = [MemoryEntry.from_dict(m) for m in req.memories]
    compressor = MemoryCompressor()
    manager = CompressionManager(compressor)
    result = await manager.process_all(mem_objects)

    # Store compressed summaries
    stored_ids = []
    if req.store_semantic:
        for cm in manager.compressed_store:
            try:
                embedding = await _generate_embedding(cm.summary)
            except Exception:
                embedding = [0.0] * 768
            mem = SemanticMemory(
                content=cm.summary,
                summary=cm.summary[:100],
                category=f"compressed_{cm.tier}",
                embedding=embedding,
                importance=0.7 if cm.tier == "archive" else 0.5,
                source="compression_api",
                metadata_json={
                    "tier": cm.tier,
                    "original_count": cm.original_count,
                    "key_entities": cm.key_entities,
                    "key_facts": cm.key_facts,
                },
            )
            db.add(mem)
        await db.commit()

    return {
        "compressed": result.success,
        "memories_processed": result.memories_processed,
        "compression_ratio": round(result.compression_ratio, 3),
        "tokens_saved_estimate": result.tokens_saved_estimate,
        "tiers_updated": result.tiers_updated,
        "summaries": [cm.to_dict() for cm in manager.compressed_store],
    }


@router.get("/compression/history")
async def get_compression_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get stored compressed memories from semantic memory."""
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.category.in_(["compressed_recent", "compressed_archive"]))
        .order_by(SemanticMemory.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {
        "items": [
            {
                "id": str(m.id),
                "content": m.content,
                "category": m.category,
                "importance": m.importance,
                "metadata": m.metadata_json,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in items
        ],
        "total": len(items),
    }


# ── Seed: backfill semantic_memories from activity_log + thoughts ────────────


@router.post("/seed-memories")
async def seed_semantic_memories(
    limit: int = 200,
    skip_existing: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Backfill semantic_memories from activity_log + thoughts.

    Reads recent activities and thoughts, generates embeddings via LiteLLM,
    and stores them in semantic_memories so pattern_recognition,
    sentiment_analysis, and unified_search have data to work with.
    """
    import logging

    logger = logging.getLogger("aria.analysis.seed")
    seeded = 0
    skipped = 0
    errors = 0
    batch_size = 10

    # ── 1. Thoughts → semantic_memories ──
    thought_stmt = (
        select(Thought)
        .order_by(Thought.created_at.desc())
        .limit(limit)
    )
    thoughts = (await db.execute(thought_stmt)).scalars().all()

    for i in range(0, len(thoughts), batch_size):
        batch = thoughts[i : i + batch_size]
        for t in batch:
            content = t.content.strip()
            if not content or len(content) < 10:
                skipped += 1
                continue

            if skip_existing:
                fp = content[:100]
                exists = await db.execute(
                    select(func.count())
                    .select_from(SemanticMemory)
                    .where(
                        SemanticMemory.source == "seed_thoughts",
                        SemanticMemory.summary == fp,
                    )
                )
                if (exists.scalar() or 0) > 0:
                    skipped += 1
                    continue

            try:
                embedding = await _generate_embedding(content[:2000])
            except Exception as e:
                logger.warning("Embedding failed for thought %s: %s", t.id, e)
                embedding = [0.0] * 768
                errors += 1

            cat = t.category or "general"
            mem = SemanticMemory(
                content=content[:5000],
                summary=content[:100],
                category=f"thought_{cat}",
                embedding=embedding,
                importance=0.6,
                source="seed_thoughts",
                metadata_json={
                    "original_id": str(t.id),
                    "thought_category": cat,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                },
            )
            db.add(mem)
            seeded += 1
        await db.commit()

    # ── 2. Activities → semantic_memories ──
    activity_stmt = (
        select(ActivityLog)
        .where(
            ActivityLog.action.notin_(["skill.health_check", "heartbeat"]),
            ActivityLog.error_message.is_(None),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )
    activities = (await db.execute(activity_stmt)).scalars().all()

    for i in range(0, len(activities), batch_size):
        batch = activities[i : i + batch_size]
        for a in batch:
            details = a.details or {}
            result_preview = details.get("result_preview", "")
            args_preview = details.get("args_preview", "")
            content = (
                f"Action: {a.action}"
                + (f" | Skill: {a.skill}" if a.skill else "")
                + (f" | {result_preview[:200]}" if result_preview else "")
                + (f" | Args: {args_preview[:100]}" if args_preview else "")
            )
            content = content.strip()
            if len(content) < 15:
                skipped += 1
                continue

            if skip_existing:
                fp = content[:100]
                exists = await db.execute(
                    select(func.count())
                    .select_from(SemanticMemory)
                    .where(
                        SemanticMemory.source == "seed_activities",
                        SemanticMemory.summary == fp,
                    )
                )
                if (exists.scalar() or 0) > 0:
                    skipped += 1
                    continue

            try:
                embedding = await _generate_embedding(content[:2000])
            except Exception as e:
                logger.warning("Embedding failed for activity %s: %s", a.id, e)
                embedding = [0.0] * 768
                errors += 1

            importance = 0.4
            if a.action.startswith("goal"):
                importance = 0.7
            elif a.action == "cron_execution":
                importance = 0.3
            elif not a.success:
                importance = 0.6

            mem = SemanticMemory(
                content=content[:5000],
                summary=content[:100],
                category="activity",
                embedding=embedding,
                importance=importance,
                source="seed_activities",
                metadata_json={
                    "original_id": str(a.id),
                    "action": a.action,
                    "skill": a.skill,
                    "success": a.success,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                },
            )
            db.add(mem)
            seeded += 1
        await db.commit()

    return {
        "seeded": seeded,
        "skipped": skipped,
        "errors": errors,
        "sources": {
            "thoughts": len(thoughts),
            "activities": len(activities),
        },
    }
