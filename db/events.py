from uuid import UUID
from db.connection import get_conn
from datetime import datetime

async def insert_event(event: dict) -> UUID:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO events (article_id, text, offset_start, offset_end,
                time_expr_type, resolved_start, resolved_end, certainty,
                anchor_event_id, resolution_notes, extraction_method)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING id
            """,
            event["article_id"], event["text"], event.get("offset_start"),
            event.get("offset_end"), event.get("time_expr_type"),
            event.get("resolved_start"), event.get("resolved_end"),
            event.get("certainty"), event.get("anchor_event_id"),
            event.get("resolution_notes"), event.get("extraction_method"),
        )
        return row["id"]

async def insert_event_link(event_link: dict) -> UUID:
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO event_links (source_event_id, target_event_id, relation, offset_value)
            VALUES ($1,$2,$3,$4)
            RETURNING id
            """,
            event_link["source_event_id"], event_link["target_event_id"],
            event_link["relation"], event_link.get("offset_value"),
        )
        return row["id"]
        
async def get_events_by_article(article_id: UUID) -> list[dict]:
    async with get_conn() as conn:
        return await conn.fetch(
            "SELECT * FROM events WHERE article_id = $1", article_id,
        )
        
async def get_timeline_for_articles(article_ids: list[UUID]) -> list[dict]:
    async with get_conn() as conn:
        return await conn.fetch(
            """
            SELECT e.* FROM events e
            JOIN articles a ON a.id = e.article_id
            WHERE e.article_id = ANY($1)
            ORDER BY e.resolved_start NULLS LAST, a.published_at NULLS LAST
            """,
            article_ids,
        )

async def get_event_links(event_ids: list[UUID]) -> list[dict]:
    async with get_conn() as conn:
        return await conn.fetch(
            "SELECT * FROM event_links WHERE source_event_id = ANY($1) OR target_event_id = ANY($1)",
            event_ids,
        )

async def update_event_resolution(event_id: UUID, resolved_start: datetime, resolved_end: datetime, certainty: str, resolution_notes: str) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE events SET resolved_start = $1, resolved_end = $2, certainty = $3, resolution_notes = $4 WHERE id = $5",
            resolved_start, resolved_end, certainty, resolution_notes, event_id,
        )