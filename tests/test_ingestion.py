import pytest
from unittest.mock import patch, MagicMock
from ingestion.pipeline import load_feeds
from ingestion.rss import parse_rss, normalise_feed_entries


def test_load_feed():
    """Integration: real rss_feeds.json has correct schema."""
    feeds = load_feeds()
    assert isinstance(feeds, list)
    assert len(feeds) > 0
    assert all(isinstance(feed, dict) for feed in feeds)
    assert all("url" in feed and "name" in feed for feed in feeds)


def test_parse_rss_returns_raw_entries():
    """parse_rss returns raw feedparser entries (link/title, NOT source_name/url)."""
    entry = {"title": "Test", "link": "http://example.com/1", "summary": "blurb"}
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [entry]

    with patch("ingestion.rss.feedparser.parse", return_value=mock_feed):
        result = parse_rss("http://example.com/feed")

    assert isinstance(result, list)
    assert len(result) == 1
    # Raw entries have 'link', not 'url'; no 'source_name'
    assert "link" in result[0]
    assert "source_name" not in result[0]


def test_normalise_feed_entries_produces_correct_shape():
    """normalise_feed_entries maps raw entries to the normalised shape."""
    raw_entries = [{"title": "Test", "link": "http://example.com/1", "summary": "blurb", "content": []}]
    result = normalise_feed_entries(raw_entries, source_name="TestSource")

    assert len(result) == 1
    article = result[0]
    assert article["source_name"] == "TestSource"
    assert article["url"] == "http://example.com/1"
    assert "title" in article
    assert "published_parsed" in article
    assert "summary" in article
    assert "content" in article
    assert "author" in article