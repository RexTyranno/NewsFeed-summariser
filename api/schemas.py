from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ArticleOut(BaseModel):
    id: UUID
    source_name: str | None = None
    title: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    summary: str | None = None
    snippet_only: bool = False
    ingested_at: datetime | None = None

    model_config = {"from_attributes": True}


class ArticleSearchOut(ArticleOut):
    rrf_score: float | None = None


class SimilarArticlesOut(BaseModel):
    article_id: UUID
    results: list[ArticleSearchOut]


class SourceRefOut(BaseModel):
    index: int
    article_id: str
    title: str | None = None
    source_name: str | None = None
    url: str | None = None
    published_at: str | None = None


class TimelineEventOut(BaseModel):
    event: str
    resolved_date: str | None = None
    article_ref: int
    confidence: float


class ResearchRequest(BaseModel):
    topic: str
    k: int = 10
    recency_days: int | None = None


class ResearchResponse(BaseModel):
    summary: str
    sources: list[SourceRefOut]
    timeline_events: list[TimelineEventOut]