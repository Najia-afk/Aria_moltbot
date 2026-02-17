"""One-shot debug script for autoscorer state."""
import asyncio
from db.session import AsyncSessionLocal
from db.models import SessionMessage, SentimentEvent
from sqlalchemy import select, func

async def check():
    async with AsyncSessionLocal() as db:
        total_msgs = (await db.execute(select(func.count(SessionMessage.id)))).scalar()
        total_events = (await db.execute(select(func.count(SentimentEvent.id)))).scalar()

        scored_ids = select(SentimentEvent.message_id).where(
            SentimentEvent.message_id.isnot(None)
        ).scalar_subquery()
        unscored = (await db.execute(
            select(func.count(SessionMessage.id))
            .where(SessionMessage.role.in_(["user", "assistant"]))
            .where(SessionMessage.id.notin_(scored_ids))
        )).scalar()

        agents = (await db.execute(
            select(SessionMessage.agent_id, func.count(SessionMessage.id))
            .group_by(SessionMessage.agent_id)
        )).all()

        speakers = (await db.execute(
            select(SentimentEvent.speaker, func.count(SentimentEvent.id))
            .group_by(SentimentEvent.speaker)
        )).all()

        ev_agents = (await db.execute(
            select(SentimentEvent.agent_id, func.count(SentimentEvent.id))
            .group_by(SentimentEvent.agent_id)
        )).all()

        # Check if sentiment_analysis skill is importable
        try:
            from aria_skills.sentiment_analysis import (
                SentimentAnalyzer, LLMSentimentClassifier, EmbeddingSentimentClassifier,
            )
            print("sentiment_analysis skill: OK")
        except ImportError as e:
            print(f"sentiment_analysis skill: IMPORT FAILED - {e}")

        # Show some unscored messages
        if unscored > 0:
            rows = (await db.execute(
                select(SessionMessage.id, SessionMessage.role, SessionMessage.agent_id,
                       SessionMessage.content, SessionMessage.created_at)
                .where(SessionMessage.role.in_(["user", "assistant"]))
                .where(SessionMessage.id.notin_(scored_ids))
                .order_by(SessionMessage.created_at.desc())
                .limit(5)
            )).all()
            print(f"\nSample unscored messages:")
            for r in rows:
                print(f"  id={r[0]} role={r[1]} agent={r[2]} len={len(r[3] or '')} date={r[4]}")

        print(f"\nsession_messages total: {total_msgs}")
        print(f"sentiment_events total: {total_events}")
        print(f"unscored messages: {unscored}")
        print(f"session_messages by agent_id: {agents}")
        print(f"sentiment_events by speaker: {speakers}")
        print(f"sentiment_events by agent_id: {ev_agents}")

asyncio.run(check())
