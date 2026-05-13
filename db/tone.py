from uuid import UUID
from db.connection import get_conn


async def upsert_tone_framing(conn, row: dict) -> None:
    await conn.execute(
        """
        INSERT INTO tone_framing (article_id, overall_tone, tone_score, framing_cues, extraction_method)
        VALUES ($1,$2,$3,$4,$5)
        ON CONFLICT (article_id) DO UPDATE
            SET overall_tone      = EXCLUDED.overall_tone,
                tone_score        = EXCLUDED.tone_score,
                framing_cues      = EXCLUDED.framing_cues,
                extraction_method = EXCLUDED.extraction_method
        """,
        row["article_id"], row.get("overall_tone"), row.get("tone_score"),
        row.get("framing_cues"), row["extraction_method"],
    )


async def get_tone_by_article(conn, article_id: UUID) -> dict | None:
    return await conn.fetchrow(
        "SELECT * FROM tone_framing WHERE article_id = $1", article_id,
    )


async def get_tone_for_articles(conn, article_ids: list[UUID]) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM tone_framing WHERE article_id = ANY($1)", article_ids,
    )