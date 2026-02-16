"""
Analysis endpoints — Sentiment, Patterns, Compression.

Provides REST endpoints that integrate with
aria_skills/{sentiment_analysis,pattern_recognition,memory_compression}.
All heavy lifting is done in the skills; these endpoints serve as a thin
HTTP façade for the web dashboard and external callers.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ActivityLog, SemanticMemory, Thought
from deps import get_db

LITELLM_URL = os.environ.get("LITELLM_URL", "http://litellm:4000")
LITELLM_KEY = os.environ.get("LITELLM_MASTER_KEY", "")

router = APIRouter(prefix="/analysis", tags=["Analysis"])


async def _generate_embedding(text: str) -> list[float]:
    """Generate embedding via LiteLLM embedding endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/v1/embeddings",
            json={"model": "nomic-embed-text", "input": text},
            headers={"Authorization": f"Bearer {LITELLM_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


# ── Request / Response Schemas ──────────────────────────────────────────────

class SentimentRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10_000)
    context: Optional[List[str]] = None
    store: bool = True


class ConversationSentimentRequest(BaseModel):
    messages: List[Dict[str, Any]] = Field(..., min_items=1)
    store: bool = True


class PatternDetectionRequest(BaseModel):
    memories: Optional[List[Dict[str, Any]]] = None
    min_confidence: float = Field(0.3, ge=0, le=1)
    store: bool = True


class CompressionRequest(BaseModel):
    memories: List[Dict[str, Any]] = Field(..., min_items=5)
    store_semantic: bool = True


class SessionCompressionRequest(BaseModel):
    hours_back: int = Field(6, ge=1, le=48)


# ── Sentiment Endpoints ────────────────────────────────────────────────────

@router.post("/sentiment/message")
async def analyze_message_sentiment(req: SentimentRequest, db: AsyncSession = Depends(get_db)):
    """Analyze sentiment of a single message."""
    try:
        from aria_skills.sentiment_analysis import SentimentAnalyzer, LLMSentimentClassifier, ResponseTuner

        classifier = LLMSentimentClassifier()
        analyzer = SentimentAnalyzer(llm_classifier=classifier)
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
                metadata_json={
                    "valence": sentiment.valence,
                    "arousal": sentiment.arousal,
                    "dominance": sentiment.dominance,
                    "primary_emotion": sentiment.primary_emotion,
                    "text_snippet": req.text[:100],
                },
            )
            db.add(mem)
            await db.commit()
            await db.refresh(mem)
            result["stored_id"] = str(mem.id)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sentiment/conversation")
async def analyze_conversation_sentiment(req: ConversationSentimentRequest,
                                          db: AsyncSession = Depends(get_db)):
    """Analyze sentiment trajectory of a full conversation."""
    try:
        from aria_skills.sentiment_analysis import (
            SentimentAnalyzer, LLMSentimentClassifier, ConversationAnalyzer)

        classifier = LLMSentimentClassifier()
        analyzer = SentimentAnalyzer(llm_classifier=classifier)
        conv = ConversationAnalyzer(analyzer)
        result = await conv.analyze_conversation(req.messages)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/history")
async def get_sentiment_history(category: str = "sentiment",
                                 limit: int = 50,
                                 db: AsyncSession = Depends(get_db)):
    """Get stored sentiment events from semantic memory."""
    stmt = (
        select(SemanticMemory)
        .where(SemanticMemory.category == category)
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

    # Store in semantic memory if requested
    stored_ids = []
    if req.store:
        for p in detection.patterns_found[:20]:
            content_text = (f"Pattern: {p.type.value} — {p.subject} "
                           f"(confidence={p.confidence:.2f})")
            try:
                embedding = await _generate_embedding(content_text)
            except Exception:
                embedding = [0.0] * 768
            mem = SemanticMemory(
                content=content_text,
                summary=content_text[:100],
                category="pattern_detection",
                embedding=embedding,
                importance=p.confidence,
                source="analysis_api",
                metadata_json={
                    "pattern_type": p.type.value,
                    "subject": p.subject,
                    "confidence": p.confidence,
                    "evidence": p.evidence[:5],
                },
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
