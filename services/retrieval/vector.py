"""Query-time dense retrieval: embed user text, then pgvector search on chunks."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from db import chunks as chunks_db

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        name = os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        _model = SentenceTransformer(name)
    return _model


def _embed_sync(text: str) -> list[float]:
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


async def embed_query(query: str) -> list[float]:
    return await asyncio.to_thread(_embed_sync, query)


async def vector_search(
    query: str,
    k: int = 20,
    recency_cutoff: datetime | None = None,
):
    embedding = await embed_query(query)
    rows = await chunks_db.vector_search(
        embedding, k=k, recency_cutoff=recency_cutoff
    )
    # asyncpg.Record → plain dicts for JSON / fusion code
    return [dict(r) for r in rows]