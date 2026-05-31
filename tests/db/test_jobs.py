import uuid
from unittest.mock import AsyncMock

import pytest

from db import jobs


@pytest.mark.asyncio
async def test_create_job_returns_id():
    jid = uuid.uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": jid})
    out = await jobs.create_job(conn, "https://feed")
    assert out == jid
    conn.fetchrow.assert_awaited_once_with(
        "INSERT INTO ingestion_jobs (feed_url) VALUES ($1) RETURNING id",
        "https://feed",
    )


@pytest.mark.asyncio
async def test_start_job():
    conn = AsyncMock()
    jid = uuid.uuid4()
    await jobs.start_job(conn, jid)
    conn.execute.assert_awaited_once_with(
        "UPDATE ingestion_jobs SET status = 'running', started_at = now() WHERE id = $1",
        jid,
    )


@pytest.mark.asyncio
async def test_finish_job():
    conn = AsyncMock()
    jid = uuid.uuid4()
    await jobs.finish_job(conn, jid, 7)
    sql = conn.execute.await_args.args[0]
    assert "status = 'done'" in sql
    assert conn.execute.await_args.args[1:] == (jid, 7)


@pytest.mark.asyncio
async def test_fail_job():
    conn = AsyncMock()
    jid = uuid.uuid4()
    await jobs.fail_job(conn, jid, "boom")
    sql = conn.execute.await_args.args[0]
    assert "failed" in sql
    assert conn.execute.await_args.args[1:] == (jid, "boom")


@pytest.mark.asyncio
async def test_get_latest_job_for_feed():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    await jobs.get_latest_job_for_feed(conn, "https://f")
    conn.fetchrow.assert_awaited_once_with(
        "SELECT * FROM ingestion_jobs WHERE feed_url = $1 ORDER BY created_at DESC LIMIT 1",
        "https://f",
    )


@pytest.mark.asyncio
async def test_get_running_jobs():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    await jobs.get_running_jobs(conn)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM ingestion_jobs WHERE status = 'running'",
    )