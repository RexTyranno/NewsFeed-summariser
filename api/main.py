from contextlib import asynccontextmanager

from fastapi import FastAPI

import db.connection as db_conn
from api.routers import health, articles, search, research


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db_conn.get_pool()
    yield
    await db_conn.close_pool()


app = FastAPI(title="NewsFeed Summariser", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(articles.router)
app.include_router(search.router)
app.include_router(research.router)