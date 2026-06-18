from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from db import chunks as chunks_db
from services.retrieval.vector import _get_model

DEFAULT_CHUNK_SIZE = 512
DEFAULT_CHUNK_OVERLAP = 64


@dataclass
class IndexingOptions:
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP


@dataclass
class IndexingResult:
    chunks_written: int
    skipped: bool
    elapsed_ms: float
    error: str | None = None


@dataclass
class BatchResult:
    succeeded: int
    failed: int
    skipped: int
    outcomes: list[dict[str, Any]] = field(default_factory=list)


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Sliding-window splitter with configurable overlap."""
    text = text.strip()
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be in [0, chunk_size)")

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start += chunk_size - overlap
    return chunks


def _embed_chunks_sync(chunks: list[str]) -> list[list[float]]:
    if not chunks:
        return []
    model = _get_model()
    vectors = model.encode(chunks, normalize_embeddings=True)
    return [vec.tolist() for vec in vectors]


async def embed_chunks(chunks: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(_embed_chunks_sync, chunks)


def _article_id(row_or_id: dict | UUID | str) -> UUID:
    if isinstance(row_or_id, UUID):
        return row_or_id
    if isinstance(row_or_id, str):
        return UUID(row_or_id)
    raw = row_or_id.get("id") or row_or_id.get("article_id")
    if raw is None:
        raise ValueError("article row missing id / article_id")
    return raw if isinstance(raw, UUID) else UUID(str(raw))


async def index_article(
    article_id: UUID,
    full_text: str,
    published_at: datetime | None = None,
    *,
    options: IndexingOptions | None = None,
) -> IndexingResult:
    """End-to-end index for one article. Idempotent: re-runs use ON CONFLICT DO NOTHING."""
    del published_at  # reserved for future recency tagging on chunks
    started = time.perf_counter()
    opts = options or IndexingOptions()

    if not full_text or not full_text.strip():
        elapsed = (time.perf_counter() - started) * 1000
        return IndexingResult(
            chunks_written=0, skipped=True, elapsed_ms=elapsed, error="empty text"
        )

    try:
        chunks = chunk_text(full_text, opts.chunk_size, opts.chunk_overlap)
        if not chunks:
            elapsed = (time.perf_counter() - started) * 1000
            return IndexingResult(
                chunks_written=0, skipped=True, elapsed_ms=elapsed, error="no chunks"
            )

        embeddings = await embed_chunks(chunks)
        rows = [
            {
                "article_id": article_id,
                "chunk_index": idx,
                "text": chunk,
                "embedding": embedding,
            }
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        await chunks_db.insert_chunks(rows)
        elapsed = (time.perf_counter() - started) * 1000
        return IndexingResult(
            chunks_written=len(rows), skipped=False, elapsed_ms=elapsed
        )
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        return IndexingResult(
            chunks_written=0, skipped=False, elapsed_ms=elapsed, error=str(exc)
        )


async def index_batch(
    article_rows: list[dict],
    *,
    options: IndexingOptions | None = None,
) -> BatchResult:
    """Index many articles with per-row error isolation; skip snippet_only rows."""
    succeeded = failed = skipped = 0
    outcomes: list[dict[str, Any]] = []

    for row in article_rows:
        aid_raw = row.get("id") or row.get("article_id")
        if row.get("snippet_only"):
            skipped += 1
            outcomes.append(
                {
                    "article_id": str(aid_raw) if aid_raw else None,
                    "status": "skipped",
                    "reason": "snippet_only",
                }
            )
            continue

        try:
            aid = _article_id(row)
        except (ValueError, TypeError) as exc:
            failed += 1
            outcomes.append({"article_id": None, "status": "failed", "reason": str(exc)})
            continue

        result = await index_article(
            aid,
            row.get("full_text") or "",
            row.get("published_at"),
            options=options,
        )

        if result.error and result.chunks_written == 0:
            if result.skipped:
                skipped += 1
                outcomes.append(
                    {
                        "article_id": str(aid),
                        "status": "skipped",
                        "reason": result.error,
                        "elapsed_ms": result.elapsed_ms,
                    }
                )
            else:
                failed += 1
                outcomes.append(
                    {
                        "article_id": str(aid),
                        "status": "failed",
                        "reason": result.error,
                        "elapsed_ms": result.elapsed_ms,
                    }
                )
        else:
            succeeded += 1
            outcomes.append(
                {
                    "article_id": str(aid),
                    "status": "ok",
                    "chunks_written": result.chunks_written,
                    "elapsed_ms": result.elapsed_ms,
                }
            )

    return BatchResult(
        succeeded=succeeded, failed=failed, skipped=skipped, outcomes=outcomes
    )

