import uuid
from unittest.mock import AsyncMock

import pytest

from db import claims


@pytest.mark.asyncio
async def test_insert_entities_executemany():
    conn = AsyncMock()
    aid = uuid.uuid4()
    await claims.insert_entities(
        conn,
        [{"article_id": aid, "text": "e", "label": "ORG", "offset_start": 0, "offset_end": 3}],
    )
    conn.executemany.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_claim_returns_uuid_and_defaults_is_numeric():
    cid = uuid.uuid4()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": cid})
    aid = uuid.uuid4()
    out = await claims.insert_claim(
        conn,
        {
            "article_id": aid,
            "predicate": "p",
            "object": "o",
            "extraction_method": "m",
        },
    )
    assert out == cid
    args, _ = conn.fetchrow.await_args
    assert args[5] is False


@pytest.mark.asyncio
async def test_get_entities_by_article():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    aid = uuid.uuid4()
    await claims.get_entities_by_article(conn, aid)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM entities WHERE article_id = $1", aid
    )


@pytest.mark.asyncio
async def test_get_claims_by_article():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    aid = uuid.uuid4()
    await claims.get_claims_by_article(conn, aid)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM claims WHERE article_id = $1", aid
    )


@pytest.mark.asyncio
async def test_get_conflicting_numeric_claims():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    ids = [uuid.uuid4()]
    await claims.get_conflicting_numeric_claims(conn, ids)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM claims WHERE article_id = ANY($1) AND is_numeric = TRUE", ids
    )


@pytest.mark.asyncio
async def test_get_claims_for_conflict_reasoning():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    ids = [uuid.uuid4(), uuid.uuid4()]
    await claims.get_claims_for_conflict_reasoning(conn, ids)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM claims WHERE article_id = ANY($1)", ids
    )