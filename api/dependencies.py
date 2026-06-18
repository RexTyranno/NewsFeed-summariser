from typing import AsyncGenerator

import asyncpg

import db.connection as db_conn


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    async with db_conn.get_conn() as conn:
        yield conn