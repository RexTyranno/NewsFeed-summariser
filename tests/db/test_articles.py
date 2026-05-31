import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from db import articles


def _patch_articles_conn(mock_conn):
    @asynccontextmanager
    async def _cm():
        yield mock_conn
    return patch.object(articles, "get_conn", _cm)


@pytest.mark.asyncio
async def test_upsert_article_returns_uuid_when_row():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": aid})
    article = {
        "source_name": "s",
        "title": "t",
        "url": "https://u",
        "full_text": "x",
        "content_fingerprint": "fp",
    }
    with _patch_articles_conn(mock_conn):
        out = await articles.upsert_article(article)
    assert out == aid
    mock_conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_article_returns_none_when_duplicate():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value=None)
    article = {
        "source_name": "s",
        "title": "t",
        "url": "https://u",
        "full_text": "x",
        "content_fingerprint": "fp",
    }
    with _patch_articles_conn(mock_conn):
        out = await articles.upsert_article(article)
    assert out is None


@pytest.mark.asyncio
async def test_get_article_by_id():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": aid})
    with _patch_articles_conn(mock_conn):
        row = await articles.get_article_by_id(aid)
    assert row["id"] == aid
    mock_conn.fetchrow.assert_awaited_once_with(
        "SELECT * FROM articles WHERE id = $1", aid
    )


@pytest.mark.asyncio
async def test_get_article_by_url():
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"url": "https://x"})
    with _patch_articles_conn(mock_conn):
        row = await articles.get_article_by_url("https://x")
    assert row["url"] == "https://x"


@pytest.mark.asyncio
async def test_get_recent_articles_default_and_custom():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_articles_conn(mock_conn):
        await articles.get_recent_articles()
        await articles.get_recent_articles(limit=5, offset=10)
    mock_conn.fetch.assert_any_await(
        "SELECT * FROM articles ORDER BY ingested_at DESC LIMIT $1 OFFSET $2",
        20, 0,
    )
    mock_conn.fetch.assert_any_await(
        "SELECT * FROM articles ORDER BY ingested_at DESC LIMIT $1 OFFSET $2",
        5, 10,
    )


@pytest.mark.asyncio
async def test_search_articles_fulltext():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_articles_conn(mock_conn):
        await articles.search_articles_fulltext("climate", 15)
    args, _ = mock_conn.fetch.await_args
    assert "plainto_tsquery" in args[0]
    assert args[1] == "climate" and args[2] == 15


@pytest.mark.asyncio
async def test_get_articles_by_source():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_articles_conn(mock_conn):
        await articles.get_articles_by_source("BBC", 30)
    mock_conn.fetch.assert_awaited_once_with(
        "SELECT * FROM articles WHERE source_name = $1 ORDER BY published_at DESC NULLS LAST LIMIT $2",
        "BBC", 30,
    )


@pytest.mark.asyncio
async def test_mark_snippet_only():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    with _patch_articles_conn(mock_conn):
        await articles.mark_snippet_only(aid)
    mock_conn.execute.assert_awaited_once_with(
        "UPDATE articles SET snippet_only = TRUE WHERE id = $1", aid
    )