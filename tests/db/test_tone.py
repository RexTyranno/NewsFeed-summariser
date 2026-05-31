import uuid
from unittest.mock import AsyncMock

import pytest

from db import tone


@pytest.mark.asyncio
async def test_upsert_tone_framing_execute():
    conn = AsyncMock()
    aid = uuid.uuid4()
    await tone.upsert_tone_framing(
        conn,
        {
            "article_id": aid,
            "overall_tone": "neutral",
            "tone_score": 0.0,
            "framing_cues": [],
            "extraction_method": "llm",
        },
    )
    conn.execute.assert_awaited_once()
    assert "ON CONFLICT (article_id) DO UPDATE" in conn.execute.await_args.args[0]


@pytest.mark.asyncio
async def test_get_tone_by_article():
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=None)
    aid = uuid.uuid4()
    await tone.get_tone_by_article(conn, aid)
    conn.fetchrow.assert_awaited_once_with(
        "SELECT * FROM tone_framing WHERE article_id = $1", aid
    )


@pytest.mark.asyncio
async def test_get_tone_for_articles():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    ids = [uuid.uuid4()]
    await tone.get_tone_for_articles(conn, ids)
    conn.fetch.assert_awaited_once_with(
        "SELECT * FROM tone_framing WHERE article_id = ANY($1)", ids
    )