import json
from pathlib import Path
import uuid
import logging
from datetime import datetime, timezone

from .rss import parse_rss, normalise_feed_entries
from .fulltext import resolve_full_text, quality_gate
from .dedup import is_duplicate, content_fingerprint

logging.basicConfig(level=logging.INFO)

def load_feeds() -> list[dict]:
    feeds_path = Path(__file__).parent / "rss_feeds.json"
    with open(feeds_path) as f:
        return json.load(f)

def parse_published(published_parsed: datetime) -> datetime:
    if published_parsed is None:
        return None
    return datetime.fromtimestamp(published_parsed, timezone.utc)

def run_ingestion_pipeline() -> list[dict]:
    feeds = load_feeds()
    seen = set()
    records = []

    for feed in feeds:
        entries = parse_rss(feed["url"])
        articles = normalise_feed_entries(entries, source_name=feed["name"])

        for article in articles:
            full_text = resolve_full_text(article)
            if not quality_gate(full_text):
                logging.info("Quality gate failed for %s", article.get("url"))
                continue
            if is_duplicate(article["url"], full_text, seen):
                continue

            record = {
                "id": str(uuid.uuid4()),
                "source_name": article["source_name"],
                "title": article["title"],
                "url": article["url"],
                "published_at": parse_published(article.get("published_parsed")),
                "author": article.get("author"),
                "summary": article.get("summary"),
                "full_text": full_text,
                "content_fingerprint": content_fingerprint(full_text),
                "ingested_at": datetime.now(timezone.utc)
            }
            records.append(record)
    return records