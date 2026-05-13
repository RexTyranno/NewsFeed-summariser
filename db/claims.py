from db.connection import get_conn
from uuid import UUID

async def insert_entities(conn, entities: list[dict]) -> None:
    await conn.executemany(
        "INSERT INTO entities (article_id, text, label, offset_start, offset_end) VALUES ($1,$2,$3,$4,$5)",
        [(e["article_id"], e["text"], e["label"], e.get("offset_start"), e.get("offset_end"))
         for e in entities],
    )

async def insert_claim(conn, claim: dict) -> UUID:
    row = await conn.fetchrow(
        """
        INSERT INTO claims (article_id, subject_entity_id, predicate, object,
            is_numeric, raw_value, normalized_value, unit, time_phrase,
            resolved_date, extraction_method, confidence)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        RETURNING id
        """,
        claim["article_id"], claim.get("subject_entity_id"), claim["predicate"],
        claim["object"], claim.get("is_numeric", False), claim.get("raw_value"),
        claim.get("normalized_value"), claim.get("unit"), claim.get("time_phrase"),
        claim.get("resolved_date"), claim["extraction_method"], claim.get("confidence"),
    )
    return row["id"]

async def get_entities_by_article(conn, article_id: UUID) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM entities WHERE article_id = $1", article_id,
    )

async def get_claims_by_article(conn, article_id: UUID) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM claims WHERE article_id = $1", article_id,
    )

async def get_conflicting_numeric_claims(conn, article_ids: list[UUID]) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM claims WHERE article_id = ANY($1) AND is_numeric = TRUE",
        article_ids,
    )

async def get_claims_for_conflict_reasoning(conn, article_ids: list[UUID]) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM claims WHERE article_id = ANY($1)",
        article_ids,
    )