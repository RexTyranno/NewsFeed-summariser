from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from api.schemas import ResearchRequest, ResearchResponse, SourceRefOut, TimelineEventOut
from services.retrieval.fusion import hybrid_search
from services.summarisation import summarise

router = APIRouter(prefix="/research", tags=["research"])


@router.post("", response_model=ResearchResponse)
async def research(body: ResearchRequest):
    recency_cutoff: datetime | None = None
    if body.recency_days is not None:
        recency_cutoff = datetime.now(tz=timezone.utc) - timedelta(days=body.recency_days)

    rows = await hybrid_search(body.topic, k=body.k, recency_cutoff=recency_cutoff)
    payload = await summarise(body.topic, rows, max_sources=body.k)

    return ResearchResponse(
        summary=payload.summary,
        sources=[SourceRefOut(**vars(s)) for s in payload.sources],
        timeline_events=[TimelineEventOut(**vars(e)) for e in payload.timeline_events],
    )