import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import db.connection as connection


@pytest.fixture(autouse=True)
def reset_pool():
    connection._pool = None
    yield
    connection._pool = None


@pytest.mark.asyncio
async def test_get_pool_creates_once_and_caches(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/test")

    mock_pool = MagicMock()
    created = {"n": 0}

    async def fake_create_pool(dsn):
        created["n"] += 1
        return mock_pool

    with patch("db.connection.asyncpg.create_pool", new=fake_create_pool):
        p1 = await connection.get_pool()
        p2 = await connection.get_pool()

    assert p1 is mock_pool is p2
    assert created["n"] == 1


@pytest.mark.asyncio
async def test_close_pool_closes_and_clears(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/test")
    mock_pool = MagicMock()
    mock_pool.close = AsyncMock()

    async def fake_create_pool(dsn):
        return mock_pool

    with patch("db.connection.asyncpg.create_pool", new=fake_create_pool):
        await connection.get_pool()
        await connection.close_pool()

    mock_pool.close.assert_awaited_once()
    assert connection._pool is None


@pytest.mark.asyncio
async def test_close_pool_noop_when_none():
    connection._pool = None
    await connection.close_pool()  # should not raise


@pytest.mark.asyncio
async def test_get_conn_yields_acquired_connection(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test/test")
    mock_conn = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=mock_cm)
    mock_pool.close = AsyncMock()

    async def fake_create_pool(dsn):
        return mock_pool

    with patch("db.connection.asyncpg.create_pool", new=fake_create_pool):
        async with connection.get_conn() as conn:
            assert conn is mock_conn
    mock_pool.acquire.assert_called_once()