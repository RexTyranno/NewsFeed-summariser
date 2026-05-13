from uuid import UUID
from db.connection import get_conn
from datetime import datetime

async def insert_chunks(chunks: list[dict]) -> None:
    async with get_conn() as conn:
        await conn.executemany(
            """
            INSERT INTO chunks (article_id, chunk_index, text, embedding, coarse_tags)
            VALUES ($1, $2, $3, $4::vector, $5)
            ON CONFLICT (article_id, chunk_index) DO NOTHING
            """,
            [
                (c["article_id"], c["chunk_index"], c["text"],
                 str(c["embedding"]), c.get("coarse_tags"))
                for c in chunks
            ],
        )

async def get_chunks_by_article(article_id: UUID) -> list[dict]:
    async with get_conn() as conn:
        return await conn.fetch(
            "SELECT * FROM chunks WHERE article_id = $1", article_id,
        )


async def vector_search(
    embedding: list[float],
    k: int = 20,
    recency_cutoff: datetime | None = None,
) -> list:
    async with get_conn() as conn:
        if recency_cutoff is None:
            return await conn.fetch(
                """
                SELECT c.* FROM chunks c
                ORDER BY c.embedding <=> $1::vector
                LIMIT $2
                """,
                str(embedding), k,
            )
        return await conn.fetch(
            """
            SELECT c.* FROM chunks c
            JOIN articles a ON a.id = c.article_id
            WHERE a.published_at >= $3
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2
            """,
            str(embedding), k, recency_cutoff,
        )

async def delete_chunks_by_article(article_id: UUID) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "DELETE FROM chunks WHERE article_id = $1", article_id,
        )