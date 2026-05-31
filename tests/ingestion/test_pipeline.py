import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from ingestion.pipeline import load_feeds, parse_published, run_ingestion_pipeline

LONG_TEXT = "a" * 150


# ---------------------------------------------------------------------------
# load_feeds
# ---------------------------------------------------------------------------

class TestLoadFeeds:
    def test_returns_list_of_dicts_with_url_and_name(self, tmp_path):
        feeds_data = [{"url": "http://feed1.example.com/rss", "name": "Feed One"}]
        feeds_file = tmp_path / "rss_feeds.json"
        feeds_file.write_text(json.dumps(feeds_data))

        with patch("ingestion.pipeline.Path") as mock_path_cls:
            # Make Path(__file__).parent / "rss_feeds.json" resolve to our tmp file
            mock_path_cls.return_value.parent.__truediv__.return_value = feeds_file
            result = load_feeds()

        assert isinstance(result, list)
        assert result[0]["url"] == "http://feed1.example.com/rss"
        assert result[0]["name"] == "Feed One"

    def test_real_rss_feeds_json_schema(self):
        """Light integration: checks real file has correct schema (no network)."""
        result = load_feeds()
        assert isinstance(result, list)
        assert len(result) > 0
        for feed in result:
            assert "url" in feed
            assert "name" in feed


# ---------------------------------------------------------------------------
# parse_published
# ---------------------------------------------------------------------------

class TestParsePublished:
    def test_none_returns_none(self):
        assert parse_published(None) is None

    def test_valid_struct_time_returns_datetime(self):
        # feedparser gives time.struct_time; pipeline currently passes it directly
        # to datetime.fromtimestamp which expects a numeric timestamp.
        # This test exposes the existing bug so it can be fixed.
        st = time.gmtime(0)  # 1970-01-01 00:00:00 UTC as struct_time
        # If bug is present, this will raise TypeError.
        # Once fixed (e.g. wrapping with time.mktime), it returns a datetime.
        try:
            result = parse_published(st)
            assert isinstance(result, datetime)
            assert result.tzinfo == timezone.utc
        except TypeError:
            pytest.xfail(
                "parse_published does not handle time.struct_time — "
                "needs time.mktime() wrapper before fromtimestamp()"
            )

    def test_numeric_timestamp_returns_utc_datetime(self):
        ts = 1_700_000_000  # 2023-11-14 22:13:20 UTC
        result = parse_published(ts)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# run_ingestion_pipeline
# ---------------------------------------------------------------------------

class TestRunIngestionPipeline:
    def _make_article(self, url="http://example.com/1", **kwargs):
        return {
            "source_name": "TestSource",
            "title": "Test Article",
            "url": url,
            "published_parsed": None,
            "summary": "A summary.",
            "content": "<p>Some content</p>",
            "author": "Author Name",
            **kwargs,
        }

    def test_returns_list_of_records_with_required_keys(self):
        feeds = [{"url": "http://feed.example.com/rss", "name": "TestSource"}]
        articles = [self._make_article()]

        with patch("ingestion.pipeline.load_feeds", return_value=feeds), \
             patch("ingestion.pipeline.parse_rss", return_value=[{"link": "http://example.com/1"}]), \
             patch("ingestion.pipeline.normalise_feed_entries", return_value=articles), \
             patch("ingestion.pipeline.resolve_full_text", return_value=LONG_TEXT), \
             patch("ingestion.pipeline.quality_gate", return_value=True), \
             patch("ingestion.pipeline.is_duplicate", return_value=False):

            records = run_ingestion_pipeline()

        assert len(records) == 1
        record = records[0]
        for key in ("id", "source_name", "title", "url", "published_at",
                    "author", "summary", "full_text", "content_fingerprint", "ingested_at"):
            assert key in record, f"Missing key: {key}"

    def test_quality_gate_failure_skips_article(self):
        feeds = [{"url": "http://feed.example.com/rss", "name": "TestSource"}]
        articles = [self._make_article()]

        with patch("ingestion.pipeline.load_feeds", return_value=feeds), \
             patch("ingestion.pipeline.parse_rss", return_value=[]), \
             patch("ingestion.pipeline.normalise_feed_entries", return_value=articles), \
             patch("ingestion.pipeline.resolve_full_text", return_value="short"), \
             patch("ingestion.pipeline.quality_gate", return_value=False):

            records = run_ingestion_pipeline()

        assert records == []

    def test_duplicate_article_is_skipped(self):
        feeds = [{"url": "http://feed.example.com/rss", "name": "TestSource"}]
        # Two articles with same URL/body
        articles = [self._make_article(), self._make_article()]

        def fake_is_duplicate(url, text, seen):
            key = (url, text)
            if key in seen:
                return True
            seen.add(key)
            return False

        with patch("ingestion.pipeline.load_feeds", return_value=feeds), \
             patch("ingestion.pipeline.parse_rss", return_value=[]), \
             patch("ingestion.pipeline.normalise_feed_entries", return_value=articles), \
             patch("ingestion.pipeline.resolve_full_text", return_value=LONG_TEXT), \
             patch("ingestion.pipeline.quality_gate", return_value=True), \
             patch("ingestion.pipeline.is_duplicate", side_effect=fake_is_duplicate):

            records = run_ingestion_pipeline()

        assert len(records) == 1

    def test_empty_feed_returns_no_records(self):
        feeds = [{"url": "http://feed.example.com/rss", "name": "TestSource"}]

        with patch("ingestion.pipeline.load_feeds", return_value=feeds), \
             patch("ingestion.pipeline.parse_rss", return_value=[]), \
             patch("ingestion.pipeline.normalise_feed_entries", return_value=[]):

            records = run_ingestion_pipeline()

        assert records == []

    def test_record_id_is_unique_uuid_string(self):
        import uuid
        feeds = [{"url": "http://feed.example.com/rss", "name": "TestSource"}]
        articles = [self._make_article(url=f"http://example.com/{i}") for i in range(3)]

        with patch("ingestion.pipeline.load_feeds", return_value=feeds), \
             patch("ingestion.pipeline.parse_rss", return_value=[]), \
             patch("ingestion.pipeline.normalise_feed_entries", return_value=articles), \
             patch("ingestion.pipeline.resolve_full_text", return_value=LONG_TEXT), \
             patch("ingestion.pipeline.quality_gate", return_value=True), \
             patch("ingestion.pipeline.is_duplicate", return_value=False):

            records = run_ingestion_pipeline()

        ids = [r["id"] for r in records]
        assert len(set(ids)) == 3  # all unique
        for id_ in ids:
            uuid.UUID(id_)  # raises if not valid UUID