from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from api.schemas import ArticleOut, SimilarArticlesOut, ArticleSearchOut
from db.articles import get_recent_articles, get_article_by_id
from db.chunks import vector_search
from services.retrieval.vector import embed_query

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("/recent", response_model=list[ArticleOut])
async def recent_articles(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    rows = await get_recent_articles(limit=limit, offset=offset)
    return rows


@router.get("/{article_id}/similar", response_model=SimilarArticlesOut)
async def similar_articles(
    article_id: UUID,
    k: int = Query(10, ge=1, le=50),
):
    article = await get_article_by_id(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    full_text = article.get("full_text") or article.get("summary") or ""
    if not full_text.strip():
        return SimilarArticlesOut(article_id=article_id, results=[])

    embedding = await embed_query(full_text)
    rows = await vector_search(embedding, k=k, exclude_article_id=article_id)

    seen: set[str] = set()
    results: list[ArticleSearchOut] = []
    for row in rows:
        aid = str(row.get("article_id") or row.get("id"))
        if aid in seen or aid == str(article_id):
            continue
        seen.add(aid)
        results.append(ArticleSearchOut(**row))
        if len(results) >= k:
            break

    return SimilarArticlesOut(article_id=article_id, results=results)