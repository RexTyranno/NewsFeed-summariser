"""Hybrid retrieval: reciprocal rank fusion + per-article dedupe."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.retrieval import fulltext as fulltext_retrieval
from services.retrieval import vector as vector_retrieval

RRF_SCORE_KEY = "_rrf_score"


def hit_id(row: dict[str, Any]) -> str:
    """Stable id for RRF: prefer chunk id, else (article_id, chunk_index), else article_id."""
    cid = row.get("id")
    if cid is not None:
        return f"chunk:{cid}"
    aid = row.get("article_id")
    if aid is not None and row.get("chunk_index") is not None:
        return f"chunk:{aid}:{row['chunk_index']}"
    if aid is not None:
        return f"article:{aid}"
    raise ValueError(f"Cannot derive hit id from row keys: {sorted(row)}")


def reciprocal_rank_fusion(
    vector_hits: list[dict[str, Any]],
    fulltext_hits: list[dict[str, Any]],
    *,
    id_fn: Callable[[dict[str, Any]], str] = hit_id,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """RRF merge of two ranked lists. Adds RRF_SCORE_KEY to each row; sorts descending."""
    scores: dict[str, float] = {}
    reps: dict[str, dict[str, Any]] = {}

    def _accumulate(rank: int, row: dict[str, Any], prefer_new: bool) -> None:
        hid = id_fn(row)
        scores[hid] = scores.get(hid, 0.0) + 1.0 / (rrf_k + rank)
        if hid not in reps:
            reps[hid] = dict(row)
            return
        if prefer_new:
            merged = dict(row)
            merged.update({k: v for k, v in reps[hid].items() if k not in row or row[k] is None})
            reps[hid] = merged

    for rank, row in enumerate(vector_hits, start=1):
        _accumulate(rank, row, prefer_new=False)
    for rank, row in enumerate(fulltext_hits, start=1):
        _accumulate(rank, row, prefer_new=True)

    out: list[dict[str, Any]] = []
    for hid, rep in reps.items():
        r = dict(rep)
        r[RRF_SCORE_KEY] = scores[hid]
        out.append(r)
    out.sort(key=lambda r: r[RRF_SCORE_KEY], reverse=True)
    return out


def dedupe_by_article(
    hits: list[dict[str, Any]],
    *,
    score_key: str = RRF_SCORE_KEY,
) -> list[dict[str, Any]]:
    """Keep the single best-scoring row per article_id (for summarization context)."""
    best: dict[Any, dict[str, Any]] = {}
    for row in hits:
        aid = row.get("article_id")
        if aid is None:
            continue
        cur = best.get(aid)
        if cur is None or row.get(score_key, 0.0) > cur.get(score_key, 0.0):
            best[aid] = row
    merged = list(best.values())
    merged.sort(key=lambda r: r.get(score_key, 0.0), reverse=True)
    return merged


async def hybrid_search(
    query: str,
    k: int = 20,
    *,
    recency_cutoff: datetime | None = None,
    per_modality_k: int | None = None,
    rrf_k: int = 60,
    dedupe_articles: bool = True,
) -> list[dict[str, Any]]:
    """
    Run dense + lexical search in parallel, RRF-merge, optionally one hit per article.

    `per_modality_k` — how many candidates to pull from each leg before fusion
    (defaults to `k` or a sensible minimum).
    """
    n = per_modality_k if per_modality_k is not None else max(k, 20)

    vec_task = vector_retrieval.vector_search(
        query, k=n, recency_cutoff=recency_cutoff
    )
    ft_task = fulltext_retrieval.fulltext_search(
        query, k=n, recency_cutoff=recency_cutoff
    )
    vector_hits, fulltext_hits = await asyncio.gather(vec_task, ft_task)

    fused = reciprocal_rank_fusion(
        vector_hits, fulltext_hits, rrf_k=rrf_k
    )
    if dedupe_articles:
        fused = dedupe_by_article(fused)
    return fused[:k]