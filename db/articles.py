from uuid import UUID
from db.connection import get_conn


async def upsert_article(article: dict) -> UUID | None:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO articles (
                source_name, title, url, published_at, author, summary,
                full_text, content_fingerprint, extraction_method,
                snippet_only, fetched_at
            )
                        SELECT $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11
            WHERE NOT EXISTS (
                SELECT 1 FROM articles
                WHERE url = $3 OR content_fingerprint = $8
            )
            RETURNING id
            """,
            article["source_name"], article["title"], article["url"],
            article.get("published_at"), article.get("author"),
            article.get("summary"), article["full_text"],
            article["content_fingerprint"], article.get("extraction_method"),
            article.get("snippet_only", False), article.get("fetched_at"),
        )
        return row["id"] if row else None


async def get_article_by_id(article_id: UUID) -> dict | None:
    async with get_conn() as conn:
        return await conn.fetchrow(
            "SELECT * FROM articles WHERE id = $1", article_id
        )


async def get_article_by_url(url: str) -> dict | None:
    async with get_conn() as conn:
        return await conn.fetchrow(
            "SELECT * FROM articles WHERE url = $1", url
        )


async def get_recent_articles(limit: int = 20, offset: int = 0) -> list:
    async with get_conn() as conn:
        return await conn.fetch(
            "SELECT * FROM articles ORDER BY ingested_at DESC LIMIT $1 OFFSET $2",
            limit, offset,
        )


async def search_articles_fulltext(query: str, limit: int = 20) -> list:
    async with get_conn() as conn:
        return await conn.fetch(
            """
            SELECT * FROM articles
            WHERE to_tsvector('english', coalesce(title,'') || ' ' || coalesce(full_text,''))
                  @@ plainto_tsquery('english', $1)
            ORDER BY published_at DESC NULLS LAST
            LIMIT $2
            """,
            query, limit,
        )


async def get_articles_by_source(source_name: str, limit: int = 50) -> list:
    async with get_conn() as conn:
        return await conn.fetch(
            "SELECT * FROM articles WHERE source_name = $1 ORDER BY published_at DESC NULLS LAST LIMIT $2",
            source_name, limit,
        )


async def mark_snippet_only(article_id: UUID) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE articles SET snippet_only = TRUE WHERE id = $1", article_id
        )