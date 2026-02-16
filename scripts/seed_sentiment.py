#!/usr/bin/env python3
"""Batch seed sentiment analysis from existing activities and thoughts."""
import asyncio
import os
import sys

sys.path.insert(0, "/")
sys.path.insert(0, "/app")


async def main():
    from db.session import AsyncSessionLocal
    from db.models import SemanticMemory, ActivityLog, Thought
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        # Get recent activities with meaningful content
        stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(20)
        rows = (await db.execute(stmt)).scalars().all()
        texts = []
        for r in rows:
            if r.details:
                note = r.details.get("note", "") or r.details.get("message", "") or str(r.details)[:200]
                if len(note) > 20:
                    texts.append(note)

        # Get recent thoughts
        stmt2 = select(Thought).order_by(Thought.created_at.desc()).limit(8)
        thoughts = (await db.execute(stmt2)).scalars().all()
        for t in thoughts:
            if t.content and len(t.content) > 20:
                texts.append(t.content[:300])

        # Deduplicate and limit
        seen = set()
        unique = []
        for t in texts:
            key = t[:50]
            if key not in seen:
                seen.add(key)
                unique.append(t)
        texts = unique[:12]
        print(f"Got {len(texts)} texts to analyze")

        from aria_skills.sentiment_analysis import SentimentAnalyzer, LLMSentimentClassifier

        classifier = LLMSentimentClassifier()
        analyzer = SentimentAnalyzer(llm_classifier=classifier)

        stored = 0
        for i, text in enumerate(texts):
            try:
                sentiment = await analyzer.analyze(text[:300])
                content_text = (
                    f"Sentiment: {sentiment.primary_emotion} "
                    f"(v={sentiment.valence:.2f}, a={sentiment.arousal:.2f}, d={sentiment.dominance:.2f})"
                )
                mem = SemanticMemory(
                    content=content_text,
                    summary=content_text[:100],
                    category="sentiment",
                    embedding=[0.0] * 768,
                    importance=max(0.3, abs(sentiment.valence)),
                    source="analysis_api",
                    metadata_json={
                        "valence": sentiment.valence,
                        "arousal": sentiment.arousal,
                        "dominance": sentiment.dominance,
                        "primary_emotion": sentiment.primary_emotion,
                        "text_snippet": text[:100],
                        "sentiment": {
                            "sentiment": sentiment.primary_emotion
                            if sentiment.valence > 0.1
                            else "negative"
                            if sentiment.valence < -0.1
                            else "neutral",
                            "dominant_emotion": sentiment.primary_emotion,
                            "confidence": sentiment.confidence,
                            "signals": sentiment.labels[:3] if sentiment.labels else [],
                        },
                    },
                )
                db.add(mem)
                stored += 1
                print(
                    f"  [{i+1}/{len(texts)}] {sentiment.primary_emotion} "
                    f"(v={sentiment.valence:.2f}) - {text[:60]}..."
                )
            except Exception as e:
                print(f"  [{i+1}/{len(texts)}] FAIL: {e}")

        await db.commit()
        print(f"\nStored {stored} sentiment entries")


asyncio.run(main())
