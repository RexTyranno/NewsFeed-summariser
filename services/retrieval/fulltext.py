from __future__ import annotations

from datetime import datetime

from db.connection import get_conn


async def fulltext_search(
    query: str,
    k: int = 20,
    recency_cutoff: datetime | None = None,
) -> list[dict]:
    """
    BM25-proxy search over articles.title + articles.full_text using the GIN index.
    Rows include both `id` and `article_id` (same value) so fusion.hit_id and
    fusion.dedupe_by_article both work correctly.
    """
    async with get_conn() as conn:
        if recency_cutoff is None:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    id          AS article_id,
                    source_name,
                    title,
                    url,
                    published_at,
                    summary,
                    snippet_only,
                    ts_rank(
                        to_tsvector('english',
                            coalesce(title,'') || ' ' || coalesce(full_text,'')),
                        plainto_tsquery('english', $1)
                    ) AS _ft_rank
                FROM articles
                WHERE
                    to_tsvector('english',
                        coalesce(title,'') || ' ' || coalesce(full_text,''))
                    @@ plainto_tsquery('english', $1)
                    AND snippet_only = FALSE
                ORDER BY _ft_rank DESC
                LIMIT $2
                """,
                query, k,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    id          AS article_id,
                    source_name,
                    title,
                    url,
                    published_at,
                    summary,
                    snippet_only,
                    ts_rank(
                        to_tsvector('english',
                            coalesce(title,'') || ' ' || coalesce(full_text,'')),
                        plainto_tsquery('english', $1)
                    ) AS _ft_rank
                FROM articles
                WHERE
                    to_tsvector('english',
                        coalesce(title,'') || ' ' || coalesce(full_text,''))
                    @@ plainto_tsquery('english', $1)
                    AND snippet_only = FALSE
                    AND published_at >= $3
                ORDER BY _ft_rank DESC
                LIMIT $2
                """,
                query, k, recency_cutoff,
            )
        return [dict(r) for r in rows]


async def fulltext_search_chunks(
    query: str,
    k: int = 20,
) -> list[dict]:
    """
    Passage-level full-text search over chunks.text (no GIN index — seq scan, MVP only).
    Returns chunk rows; `article_id` is already a native column on chunks.
    """
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT
                id,
                article_id,
                chunk_index,
                text,
                ts_rank(
                    to_tsvector('english', text),
                    plainto_tsquery('english', $1)
                ) AS _ft_rank
            FROM chunks
            WHERE to_tsvector('english', text) @@ plainto_tsquery('english', $1)
            ORDER BY _ft_rank DESC
            LIMIT $2
            """,
            query, k,
        )
        return [dict(r) for r in rows]