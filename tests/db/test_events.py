import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from db import events


def _patch_events_conn(mock_conn):
    @asynccontextmanager
    async def _cm():
        yield mock_conn
    return patch.object(events, "get_conn", _cm)


@pytest.mark.asyncio
async def test_insert_event_returns_id_and_passes_fields():
    eid = uuid.uuid4()
    aid = uuid.uuid4()
    anchor = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": eid})
    payload = {
        "article_id": aid,
        "text": "t",
        "offset_start": 1,
        "offset_end": 2,
        "time_expr_type": "DATE",
        "resolved_start": datetime.now(timezone.utc),
        "resolved_end": datetime.now(timezone.utc),
        "certainty": "high",
        "anchor_event_id": anchor,
        "resolution_notes": "n",
        "extraction_method": "m",
    }
    with _patch_events_conn(mock_conn):
        out = await events.insert_event(payload)
    assert out == eid
    args = mock_conn.fetchrow.await_args.args
    assert args[1] is aid and args[9] is anchor


@pytest.mark.asyncio
async def test_insert_event_link():
    lid = uuid.uuid4()
    s = uuid.uuid4()
    t = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetchrow = AsyncMock(return_value={"id": lid})
    with _patch_events_conn(mock_conn):
        out = await events.insert_event_link(
            {"source_event_id": s, "target_event_id": t, "relation": "before", "offset_value": 3}
        )
    assert out == lid


@pytest.mark.asyncio
async def test_get_events_by_article():
    aid = uuid.uuid4()
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_events_conn(mock_conn):
        await events.get_events_by_article(aid)
    mock_conn.fetch.assert_awaited_once_with(
        "SELECT * FROM events WHERE article_id = $1", aid
    )


@pytest.mark.asyncio
async def test_get_timeline_for_articles():
    ids = [uuid.uuid4(), uuid.uuid4()]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_events_conn(mock_conn):
        await events.get_timeline_for_articles(ids)
    sql = mock_conn.fetch.await_args.args[0]
    assert "ORDER BY e.resolved_start NULLS LAST" in sql
    assert mock_conn.fetch.await_args.args[1] == ids


@pytest.mark.asyncio
async def test_get_event_links():
    ids = [uuid.uuid4()]
    mock_conn = AsyncMock()
    mock_conn.fetch = AsyncMock(return_value=[])
    with _patch_events_conn(mock_conn):
        await events.get_event_links(ids)
    mock_conn.fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_event_resolution():
    eid = uuid.uuid4()
    rs = datetime.now(timezone.utc)
    re = datetime.now(timezone.utc)
    mock_conn = AsyncMock()
    with _patch_events_conn(mock_conn):
        await events.update_event_resolution(eid, rs, re, "med", "notes")
    mock_conn.execute.assert_awaited_once_with(
        "UPDATE events SET resolved_start = $1, resolved_end = $2, certainty = $3, resolution_notes = $4 WHERE id = $5",
        rs, re, "med", "notes", eid,
    )