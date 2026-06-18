from typing import Literal

from fastapi import APIRouter, Query

from api.schemas import ArticleSearchOut
from db.articles import search_articles_fulltext
from services.retrieval.fusion import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/articles", response_model=list[ArticleSearchOut])
async def search_articles(
    q: str = Query(..., min_length=1),
    k: int = Query(20, ge=1, le=100),
    mode: Literal["hybrid", "fulltext"] = Query("hybrid"),
):
    if mode == "fulltext":
        rows = await search_articles_fulltext(q, limit=k)
    else:
        rows = await hybrid_search(q, k=k)
    return rows