from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch


@asynccontextmanager
async def fake_get_conn(mock_conn: AsyncMock):
    yield mock_conn

def patch_get_conn(target: str, mock_conn):
    @asynccontextmanager
    async def _cm():
        yield mock_conn
    return patch(target, _cm)