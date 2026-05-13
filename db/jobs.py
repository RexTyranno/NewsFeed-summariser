from uuid import UUID
from db.connection import get_conn


async def create_job(conn, feed_url: str) -> UUID:
    row = await conn.fetchrow(
        "INSERT INTO ingestion_jobs (feed_url) VALUES ($1) RETURNING id",
        feed_url,
    )
    return row["id"]


async def start_job(conn, job_id: UUID) -> None:
    await conn.execute(
        "UPDATE ingestion_jobs SET status = 'running', started_at = now() WHERE id = $1",
        job_id,
    )


async def finish_job(conn, job_id: UUID, articles_inserted: int) -> None:
    await conn.execute(
        """
        UPDATE ingestion_jobs
        SET status = 'done', finished_at = now(), articles_inserted = $2
        WHERE id = $1
        """,
        job_id, articles_inserted,
    )


async def fail_job(conn, job_id: UUID, error_message: str) -> None:
    await conn.execute(
        """
        UPDATE ingestion_jobs
        SET status = 'failed', finished_at = now(), error_message = $2
        WHERE id = $1
        """,
        job_id, error_message,
    )


async def get_latest_job_for_feed(conn, feed_url: str) -> dict | None:
    return await conn.fetchrow(
        "SELECT * FROM ingestion_jobs WHERE feed_url = $1 ORDER BY created_at DESC LIMIT 1",
        feed_url,
    )


async def get_running_jobs(conn) -> list[dict]:
    return await conn.fetch(
        "SELECT * FROM ingestion_jobs WHERE status = 'running'",
    )