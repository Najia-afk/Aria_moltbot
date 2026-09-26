"""Ingest aria_souvenirs/*.md into the pgvector semantic memory index.

aria_souvenirs/ is Aria's curated "keeper" archive -- dated snapshot folders
(SOUVENIR_*.md, SPRINT_*_BOARD.md, INDEX.md) plus standalone reflective/
creative pieces she decided were worth preserving once a piece of work was
done. This is deliberately NOT aria_memories/ -- that tree is Aria's raw
working space (logs, drafts, in-progress tickets/specs, scratch code, state
files) that she manages herself via her own memory_compression/consolidation
skills (surface -> medium -> deep tiers, already stored in this same table).
Mechanically vectorizing all of aria_memories/ would bypass her own curation
choices and flood semantic search with working scratch instead of finished
knowledge. aria_souvenirs/ is the tree she already treats as "done, keep
this" -- so that's what becomes searchable here.

Until now these files were invisible to semantic search and chat context
recall -- only memories stored via the memory_store skill
(aria_data.semantic_memories) were embedded and searchable. This scans the
tree, embeds new/changed files, and upserts them into the same table so they
show up in /memory-search and get pulled into chat context recall exactly
like any other memory.

Idempotent: each file's content hash is stored in metadata_json, so re-running
only re-embeds files that actually changed.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

logger = logging.getLogger("aria.memory_file_ingest")

SOUVENIRS_ROOT = Path(__file__).resolve().parent.parent / "aria_souvenirs"
# Code snapshots mirrored into each dated folder -- not knowledge, skip them.
IGNORE_DIR_NAMES = {"aria_files"}
# The shared generate_embedding() in routers.memories uses a 2.5s timeout
# tuned for interactive chat-context injection -- too tight for a bulk pass
# over hundreds of files, where it was silently tripping the 120s fallback
# circuit breaker mid-batch (degrading the rest of the run to low-quality
# hash vectors without erroring). Batch ingestion calls LiteLLM directly with
# its own generous timeout + retry instead, and never persists a fallback
# vector -- a failed embedding is recorded as an error and the file is left
# for the next (idempotent) run.
BATCH_EMBED_TIMEOUT_SECONDS = 30.0
BATCH_EMBED_RETRIES = 2
SOURCE_TAG = "aria_souvenirs_file"
MAX_CHARS = 6000  # keeps well within the embedding model's context window

# Dated snapshot folders look like 'aria_v3_250926' -> 25 Sep 2026 (DDMMYY).
SNAPSHOT_DATE_RE = re.compile(r"^aria_v\d+_(\d{2})(\d{2})(\d{2})$")
# Standalone pieces (letters, identity docs, creative writing) are evergreen --
# they represent who Aria is, not a dated build/engineering log, so they don't
# fade with age the way session snapshots do.
STANDALONE_IMPORTANCE = 0.65
SNAPSHOT_BASE_IMPORTANCE = 0.5
SNAPSHOT_DAILY_DECAY = 0.995  # ~30% left after a year, floors out below
SNAPSHOT_IMPORTANCE_FLOOR = 0.2


def _relative_path(path: Path) -> str:
    return str(path.relative_to(SOUVENIRS_ROOT.parent))


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _category_for(path: Path) -> str:
    """Dated snapshot folder name (e.g. 'aria_v3_250926'), or 'standalone'
    for the loose curated pieces living directly under aria_souvenirs/."""
    rel = path.relative_to(SOUVENIRS_ROOT)
    return rel.parts[0] if len(rel.parts) > 1 else "standalone"


def _importance_for(category: str, today: date | None = None) -> float:
    """Weight identity/creative 'standalone' pieces as enduring; age-decay
    dated engineering/build snapshots so old sessions fade into the
    background instead of competing equally with recent work."""
    if category == "standalone":
        return STANDALONE_IMPORTANCE

    match = SNAPSHOT_DATE_RE.match(category)
    if not match:
        return SNAPSHOT_BASE_IMPORTANCE

    day, month, year = (int(g) for g in match.groups())
    try:
        snapshot_date = date(2000 + year, month, day)
    except ValueError:
        return SNAPSHOT_BASE_IMPORTANCE

    age_days = max(((today or date.today()) - snapshot_date).days, 0)
    decayed = SNAPSHOT_BASE_IMPORTANCE * (SNAPSHOT_DAILY_DECAY ** age_days)
    return round(max(SNAPSHOT_IMPORTANCE_FLOOR, decayed), 3)


def _iter_souvenir_markdown_files():
    for path in sorted(SOUVENIRS_ROOT.rglob("*.md")):
        if IGNORE_DIR_NAMES.intersection(path.relative_to(SOUVENIRS_ROOT).parts[:-1]):
            continue
        yield path


async def _generate_embedding_batch(text: str) -> list[float]:
    """Fetch a real embedding with a batch-appropriate timeout + retry.

    Raises on failure instead of ever returning a hash-based fallback
    vector -- callers must treat a raised exception as "skip this file",
    not "persist something anyway".
    """
    from aria_models.loader import get_embedding_model

    litellm_url = os.environ.get("LITELLM_URL", "http://litellm:4000")
    litellm_key = os.environ.get("LITELLM_MASTER_KEY", "")
    model = get_embedding_model() or "embedding"

    last_exc: Exception | None = None
    for attempt in range(BATCH_EMBED_RETRIES + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{litellm_url}/v1/embeddings",
                    json={"model": model, "input": text},
                    headers={"Authorization": f"Bearer {litellm_key}"},
                    timeout=httpx.Timeout(BATCH_EMBED_TIMEOUT_SECONDS),
                )
                resp.raise_for_status()
                embedding = resp.json().get("data", [{}])[0].get("embedding")
                if isinstance(embedding, list) and embedding:
                    return embedding
                raise ValueError("empty embedding from LiteLLM response")
        except Exception as exc:
            last_exc = exc
            if attempt < BATCH_EMBED_RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise last_exc or RuntimeError("embedding failed with no exception captured")


async def ingest_markdown_memories(session_factory) -> dict[str, Any]:
    """Scan aria_souvenirs/**/*.md and upsert embeddings into semantic_memories.

    Args:
        session_factory: an async_sessionmaker (e.g. db.session.AsyncSessionLocal).

    Returns:
        Stats dict: scanned/inserted/updated/skipped/errors counts.
    """
    from db.models import SemanticMemory

    stats = {"scanned": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}

    if not SOUVENIRS_ROOT.exists():
        logger.warning("aria_souvenirs/ not found at %s", SOUVENIRS_ROOT)
        return stats

    # Pre-flight: refuse to silently persist a whole batch of low-quality
    # hash-fallback vectors if the real embedding endpoint is down right now.
    try:
        await _generate_embedding_batch("embedding preflight check")
    except Exception as exc:
        logger.error("Embedding endpoint unavailable, aborting ingestion: %s", exc)
        stats["error"] = f"embedding endpoint unavailable: {exc}"
        return stats

    files = list(_iter_souvenir_markdown_files())
    stats["scanned"] = len(files)

    async with session_factory() as db:
        for path in files:
            rel_path = _relative_path(path)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError as exc:
                logger.warning("Could not read %s: %s", rel_path, exc)
                stats["errors"] += 1
                continue
            if not text:
                stats["skipped"] += 1
                continue

            content = text[:MAX_CHARS]
            content_hash = _content_hash(content)

            existing = (
                await db.execute(
                    select(SemanticMemory).where(
                        SemanticMemory.source == SOURCE_TAG,
                        SemanticMemory.metadata_json["file_path"].astext == rel_path,
                    )
                )
            ).scalar_one_or_none()

            if existing and existing.metadata_json.get("content_hash") == content_hash:
                stats["skipped"] += 1
                continue

            try:
                embedding = await _generate_embedding_batch(content)
            except Exception as exc:
                logger.warning("Embedding failed for %s (will retry next run): %s", rel_path, exc)
                stats["errors"] += 1
                continue

            summary = next((ln.strip() for ln in content.splitlines() if ln.strip()), rel_path)[:200]
            category = _category_for(path)
            importance = _importance_for(category)

            if existing:
                existing.content = content
                existing.summary = summary
                existing.embedding = embedding
                existing.category = category
                existing.importance = importance
                existing.metadata_json = {
                    **(existing.metadata_json or {}),
                    "file_path": rel_path,
                    "content_hash": content_hash,
                }
                stats["updated"] += 1
            else:
                db.add(SemanticMemory(
                    content=content,
                    summary=summary,
                    category=category,
                    embedding=embedding,
                    importance=importance,
                    source=SOURCE_TAG,
                    metadata_json={"file_path": rel_path, "content_hash": content_hash},
                ))
                stats["inserted"] += 1

            # Commit incrementally -- this is a long-running batch (hundreds
            # of real embedding calls); a single end-of-run commit means any
            # interruption (gateway timeout, container restart) loses ALL
            # progress instead of just the remaining files.
            if (stats["inserted"] + stats["updated"]) % 20 == 0:
                await db.commit()

        await db.commit()

    try:
        from aria_engine.memory_cache import get_memory_cache
        get_memory_cache().invalidate_semantic()
    except Exception:
        pass

    logger.info("Markdown memory ingestion: %s", stats)
    return stats
