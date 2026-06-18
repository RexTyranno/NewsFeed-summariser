from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from .LLM_service.client import llm_client

from db.articles import get_article_by_id


@dataclass
class SourceRef:
    index: int
    article_id: str
    title: str | None
    source_name: str | None
    url: str | None
    published_at: str | None


@dataclass
class TimelineEvent:
    event: str
    resolved_date: str | None
    article_ref: int
    confidence: float


@dataclass
class SummaryPayload:
    summary: str
    sources: list[SourceRef] = field(default_factory=list)
    timeline_events: list[TimelineEvent] = field(default_factory=list)


def _format_published(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _passage_text(row: dict[str, Any]) -> str:
    for key in ("text", "full_text", "summary"):
        val = row.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


async def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    """Vector chunk hits lack title/source — hydrate from articles when needed."""
    if row.get("title") and row.get("source_name"):
        return row
    aid = row.get("article_id") or row.get("id")
    if aid is None:
        return row
    try:
        uid = aid if isinstance(aid, UUID) else UUID(str(aid))
    except (TypeError, ValueError):
        return row
    article = await get_article_by_id(uid)
    if not article:
        return row
    merged = dict(article)
    merged.update({k: v for k, v in row.items() if v is not None})
    return merged


async def _pack_context(
    retrieved_rows: list[dict[str, Any]],
    *,
    max_sources: int,
) -> tuple[list[SourceRef], str]:
    seen: set[str] = set()
    sources: list[SourceRef] = []
    blocks: list[str] = []

    for row in retrieved_rows:
        enriched = await _enrich_row(row)
        aid = enriched.get("article_id") or enriched.get("id")
        if aid is None:
            continue
        aid_str = str(aid)
        if aid_str in seen:
            continue
        seen.add(aid_str)
        if len(sources) >= max_sources:
            break

        index = len(sources) + 1
        passage = _passage_text(enriched)
        title = enriched.get("title") or "Untitled"
        source_name = enriched.get("source_name") or "Unknown"
        published = _format_published(enriched.get("published_at")) or "unknown"

        sources.append(
            SourceRef(
                index=index,
                article_id=aid_str,
                title=title,
                source_name=source_name,
                url=enriched.get("url"),
                published_at=_format_published(enriched.get("published_at")),
            )
        )
        blocks.append(
            f"[{index}] {title}\n"
            f"Source: {source_name} | Published: {published}\n"
            f"{passage}"
        )

    return sources, "\n\n".join(blocks)


def _build_prompt(topic: str, context_block: str) -> str:
    return (
        "You are a news research assistant. Summarise the topic using ONLY the numbered "
        "sources below. Cite sources inline as [N] matching the indices in the context.\n\n"
        f"Topic: {topic}\n\n"
        f"Sources:\n{context_block}\n\n"
        "Return ONLY valid JSON with exactly these keys:\n"
        "{\n"
        '  "summary": "2-4 paragraph synthesis with [N] citations",\n'
        '  "sources_used": [1, 2],\n'
        '  "timeline_events": [\n'
        '    {"event": "...", "resolved_date": "YYYY-MM-DD or null", '
        '"article_ref": 1, "confidence": 0.0}\n'
        "  ]\n"
        "}\n"
        "Use only indices present in the context. "
        "If dates are unclear, set resolved_date to null and lower confidence."
    )


def _parse_timeline_events(raw: Any) -> list[TimelineEvent]:
    if not isinstance(raw, list):
        return []
    events: list[TimelineEvent] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        event = str(item.get("event", "")).strip()
        if not event:
            continue
        ref = item.get("article_ref", 0)
        try:
            article_ref = int(ref)
        except (TypeError, ValueError):
            article_ref = 0
        conf_raw = item.get("confidence", 0.5)
        try:
            confidence = float(conf_raw)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))
        resolved = item.get("resolved_date")
        resolved_date = str(resolved).strip() if resolved not in (None, "", "null") else None
        events.append(
            TimelineEvent(
                event=event,
                resolved_date=resolved_date,
                article_ref=article_ref,
                confidence=confidence,
            )
        )
    return events


def _filter_sources_used(
    sources: list[SourceRef], sources_used: Any
) -> list[SourceRef]:
    if not isinstance(sources_used, list) or not sources_used:
        return sources
    wanted = set()
    for x in sources_used:
        try:
            wanted.add(int(x))
        except (TypeError, ValueError):
            continue
    if not wanted:
        return sources
    return [s for s in sources if s.index in wanted]


def _unavailable_payload() -> SummaryPayload:
    return SummaryPayload(summary="unavailable", sources=[], timeline_events=[])


async def summarise(
    topic: str,
    retrieved_rows: list[dict],
    *,
    max_sources: int = 10,
    model: str | None = None,
) -> SummaryPayload:
    if not topic.strip() or not retrieved_rows:
        return _unavailable_payload()

    sources, context_block = await _pack_context(
        retrieved_rows, max_sources=max_sources
    )
    if not sources or not context_block.strip():
        return _unavailable_payload()

    prompt = _build_prompt(topic.strip(), context_block)
    data = await llm_client.generate_json(
        prompt,
        required_keys={"summary", "sources_used", "timeline_events"},
        model=model,
    )
    if data is None:
        return _unavailable_payload()

    summary = str(data.get("summary", "")).strip() or "unavailable"
    filtered_sources = _filter_sources_used(sources, data.get("sources_used"))
    timeline_events = _parse_timeline_events(data.get("timeline_events"))

    return SummaryPayload(
        summary=summary,
        sources=filtered_sources,
        timeline_events=timeline_events,
    )