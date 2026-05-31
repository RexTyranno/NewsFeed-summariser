import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from db import chunks


def _patch_chunks_conn(mock_conn):
    @asynccontextmanager
    async def _cm():
        yield mock_conn
    return patch.object(chunks, "get_conn", _cm)


@pytest.mark.asyncio
async def test_insert_chunks_executemany_shape():
    aid = uuid.uuid4()
    emb = [0.1, 0.2]
    mock_conn = AsyncMock()
    with _patch_chunks_conn(mock_conn):
        await chunks.insert_chunks(
            [
                {"article_id": aid, "chunk_index": 0, "text": "a", "embedding": emb},
                {"article_id": aid, "chunk_index": 1, "text": "b", "embedding": emb, "coarse_tags": ["x"]},
            ]
        )
    mock_conn.executemany.assert_awaited_once()
    sql, rows = mock_conn.executemany.await_args.args
    assert "::vector" in sql
    assert rows[0][3] == str(emb) and rows[0][4] is None
    assert rows[1][4] == ["x"]


@pytest.mark.asyncio
async def test_insert_chunks_empty_list():
    mock_conn = AsyncMock()
    with _patch_chunks_conn(mock_conn):
        await chunks.insert_chunks([])
    mock_conn.executemany.assert_awaited_once()
    assert mock_conn.executemany.await_args.args[1] == []


@pytest.mark.asyncio
async def test_get_chunks_by_article():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_chunks_conn(mock_conn):
        await chunks.get_chunks_by_article(aid)
    mock_conn.fetch.assert_awaited_once_with(
        "SELECT * FROM chunks WHERE article_id = $1", aid
    )


@pytest.mark.asyncio
async def test_vector_search_without_cutoff():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    emb = [1.0, 0.0]
    with _patch_chunks_conn(mock_conn):
        await chunks.vector_search(emb, k=5)
    sql = mock_conn.fetch.await_args.args[0]
    assert "JOIN articles" not in sql
    assert mock_conn.fetch.await_args.args[1:] == (str(emb), 5)


@pytest.mark.asyncio
async def test_vector_search_with_cutoff():
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    emb = [1.0, 0.0]
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with _patch_chunks_conn(mock_conn):
        await chunks.vector_search(emb, k=3, recency_cutoff=cutoff)
    args = mock_conn.fetch.await_args.args
    assert "JOIN articles a" in args[0]
    assert args[1:] == (str(emb), 3, cutoff)


@pytest.mark.asyncio
async def test_delete_chunks_by_article():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    with _patch_chunks_conn(mock_conn):
        await chunks.delete_chunks_by_article(aid)
    mock_conn.execute.assert_awaited_once_with(
        "DELETE FROM chunks WHERE article_id = $1", aid
    )